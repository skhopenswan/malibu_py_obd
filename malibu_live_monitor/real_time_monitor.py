#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪佛兰迈锐宝 1.5T OBD 实时数据检测与自动存盘程序（含断线自动重连容错）
实现一边实时终端展示关注的 OBD 数据项，一边将数据同步保存为 CSV 文件。
支持行驶中 OBD 线缆松动/断连后自动高容错循环重连，全程无需驾驶员手动操作。

v2 更新：
  - fast=True 启用 ELM327 帧数优化，提升查询速度
  - 快/慢两组分批轮询：核心 PID 每轮读取，慢变量每 5 轮读取一次
  - 新增三元催化温度(CatTemp_B1S1)、指令当量比(EQ_Ratio)、相对节气门(RelThrottle)
"""

import os
import sys
import time
import csv
from datetime import datetime
import obd
from obd.decoders import raw_string

# ==================== 用户配置区域 ====================
PORT_NAME = "COM4"           # OBD 串口号（根据实际电脑设备管理器修改）
BAUD_RATE = 38400            # 波特率，默认 38400
SLOW_GROUP_INTERVAL = 5      # 慢组 PID 每 N 轮采集一次
RETRY_DELAY = 2.5            # OBD 断连后重连重试间隔（秒）
DISCONNECT_THRESHOLD = 2     # 连续读取失败多少次后判定为掉线并触发自动重连
LOG_DIR = os.path.join(os.path.dirname(__file__), "data_logs")  # 日志存储目录
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


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def log_event(event_file_path, msg):
    """记录断连与重连事件到日志文本文件"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}\n"
    try:
        with open(event_file_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def get_gm_tft(connection):
    try:
        res = connection.query(gm_tft_cmd, force=True)
        if not res.is_null():
            raw_str = str(res.value).replace(" ", "")
            idx = raw_str.find("621940")
            if idx != -1 and len(raw_str) >= idx + 8:
                hex_val = raw_str[idx + 6 : idx + 8]
                temp = int(hex_val, 16) - 40
                return temp, f"{temp} °C"
    except Exception:
        pass
    return None, "N/A"


def safe_query_magnitude(connection, command):
    try:
        res = connection.query(command)
        if not res.is_null() and res.value is not None:
            return round(float(res.value.magnitude), 2)
    except Exception:
        pass
    return None


def safe_query_str(connection, command):
    try:
        res = connection.query(command)
        if not res.is_null() and res.value is not None:
            val = res.value
            if isinstance(val, (tuple, list)):
                return "/".join(str(v) for v in val)
            return str(val)
    except Exception:
        pass
    return "N/A"


def query_fast_group(connection):
    """快速组 PID：每轮都查询的核心数据（动力/进气/燃油/氧传感器/三元）"""
    return {
        "rpm":       safe_query_magnitude(connection, obd.commands.RPM),
        "map_kpa":   safe_query_magnitude(connection, obd.commands.INTAKE_PRESSURE),
        "maf":       safe_query_magnitude(connection, obd.commands.MAF),
        "throttle":  safe_query_magnitude(connection, obd.commands.THROTTLE_POS),
        "load":      safe_query_magnitude(connection, obd.commands.ENGINE_LOAD),
        "stft":      safe_query_magnitude(connection, obd.commands.SHORT_FUEL_TRIM_1),
        "ltft":      safe_query_magnitude(connection, obd.commands.LONG_FUEL_TRIM_1),
        "o2_b1s1":   safe_query_magnitude(connection, obd.commands.O2_B1S1),
        "o2_b1s2":   safe_query_magnitude(connection, obd.commands.O2_B1S2),
        "cat_temp":  safe_query_magnitude(connection, obd.commands.CATALYST_TEMP_B1S1),
        "eq_ratio":  safe_query_magnitude(connection, obd.commands.COMMANDED_EQUIV_RATIO),
        "rel_throttle": safe_query_magnitude(connection, obd.commands.RELATIVE_THROTTLE_POS),
    }


def query_slow_group(connection):
    """慢速组 PID：每 SLOW_GROUP_INTERVAL 轮才查询一次的辅助数据"""
    return {
        "speed":     safe_query_magnitude(connection, obd.commands.SPEED),
        "coolant":   safe_query_magnitude(connection, obd.commands.COOLANT_TEMP),
        "iat":       safe_query_magnitude(connection, obd.commands.INTAKE_TEMP),
        "baro_kpa":  safe_query_magnitude(connection, obd.commands.BAROMETRIC_PRESSURE),
        "timing":    safe_query_magnitude(connection, obd.commands.TIMING_ADVANCE),
        "voltage":   safe_query_magnitude(connection, obd.commands.ELM_VOLTAGE),
        "fuel_status": safe_query_str(connection, obd.commands.FUEL_STATUS),
        "amb_temp":  safe_query_magnitude(connection, obd.commands.AMBIANT_AIR_TEMP),
        "tft":       get_gm_tft(connection),
    }


def main():
    print("=" * 60)
    print("      雪佛兰迈锐宝 1.5T OBD 实时数据检测与同步存盘系统")
    print("      (v2 高速版：快慢分组轮询 + ELM327帧数优化 + 三元催化监控)")
    print("=" * 60)

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file_path = os.path.join(LOG_DIR, f"malibu_obd_log_{timestamp_str}.csv")
    event_log_path = os.path.join(LOG_DIR, f"malibu_connection_events_{timestamp_str}.log")

    csv_headers = [
        "Timestamp", "RPM(rpm)", "MAP(kPa)", "MAF(g/s)", "ThrottlePos(%)",
        "RelThrottlePos(%)", "EngineLoad(%)", "STFT(%)", "LTFT(%)",
        "O2_B1S1(V)", "O2_B1S2(V)", "CatTemp_B1S1(C)", "EQ_Ratio",
        "BoostPressure(bar)", "Speed(km/h)", "CoolantTemp(C)", "IntakeTemp(C)",
        "BaroPressure(kPa)", "TimingAdvance(deg)", "Voltage(V)",
        "FuelStatus", "AmbAirTemp(C)", "TFT(C)"
    ]

    try:
        csv_file = open(csv_file_path, mode='w', newline='', encoding='utf-8-sig')
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)
        csv_file.flush()
    except IOError as e:
        print(f"❌ 无法创建日志文件: {e}")
        return

    log_event(event_log_path, f"系统启动(v2高速版)，初始化数据文件: {os.path.basename(csv_file_path)}")

    connection = None
    sample_count = 0
    fail_count = 0

    print(f"✅ 日志将同步保存至: {csv_file_path}")
    print(f"正在首次建立 OBD 连接 ({PORT_NAME}, {BAUD_RATE}, fast=True)...")

    # ---- 持久化慢组缓存值（断线重连后不清空，保持屏幕显示上一组慢变量）----
    slow_cache = {
        "speed": None, "coolant": None, "iat": None, "baro_kpa": None,
        "timing": None, "voltage": None, "fuel_status": "N/A",
        "amb_temp": None, "tft_val": None, "tft_display": "N/A",
    }

    try:
        reconnect_attempts = 0
        while True:
            try:
                connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=True)
                if connection.is_connected():
                    log_event(event_log_path, "OBD 接口连接成功 (fast=True)")
                    break
            except Exception:
                pass
            reconnect_attempts += 1
            clear_screen()
            print("==================================================================")
            print(" ⚠️  OBD 端口未连接/卡顿，系统正在后台自动重试中...")
            print("==================================================================")
            print(f" 状态: 端口 {PORT_NAME} 正在进行第 {reconnect_attempts} 次重连尝试...")
            print(" 提示: 行驶过程中无需操作电脑，插入线缆/通电后将自动恢复采集。")
            print(" (按 Ctrl+C 可停止程序)")
            time.sleep(RETRY_DELAY)

        while True:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            if connection is None or not connection.is_connected():
                fail_count += 1
            else:
                try:
                    rpm = safe_query_magnitude(connection, obd.commands.RPM)
                    if rpm is None:
                        volt = safe_query_magnitude(connection, obd.commands.ELM_VOLTAGE)
                        if volt is None:
                            fail_count += 1
                        else:
                            fail_count = 0
                    else:
                        fail_count = 0
                except Exception:
                    fail_count += 1

            if fail_count >= DISCONNECT_THRESHOLD:
                log_event(event_log_path, f"检测到 OBD 掉线 (连续 {fail_count} 次无响应)，触发自动重连机制")
                if connection:
                    try:
                        connection.close()
                    except Exception:
                        pass
                connection = None

                reconnect_count = 0
                while True:
                    reconnect_count += 1
                    clear_screen()
                    print("==================================================================")
                    print(" ⚠️  OBD 掉线告警：连接中断，后台正在自动高容错重连...")
                    print("==================================================================")
                    print(f" 重连尝试: 第 {reconnect_count} 次  | 已安全保存数据: {sample_count} 条")
                    print(f" 日志文件: {os.path.basename(csv_file_path)}")
                    print(" 提示: 安全第一！行驶中请专心驾驶，系统将在连接恢复后自动继续记账。")
                    print(" (按 Ctrl+C 可退出)")

                    try:
                        connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=True)
                        if connection.is_connected():
                            log_event(event_log_path, f"OBD 连接成功恢复！(共重试 {reconnect_count} 次)")
                            fail_count = 0
                            break
                    except Exception:
                        pass
                    time.sleep(RETRY_DELAY)

            # ---- 每轮都查：快组 ----
            f = query_fast_group(connection)

            # ---- 每 SLOW_GROUP_INTERVAL 轮查一次：慢组 ----
            is_slow_round = (sample_count % SLOW_GROUP_INTERVAL == 0)
            if is_slow_round and connection is not None and connection.is_connected():
                s = query_slow_group(connection)
                slow_cache["speed"] = s["speed"]
                slow_cache["coolant"] = s["coolant"]
                slow_cache["iat"] = s["iat"]
                slow_cache["baro_kpa"] = s["baro_kpa"]
                slow_cache["timing"] = s["timing"]
                slow_cache["voltage"] = s["voltage"]
                slow_cache["fuel_status"] = s["fuel_status"]
                slow_cache["amb_temp"] = s["amb_temp"]
                slow_cache["tft_val"], slow_cache["tft_display"] = s["tft"]

            # ---- 计算增压值 ----
            boost_bar = None
            map_kpa = f["map_kpa"]
            baro_kpa = slow_cache["baro_kpa"]
            if map_kpa is not None:
                ref_baro = baro_kpa if (baro_kpa is not None and baro_kpa > 0) else 101.3
                boost_bar = round((map_kpa - ref_baro) / 100.0, 2)

            # ---- 写 CSV ----
            row_data = [
                now_str,
                f["rpm"] if f["rpm"] is not None else "",
                f["map_kpa"] if f["map_kpa"] is not None else "",
                f["maf"] if f["maf"] is not None else "",
                f["throttle"] if f["throttle"] is not None else "",
                f["rel_throttle"] if f["rel_throttle"] is not None else "",
                f["load"] if f["load"] is not None else "",
                f["stft"] if f["stft"] is not None else "",
                f["ltft"] if f["ltft"] is not None else "",
                f["o2_b1s1"] if f["o2_b1s1"] is not None else "",
                f["o2_b1s2"] if f["o2_b1s2"] is not None else "",
                f["cat_temp"] if f["cat_temp"] is not None else "",
                f["eq_ratio"] if f["eq_ratio"] is not None else "",
                boost_bar if boost_bar is not None else "",
                slow_cache["speed"] if slow_cache["speed"] is not None else "",
                slow_cache["coolant"] if slow_cache["coolant"] is not None else "",
                slow_cache["iat"] if slow_cache["iat"] is not None else "",
                slow_cache["baro_kpa"] if slow_cache["baro_kpa"] is not None else "",
                slow_cache["timing"] if slow_cache["timing"] is not None else "",
                slow_cache["voltage"] if slow_cache["voltage"] is not None else "",
                slow_cache["fuel_status"],
                slow_cache["amb_temp"] if slow_cache["amb_temp"] is not None else "",
                slow_cache["tft_val"] if slow_cache["tft_val"] is not None else "",
            ]

            writer.writerow(row_data)
            csv_file.flush()
            sample_count += 1

            # ---- 终端面板 ----
            clear_screen()
            fmt = lambda v, u="": f"{v} {u}".strip() if v is not None else "N/A"

            print("==================================================================")
            print("    迈锐宝 1.5T (LFV) OBD 实时数据检测面板 (v2 高速版)")
            print("==================================================================")
            print(f" [时间] {now_str}  |  已采: {sample_count} 条  |  {'慢组刷新' if is_slow_round else '快组轮询'}")
            print(f" [日志] {os.path.basename(csv_file_path)}")
            print("------------------------------------------------------------------")
            print(" 1. 动力与工况 (每轮)")
            print(f"    转速(RPM)   : {fmt(f['rpm'], 'RPM'):<12}  车速(Speed) : {fmt(slow_cache['speed'], 'km/h')}")
            print(f"    负荷(Load)  : {fmt(f['load'], '%'):<12}  点火提前角  : {fmt(slow_cache['timing'], '°')}")
            print(f"    节气门(ABS) : {fmt(f['throttle'], '%'):<12}  相对节气门  : {fmt(f['rel_throttle'], '%')}")
            print(f"    闭/开环     : {slow_cache['fuel_status']}")
            print("------------------------------------------------------------------")
            print(" 2. 进气与增压 (每轮 → 排查漏气/PCV/增压核心)")
            print(f"    MAP(kPa)    : {fmt(f['map_kpa'], 'kPa'):<12}  BARO(kPa)  : {fmt(slow_cache['baro_kpa'], 'kPa')}")
            print(f"    增压(Boost) : {fmt(boost_bar, 'bar'):<12}  MAF(g/s)   : {fmt(f['maf'], 'g/s')}")
            print("    * 怠速 Boost 负数=真空正常；加速转正。")
            print("------------------------------------------------------------------")
            print(" 3. 燃油修正与氧传感器 + 三元催化 (每轮)")
            print(f"    STFT(%)     : {fmt(f['stft'], '%'):<12}  LTFT(%)    : {fmt(f['ltft'], '%')}")
            print(f"    前氧 B1S1(V): {fmt(f['o2_b1s1'], 'V'):<12}  后氧 B1S2(V):{fmt(f['o2_b1s2'], 'V')}")
            print(f"    当量比(EQ)  : {fmt(f['eq_ratio']):<12}  三元温度(C) : {fmt(f['cat_temp'], '°C')}")
            print("    * 怠速 STFT/LTFT>+10% 警惕漏气; 三元温度正常 400-800°C。")
            print("------------------------------------------------------------------")
            print(" 4. 温度与系统电压 (每 %d 轮)" % SLOW_GROUP_INTERVAL)
            print(f"    冷却液(ECT) : {fmt(slow_cache['coolant'], '°C'):<12}  进气(IAT)  : {fmt(slow_cache['iat'], '°C')}")
            print(f"    变速箱(TFT) : {fmt(slow_cache['tft_display']):<12}  环境(AMB)  : {fmt(slow_cache['amb_temp'], '°C')}")
            print(f"    电瓶电压(V) : {fmt(slow_cache['voltage'], 'V')}")
            print("==================================================================")
            print(" 【退出】Ctrl+C  |  快组 12 PID ~1.5-2 Hz | 慢组 9 PID 每 %d 轮" % SLOW_GROUP_INTERVAL)
            print("          新增：三元催化温度 / 指令当量比 / 相对节气门开度")

            # v2: 不再固定 sleep，采集速率仅受查询耗时限制

    except KeyboardInterrupt:
        print("\n\n接收到 Ctrl+C 退出指令，正在关闭程序...")
        log_event(event_log_path, "用户发送退出指令，程序正常停止")
    finally:
        try:
            csv_file.close()
        except Exception:
            pass
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        print("------------------------------------------------------------------")
        print(f"✅ 数据日志已保存至:\n   {csv_file_path}")
        print(f"   断线事件日志保存至:\n   {event_log_path}")
        print(f"   本次运行累计采集 {sample_count} 组数据。")
        print("------------------------------------------------------------------")


if __name__ == "__main__":
    main()