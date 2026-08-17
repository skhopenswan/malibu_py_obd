#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪佛兰迈锐宝 1.5T OBD PID 采样基准测试脚本
包含两大阶段：
  阶段 1 —— PID 采样最小间隔测试（重点：MAP / MAF 高频同步配对）
  阶段 2 —— 三元催化相关 PID 可读性测试（ECT/RPM/STFT/LTFT/O2/MAF/MAP/TPS/车速等）

输出：
  - 终端实时打印
  - 同步保存报告至 data_logs/benchmark_<时间戳>.txt
"""

import os
import sys
import time
from datetime import datetime
from statistics import mean

import obd

# ==================== 用户配置区域 ====================
PORT_NAME = "COM4"           # OBD 串口号（根据实际设备管理器修改）
BAUD_RATE = 38400            # 波特率，默认 38400

SINGLE_PID_TRIES = 20        # 阶段1：单 PID 响应时间测量次数
PAIR_TRIES = 100             # 阶段1：MAP+MAF 背靠背配对测量次数
READABILITY_TRIES = 5        # 阶段2：三元相关 PID 可读性采样次数

LOG_DIR = os.path.join(os.path.dirname(__file__), "data_logs")
# ======================================================

# 阶段 1 核心 PID（采样最小间隔测试重点）
CORE_PIDS = {
    "RPM": obd.commands.RPM,
    "MAP": obd.commands.INTAKE_PRESSURE,
    "MAF": obd.commands.MAF,
    "TPS": obd.commands.THROTTLE_POS,
    "Load": obd.commands.ENGINE_LOAD,
}

# 阶段 1 批量吞吐量测试用的 PID 组（从核心到扩充）
BATCH_GROUPS = [
    ("2 PID (MAP+MAF)", ["MAP", "MAF"]),
    ("3 PID (+RPM)", ["MAP", "MAF", "RPM"]),
    ("5 PID (+TPS+Load)", ["MAP", "MAF", "RPM", "TPS", "Load"]),
    ("10 PID (全项)", [
        "RPM", "MAP", "MAF", "TPS", "Load",
        "Coolant", "STFT", "LTFT", "O2_B1S1", "O2_B1S2",
    ]),
]

# 阶段 2 三元催化相关 PID 可读性测试项
READABILITY_PIDS = {
    "ECT(冷却液温度)": obd.commands.COOLANT_TEMP,
    "RPM(转速)": obd.commands.RPM,
    "STFT(短期燃油修正)": obd.commands.SHORT_FUEL_TRIM_1,
    "LTFT(长期燃油修正)": obd.commands.LONG_FUEL_TRIM_1,
    "O2_B1S1(前氧窄带V)": obd.commands.O2_B1S1,
    "O2_B1S2(后氧窄带V)": obd.commands.O2_B1S2,
    "A/F_B1S1(前氧宽域V)": obd.commands.O2_S1_WR_VOLTAGE,
    "A/F_B1S1(前氧宽域电流)": obd.commands.O2_S1_WR_CURRENT,
    "指令当量比(EQ_RATIO)": obd.commands.COMMANDED_EQUIV_RATIO,
    "Load(发动机负荷)": obd.commands.ENGINE_LOAD,
    "MAP(进气歧管压力)": obd.commands.INTAKE_PRESSURE,
    "MAF(空气流量)": obd.commands.MAF,
    "TPS(节气门开度)": obd.commands.THROTTLE_POS,
    "Speed(车速)": obd.commands.SPEED,
    "CatTemp_B1S1(三元温度)": obd.commands.CATALYST_TEMP_B1S1,
    "CatTemp_B1S2(三元温度)": obd.commands.CATALYST_TEMP_B1S2,
}


def query_magnitude(connection, command):
    """安全读取 OBD 数值，返回 float 或 None"""
    try:
        res = connection.query(command)
        if not res.is_null() and res.value is not None:
            return round(float(res.value.magnitude), 4)
    except Exception:
        pass
    return None


def fmt_or_na(v, suffix=""):
    if v is None:
        return "N/A"
    return f"{v}{suffix}"


def measure_single_pid(connection, command, tries):
    """测量单个 PID 的往返响应时间（不含 sleep），返回 (耗时列表ms, 有效次数)"""
    times_ms = []
    valid = 0
    for _ in range(tries):
        t0 = time.perf_counter()
        val = query_magnitude(connection, command)
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)
        if val is not None:
            valid += 1
    return times_ms, valid


def measure_pair_map_maf(connection, tries):
    """背靠背连续查询 MAP 与 MAF，测量配对总耗时（核心同步采样率）"""
    times_ms = []
    valid_pairs = 0
    for _ in range(tries):
        t0 = time.perf_counter()
        m = query_magnitude(connection, obd.commands.INTAKE_PRESSURE)
        a = query_magnitude(connection, obd.commands.MAF)
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)
        if m is not None and a is not None:
            valid_pairs += 1
    return times_ms, valid_pairs


def measure_batch(connection, pid_keys, command_map, rounds=20):
    """测量一组 PID 完整一轮的总耗时，返回 (每轮耗时ms列表, 有效轮数)"""
    times_ms = []
    valid_rounds = 0
    for _ in range(rounds):
        t0 = time.perf_counter()
        ok = True
        for k in pid_keys:
            v = query_magnitude(connection, command_map[k])
            if v is None:
                ok = False
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)
        if ok:
            valid_rounds += 1
    return times_ms, valid_rounds


def main():
    report = []
    def emit(line=""):
        print(line)
        report.append(line)

    emit("=" * 78)
    emit("   雪佛兰迈锐宝 1.5T OBD PID 采样基准测试 (最小间隔 + 三元催化可读性)")
    emit("=" * 78)
    emit(f"  端口: {PORT_NAME}  波特率: {BAUD_RATE}")
    emit(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("=" * 78)

    connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
    if not connection.is_connected():
        emit("❌ 无法连接 OBD 设备！")
        emit("  - 请确认 COM 端口号 (默认为 COM4) 与车辆点火开关是否打开")
        emit("  - 脚本将只保存本次连接失败的说明，稍后可在车上重新运行")
        save_report(report)
        return

    emit(f"✅ 连接成功！协议: {connection.protocol_name()}")
    emit("")

    # ================= 阶段 1：采样最小间隔测试 =================
    emit("=" * 78)
    emit(" 阶段 1 —— PID 采样最小间隔测试")
    emit("=" * 78)

    emit("\n【1.1 单 PID 响应时间】(每个 PID 连续查询 %d 次，测量往返耗时)" % SINGLE_PID_TRIES)
    emit(f"{'PID':<8} {'响应率':<8} {'平均ms':<10} {'最小ms':<10} {'最大ms':<10} {'等效Hz':<10}")
    emit("-" * 66)
    single_summary = {}
    for key, cmd in CORE_PIDS.items():
        times_ms, valid = measure_single_pid(connection, cmd, SINGLE_PID_TRIES)
        avg = mean(times_ms)
        mn = min(times_ms)
        mx = max(times_ms)
        hz = (1000.0 / avg) if avg > 0 else 0.0
        single_summary[key] = hz
        emit(f"{key:<8} {valid}/{SINGLE_PID_TRIES:<6} {avg:<10.2f} {mn:<10.2f} {mx:<10.2f} {hz:<10.1f}")

    emit("\n【1.2 MAP + MAF 背靠背配对】(连续查询 MAP→MAF 无间隔，测量 %d 次核心同步采样)" % PAIR_TRIES)
    pair_times, pair_valid = measure_pair_map_maf(connection, PAIR_TRIES)
    if pair_valid > 0:
        avg = mean(pair_times)
        mn = min(pair_times)
        mx = max(pair_times)
        hz = (1000.0 / avg) if avg > 0 else 0.0
        emit(f"  配对数响应率: {pair_valid}/{PAIR_TRIES}")
        emit(f"  配对往返耗时: 平均 {avg:.1f} ms | 最小 {mn:.1f} ms | 最大 {mx:.1f} ms")
        emit(f"  → MAP+MAF 配对有效采样率: {hz:.1f} Hz (MAP/MAF 各自同频)")
        emit(f"  → 每个 PID 平均采样间隔: {avg:.1f} ms")
        emit(f"  结论: {'✅ 满足高频同步' if hz >= 5 else '⚠️ 建议观察，ELM327 速度受限，可考虑仅轮询 MAP+MAF 两项'}")

    emit("\n【1.3 批量 PID 吞吐量】(每组 PID 连续轮询 %d 轮，测每轮总耗时)" % 20)
    emit(f"{'批量场景':<24} {'平均/轮ms':<12} {'等效首PID Hz':<14}")
    emit("-" * 56)
    # 构建命令映射，覆盖各组所需 PID
    cmd_map = {k: v for k, v in CORE_PIDS.items()}
    cmd_map.update({
        "Coolant": obd.commands.COOLANT_TEMP,
        "STFT": obd.commands.SHORT_FUEL_TRIM_1,
        "LTFT": obd.commands.LONG_FUEL_TRIM_1,
        "O2_B1S1": obd.commands.O2_B1S1,
        "O2_B1S2": obd.commands.O2_B1S2,
    })
    for label, keys in BATCH_GROUPS:
        times_ms, valid = measure_batch(connection, keys, cmd_map, rounds=20)
        if times_ms:
            avg = mean(times_ms)
            hz = (1000.0 / avg) if avg > 0 else 0.0
            emit(f"{label:<24} {avg:<12.1f} {hz:<14.1f}")

    emit("\n  * 说明: 批量 PID 越多，单个 PID 有效采样率越低；")
    emit("    若需 MAP/MAF 最高同步频率，建议单独轮询这两项，而非混入全量 20 列。")

    # ================= 阶段 2：三元催化相关 PID 可读性测试 =================
    emit("\n\n" + "=" * 78)
    emit(" 阶段 2 —— 三元催化相关 PID 可读性测试")
    emit("=" * 78)
    emit(f"  每个 PID 采样 {READABILITY_TRIES} 次，报告响应率与数值范围。\n")

    emit(f"{'PID (数据项)':<24} {'响应率':<8} {'数值范围 / 典型值':<22} {'状态'}")
    emit("-" * 78)
    for label, cmd in READABILITY_PIDS.items():
        vals = []
        for _ in range(READABILITY_TRIES):
            vals.append(query_magnitude(connection, cmd))
        valid_vals = [v for v in vals if v is not None]
        resp_rate = f"{len(valid_vals)}/{READABILITY_TRIES}"
        if valid_vals:
            mn = min(valid_vals)
            mx = max(valid_vals)
            rng = f"[{mn}, {mx}]"
            if mn == mx:
                rng = f"恒定 {mn}"
            status = "✅ 可读"
        else:
            rng = "-"
            status = "❌ 不支持/无响应"
        emit(f"{label:<24} {resp_rate:<8} {rng:<22} {status}")

    emit("\n" + "-" * 78)
    emit(" 判读提示:")
    emit("  - 2017 迈锐宝 1.5T(LFV) 前氧多为宽域传感器；若 O2_B1S1 恒定或跳变弱，")
    emit("    请改看 A/F_B1S1(宽域电压) 与 A/F_B1S1(宽域电流)。")
    emit("  - 三元健康: 闭环下前氧快速跳变(0.1~0.9V 或 λ~1.0)，后氧稳态(0.5~0.8V)。")
    emit("  - CatTemp 为 PID 013C/013E，部分 ELM327 或 ECU 不支持，无响应属正常。")

    connection.close()
    emit("\n✅ 基准测试完成。")
    save_report(report)


def save_report(report):
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    report_path = os.path.join(LOG_DIR, f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        f.write("\n")
    print(f"\n📄 报告已保存至: {report_path}")


if __name__ == "__main__":
    main()