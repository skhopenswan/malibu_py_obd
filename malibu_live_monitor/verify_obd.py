#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪佛兰迈锐宝 1.5T ELM327 OBD 数据可信度校验脚本
用于检测非原厂 ELM327 适配器读出的各项 OBD 数据是否真实有效、是否存在卡死假数据或数值超界问题。
"""

import os
import sys
import time
from datetime import datetime
import obd
from obd.decoders import raw_string

# ==================== 用户配置区域 ====================
PORT_NAME = "COM4"           # OBD 串口号
BAUD_RATE = 38400            # 波特率
SAMPLE_COUNT = 10            # 采样测试次数
SAMPLE_INTERVAL = 0.5        # 采样间隔（秒）
LOG_DIR = os.path.join(os.path.dirname(__file__), "data_logs")
# ======================================================

gm_tft_cmd = obd.OBDCommand(
    "GM_TFT",
    "Transmission Fluid Temp",
    b"221940",
    0,
    raw_string,
    obd.ECU.ALL,
    fast=False
)

PID_SPECS = {
    "RPM": {"cmd": obd.commands.RPM, "unit": "rpm", "min": 0, "max": 8000, "is_dynamic": True},
    "SPEED": {"cmd": obd.commands.SPEED, "unit": "km/h", "min": 0, "max": 260, "is_dynamic": False},
    "COOLANT_TEMP": {"cmd": obd.commands.COOLANT_TEMP, "unit": "°C", "min": -40, "max": 130, "is_dynamic": False},
    "INTAKE_TEMP": {"cmd": obd.commands.INTAKE_TEMP, "unit": "°C", "min": -40, "max": 100, "is_dynamic": False},
    "MAP": {"cmd": obd.commands.INTAKE_PRESSURE, "unit": "kPa", "min": 10, "max": 300, "is_dynamic": True},
    "BARO": {"cmd": obd.commands.BAROMETRIC_PRESSURE, "unit": "kPa", "min": 50, "max": 120, "is_dynamic": False},
    "THROTTLE": {"cmd": obd.commands.THROTTLE_POS, "unit": "%", "min": 0, "max": 100, "is_dynamic": True},
    "STFT": {"cmd": obd.commands.SHORT_FUEL_TRIM_1, "unit": "%", "min": -50, "max": 50, "is_dynamic": True},
    "LTFT": {"cmd": obd.commands.LONG_FUEL_TRIM_1, "unit": "%", "min": -50, "max": 50, "is_dynamic": False},
    "MAF": {"cmd": obd.commands.MAF, "unit": "g/s", "min": 0, "max": 500, "is_dynamic": True},
    "O2_B1S1": {"cmd": obd.commands.O2_B1S1, "unit": "V", "min": 0.0, "max": 1.5, "is_dynamic": True},
    "O2_B1S2": {"cmd": obd.commands.O2_B1S2, "unit": "V", "min": 0.0, "max": 1.5, "is_dynamic": True},
    "TIMING": {"cmd": obd.commands.TIMING_ADVANCE, "unit": "°", "min": -60, "max": 60, "is_dynamic": True},
    "VOLTAGE": {"cmd": obd.commands.ELM_VOLTAGE, "unit": "V", "min": 8.0, "max": 18.0, "is_dynamic": False},
    "LOAD": {"cmd": obd.commands.ENGINE_LOAD, "unit": "%", "min": 0, "max": 100, "is_dynamic": True},
    "AMB_TEMP": {"cmd": obd.commands.AMB_AIR_TEMP, "unit": "°C", "min": -40, "max": 60, "is_dynamic": False},
}

def query_pid_value(connection, pid_key):
    spec = PID_SPECS[pid_key]
    res = connection.query(spec["cmd"])
    if not res.is_null() and res.value is not None:
        try:
            return round(float(res.value.magnitude), 2)
        except (AttributeError, ValueError, TypeError):
            return None
    return None

def query_tft_value(connection):
    try:
        res = connection.query(gm_tft_cmd, force=True)
        if not res.is_null():
            raw_str = str(res.value).replace(" ", "")
            idx = raw_str.find("621940")
            if idx != -1 and len(raw_str) >= idx + 8:
                return int(raw_str[idx + 6 : idx + 8], 16) - 40
    except Exception:
        pass
    return None

def analyze_samples(values, spec_min, spec_max, is_dynamic):
    valid_vals = [v for v in values if v is not None]
    if not valid_vals:
        return "⚠️ 车辆/ELM不响应 (不支持)", "全为空 (None)"

    count = len(valid_vals)
    min_v = min(valid_vals)
    max_v = max(valid_vals)
    avg_v = round(sum(valid_vals) / count, 2)

    if min_v < spec_min or max_v > spec_max:
        return f"❌ 数值异常 (超出范围 [{spec_min}, {spec_max}])", f"范围: [{min_v}, {max_v}]"

    if is_dynamic and count >= 5 and (max_v - min_v == 0):
        return "⚠️ 无波动 (疑似 ELM327 缓存卡死)", f"恒定值: {min_v}"

    return "✅ 数据可信 (响应正常，范围合理)", f"均值: {avg_v}, 范围: [{min_v}, {max_v}]"

def main():
    print("=" * 70)
    print("      雪佛兰迈锐宝 ELM327 OBD 读取值有效性与可信度校验程序")
    print("=" * 70)
    print(f"正在建立 OBD 连接 ({PORT_NAME}, {BAUD_RATE})...")

    connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
    if not connection.is_connected():
        print("❌ 连接失败！请检查串口与适配器线缆。")
        return

    print(f"✅ 连接成功！开始对各项 OBD 数据进行 {SAMPLE_COUNT} 次采样校验...\n")

    sample_results = {k: [] for k in PID_SPECS.keys()}
    tft_samples = []

    for i in range(1, SAMPLE_COUNT + 1):
        print(f"\r正在进行第 {i}/{SAMPLE_COUNT} 次采样...", end="", flush=True)
        for key in PID_SPECS.keys():
            val = query_pid_value(connection, key)
            sample_results[key].append(val)
        tft_samples.append(query_tft_value(connection))
        time.sleep(SAMPLE_INTERVAL)

    print("\n\n采样完成！正在生成数据可信度分析报告...\n")
    connection.close()

    lines = []
    lines.append("=" * 75)
    lines.append(f"       迈锐宝 1.5T ELM327 OBD 数据可信度校验报告 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    lines.append("=" * 75)
    lines.append(f"{'数据项(PID)':<14} | {'响应率':<8} | {'可信度结论':<28} | {'采样统计与提示'}")
    lines.append("-" * 75)

    valid_count = 0
    total_items = len(PID_SPECS) + 1

    for key, spec in PID_SPECS.items():
        vals = sample_results[key]
        resp_rate = f"{len([v for v in vals if v is not None])}/{SAMPLE_COUNT}"
        conclusion, stat_desc = analyze_samples(vals, spec["min"], spec["max"], spec["is_dynamic"])
        if "✅" in conclusion:
            valid_count += 1
        lines.append(f"{key:<14} | {resp_rate:<8} | {conclusion:<28} | {stat_desc}")

    tft_resp_rate = f"{len([v for v in tft_samples if v is not None])}/{SAMPLE_COUNT}"
    tft_conclusion, tft_stat_desc = analyze_samples(tft_samples, -40, 150, False)
    if "✅" in tft_conclusion:
        valid_count += 1
    lines.append(f"{'TFT(Mode22)':<14} | {tft_resp_rate:<8} | {tft_conclusion:<28} | {tft_stat_desc}")

    lines.append("=" * 75)
    lines.append("【检测汇总】")
    lines.append(f"  - 共校验 {total_items} 项数据，其中 {valid_count} 项完全可信，{total_items - valid_count} 项存在风险。")
    lines.append("=" * 75)

    report_text = "\n".join(lines)
    print(report_text)

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    report_path = os.path.join(LOG_DIR, f"obd_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n✅ 可信度校验报告已保存至: {report_path}")

if __name__ == "__main__":
    main()

