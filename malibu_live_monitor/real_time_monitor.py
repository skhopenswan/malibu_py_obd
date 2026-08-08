#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪佛兰迈锐宝 1.5T OBD 实时数据检测与自动存盘程序（含断线自动重连容错）
实现一边实时终端展示关注的 OBD 数据项，一边将数据同步保存为 CSV 文件。
支持行驶中 OBD 线缆松动/断连后自动高容错循环重连，全程无需驾驶员手动操作。
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
REFRESH_INTERVAL = 0.8       # 数据采集与刷屏间隔（秒）
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



def main():
    print("=" * 60)
    print("      雪佛兰迈锐宝 1.5T OBD 实时数据检测与同步存盘系统")
    print("      (高容错模式：含断线自动重连，行驶中无须操作电脑)")
    print("=" * 60)

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file_path = os.path.join(LOG_DIR, f"malibu_obd_log_{timestamp_str}.csv")
    event_log_path = os.path.join(LOG_DIR, f"malibu_connection_events_{timestamp_str}.log")

    csv_headers = [
        "Timestamp", "RPM(rpm)", "Speed(km/h)", "CoolantTemp(C)", "IntakeTemp(C)",
        "MAP(kPa)", "BaroPressure(kPa)", "BoostPressure(bar)", "ThrottlePos(%)",
        "STFT(%)", "LTFT(%)", "MAF(g/s)", "O2_B1S1(V)", "O2_B1S2(V)",
        "TimingAdvance(deg)", "Voltage(V)", "EngineLoad(%)", "FuelStatus",
        "AmbAirTemp(C)", "TFT(C)"
    ]

    try:
        csv_file = open(csv_file_path, mode='w', newline='', encoding='utf-8-sig')
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)
        csv_file.flush()
    except IOError as e:
        print(f"❌ 无法创建日志文件: {e}")
        return

    log_event(event_log_path, f"系统启动，初始化数据文件: {os.path.basename(csv_file_path)}")

    connection = None
    sample_count = 0
    fail_count = 0

    print(f"✅ 日志将同步保存至: {csv_file_path}")
    print(f"正在首次建立 OBD 连接 ({PORT_NAME}, {BAUD_RATE})...")

    try:
        reconnect_attempts = 0
        while True:
            try:
                connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
                if connection.is_connected():
                    log_event(event_log_path, "OBD 接口连接成功")
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
                        connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
                        if connection.is_connected():
                            log_event(event_log_path, f"OBD 连接成功恢复！(共重试 {reconnect_count} 次)")
                            fail_count = 0
                            break
                    except Exception:
                        pass
                    time.sleep(RETRY_DELAY)

            rpm = safe_query_magnitude(connection, obd.commands.RPM)
            speed = safe_query_magnitude(connection, obd.commands.SPEED)
            coolant = safe_query_magnitude(connection, obd.commands.COOLANT_TEMP)
            iat = safe_query_magnitude(connection, obd.commands.INTAKE_TEMP)
            map_kpa = safe_query_magnitude(connection, obd.commands.INTAKE_PRESSURE)
            baro_kpa = safe_query_magnitude(connection, obd.commands.BAROMETRIC_PRESSURE)
            throttle = safe_query_magnitude(connection, obd.commands.THROTTLE_POS)
            stft = safe_query_magnitude(connection, obd.commands.SHORT_FUEL_TRIM_1)
            ltft = safe_query_magnitude(connection, obd.commands.LONG_FUEL_TRIM_1)
            maf = safe_query_magnitude(connection, obd.commands.MAF)
            o2_b1s1 = safe_query_magnitude(connection, obd.commands.O2_B1S1)
            o2_b1s2 = safe_query_magnitude(connection, obd.commands.O2_B1S2)
            timing = safe_query_magnitude(connection, obd.commands.TIMING_ADVANCE)
            voltage = safe_query_magnitude(connection, obd.commands.ELM_VOLTAGE)

            load = safe_query_magnitude(connection, obd.commands.ENGINE_LOAD)
            fuel_status = safe_query_str(connection, obd.commands.FUEL_STATUS)
            amb_temp = safe_query_magnitude(connection, obd.commands.AMB_AIR_TEMP)

            tft_val, tft_display = get_gm_tft(connection)

            boost_bar = None
            if map_kpa is not None:
                ref_baro = baro_kpa if (baro_kpa is not None and baro_kpa > 0) else 101.3
                boost_bar = round((map_kpa - ref_baro) / 100.0, 2)

            row_data = [
                now_str,
                rpm if rpm is not None else "",
                speed if speed is not None else "",
                coolant if coolant is not None else "",
                iat if iat is not None else "",
                map_kpa if map_kpa is not None else "",
                baro_kpa if baro_kpa is not None else "",
                boost_bar if boost_bar is not None else "",
                throttle if throttle is not None else "",
                stft if stft is not None else "",
                ltft if ltft is not None else "",
                maf if maf is not None else "",
                o2_b1s1 if o2_b1s1 is not None else "",
                o2_b1s2 if o2_b1s2 is not None else "",
                timing if timing is not None else "",
                voltage if voltage is not None else "",
                load if load is not None else "",
                fuel_status,
                amb_temp if amb_temp is not None else "",
                tft_val if tft_val is not None else ""
            ]

            writer.writerow(row_data)
            csv_file.flush()
            sample_count += 1

            clear_screen()
            fmt = lambda v, u="": f"{v} {u}".strip() if v is not None else "N/A"

            print("==================================================================")
            print("         迈锐宝 1.5T (LFV) OBD 实时数据检测面板 (高容错版)")
            print("==================================================================")
            print(f" [时间] {now_str}  |  已采数据: {sample_count} 条")
            print(f" [日志] {os.path.basename(csv_file_path)}")
            print("------------------------------------------------------------------")
            print(" 1. 动力与工况")
            print(f"    发动机转速 (RPM)     : {fmt(rpm, 'RPM'):<15} 车速 (Speed)    : {fmt(speed, 'km/h')}")
            print(f"    引擎实时负荷 (Load)  : {fmt(load, '%'):<15} 点火提前角       : {fmt(timing, '°')}")
            print(f"    节气门开度 (Throttle): {fmt(throttle, '%'):<15} 闭/开环状态     : {fuel_status}")
            print("------------------------------------------------------------------")
            print(" 2. 进气与增压 (排查漏气/PCV/增压核心)")
            print(f"    进气歧管压力 (MAP)   : {fmt(map_kpa, 'kPa'):<15} 大气压 (BARO)   : {fmt(baro_kpa, 'kPa')}")
            print(f"    涡轮增压值 (Boost)   : {fmt(boost_bar, 'bar'):<15} 空气流量 (MAF)  : {fmt(maf, 'g/s')}")
            print("    * 提示: 怠速时 Boost 为负数属于正常真空状态; 加速时转正。")
            print("------------------------------------------------------------------")
            print(" 3. 燃油修正与氧传感器 (排查漏气/混合气偏差)")
            print(f"    短期燃油修正 (STFT)  : {fmt(stft, '%'):<15} 长期修正 (LTFT) : {fmt(ltft, '%')}")
            print(f"    前氧电压 (O2_B1S1)   : {fmt(o2_b1s1, 'V'):<15} 后氧 (O2_B1S2)   : {fmt(o2_b1s2, 'V')}")
            print("    * 提示: 怠速 STFT/LTFT 持续 > +10% 需警惕真空/PCV漏气。")
            print("------------------------------------------------------------------")
            print(" 4. 温度与系统电压")
            print(f"    冷却液温度 (ECT)     : {fmt(coolant, '°C'):<15} 进气温度 (IAT)  : {fmt(iat, '°C')}")
            print(f"    变速箱油温 (TFT 6AT) : {fmt(tft_display):<15} 环境温度 (AMB)  : {fmt(amb_temp, '°C')}")
            print(f"    系统/电瓶电压        : {fmt(voltage, 'V')}")
            print("==================================================================")
            print(" 【退出方式】按键盘 Ctrl+C 停止检测并保存日志。")

            time.sleep(REFRESH_INTERVAL)

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


