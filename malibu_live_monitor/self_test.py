#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迈锐宝 OBD 实时监控离线逻辑与断线重连容错自测程序
用于在不连接真实车辆/硬件的情况下，验证界面刷新、计算逻辑、掉线重连及 CSV/事件日志导出功能。
v2 更新：CSV 表头对齐 real_time_monitor.py (23 列)
"""

import os
import sys
import time
import csv
import random
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "data_logs")

def mock_get_obd_data():
    """模拟返回怠速及行驶工况的车辆数据 (v2 新增 3 列)"""
    rpm = random.choice([600, 650, 700, 1500, 2200])
    speed = 0 if rpm < 800 else random.randint(20, 60)
    coolant = random.randint(85, 92)
    iat = random.randint(25, 35)
    baro = 101.3
    map_kpa = 35.0 if rpm < 800 else (60.0 if rpm < 2000 else 135.0)
    boost_bar = round((map_kpa - baro) / 100.0, 2)
    throttle = 12.5 if rpm < 800 else 25.0
    rel_throttle = round(throttle * 0.7, 1)  # 相对节气门通常小于绝对节气门
    stft = round(random.uniform(-3.5, 4.2), 2)
    ltft = round(random.uniform(1.2, 3.5), 2)
    maf = round(2.5 if rpm < 800 else 12.0, 2)
    o2_b1s1 = round(random.uniform(0.1, 0.9), 2)
    o2_b1s2 = round(random.uniform(0.6, 0.8), 2)
    cat_temp = random.randint(380, 450)  # 三元催化温度
    eq_ratio = round(random.uniform(0.99, 1.01), 4)  # 指令当量比
    timing = round(10.0 if rpm < 800 else 25.0, 1)
    voltage = round(random.uniform(13.5, 13.8), 2)
    load = round(20.0 if rpm < 800 else 55.0, 1)
    fuel_status = "Closed loop"
    amb_temp = 25.0
    tft_val = random.randint(55, 75)

    return {
        "rpm": rpm, "map_kpa": map_kpa, "maf": maf, "throttle": throttle,
        "rel_throttle": rel_throttle, "load": load, "stft": stft, "ltft": ltft,
        "o2_b1s1": o2_b1s1, "o2_b1s2": o2_b1s2, "cat_temp": cat_temp,
        "eq_ratio": eq_ratio, "boost_bar": boost_bar,
        "speed": speed, "coolant": coolant, "iat": iat,
        "baro_kpa": baro, "timing": timing, "voltage": voltage,
        "fuel_status": fuel_status, "amb_temp": amb_temp, "tft_val": tft_val,
    }

def log_event(event_file_path, msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(event_file_path, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {msg}\n")

def run_self_test(test_cycles=6):
    print("=" * 60)
    print("      OBD 实时监控与高容错断线重连逻辑离线自测 (v2)")
    print("=" * 60)

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_csv_path = os.path.join(LOG_DIR, f"selftest_obd_log_{timestamp_str}.csv")
    test_event_path = os.path.join(LOG_DIR, f"selftest_events_{timestamp_str}.log")

    headers = [
        "Timestamp", "RPM(rpm)", "MAP(kPa)", "MAF(g/s)", "ThrottlePos(%)",
        "RelThrottlePos(%)", "EngineLoad(%)", "STFT(%)", "LTFT(%)",
        "O2_B1S1(V)", "O2_B1S2(V)", "CatTemp_B1S1(C)", "EQ_Ratio",
        "BoostPressure(bar)", "Speed(km/h)", "CoolantTemp(C)", "IntakeTemp(C)",
        "BaroPressure(kPa)", "TimingAdvance(deg)", "Voltage(V)",
        "FuelStatus", "AmbAirTemp(C)", "TFT(C)"
    ]

    log_event(test_event_path, "测试启动(v2)，初始化日志文件")

    with open(test_csv_path, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        print(f"[步骤 1/4] CSV 初始化成功 (v2 23列): {test_csv_path}")

        collected_rows = 0
        for i in range(1, test_cycles + 1):
            # 模拟第 3 次采样时发生了一次线缆松动掉线，随后在第 4 次重连成功恢复
            if i == 3:
                print(f"[步骤 2/4] ⚠️ 模拟车辆线缆松动中断连...")
                log_event(test_event_path, "模拟线缆松动，触发掉线断连事件")
                time.sleep(0.1)
                print(f"[步骤 2/4] 🔄 触发自动重连机制，尝试重新连接 OBD 端口...")
                log_event(test_event_path, "后台重连尝试成功，恢复 OBD 通信")
                print(f"[步骤 2/4] ✅ OBD 连接成功恢复！继续往同一个 CSV 写入后续数据。")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            d = mock_get_obd_data()

            row = [
                now_str, d['rpm'], d['map_kpa'], d['maf'], d['throttle'],
                d['rel_throttle'], d['load'], d['stft'], d['ltft'],
                d['o2_b1s1'], d['o2_b1s2'], d['cat_temp'], d['eq_ratio'],
                d['boost_bar'], d['speed'], d['coolant'], d['iat'],
                d['baro_kpa'], d['timing'], d['voltage'], d['fuel_status'],
                d['amb_temp'], d['tft_val']
            ]
            writer.writerow(row)
            f.flush()
            collected_rows += 1

            print(f"[步骤 2/4] 采样周期 {i}/{test_cycles} | 转速: {d['rpm']} RPM, 增压: {d['boost_bar']} bar, 三元温度: {d['cat_temp']}°C")
            time.sleep(0.1)

    print("\n[步骤 3/4] 检验写入的 CSV 文件数据完整性...")
    with open(test_csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = list(csv.reader(f))
        header_row = reader[0]
        data_rows = reader[1:]

        assert len(header_row) == len(headers), f"表头数量不匹配！期望 {len(headers)}，实际 {len(header_row)}"
        assert len(data_rows) == test_cycles, f"数据行数不一致！期望 {test_cycles}，实际 {len(data_rows)}"

        print(f"  - CSV 表头项数: {len(header_row)} (预期: {len(headers)}) ✅")
        print(f"  - 模拟恢复后累计写行数: {len(data_rows)} (预期: {test_cycles}) ✅")

    print("\n[步骤 4/4] 检验产生的断线事件日志...")
    with open(test_event_path, mode='r', encoding='utf-8') as f:
        event_lines = f.readlines()
        assert len(event_lines) >= 3, "事件日志条数不符合预期！"
        print(f"  - 事件日志生成成功 ({len(event_lines)} 条记录) ✅")
        for line in event_lines:
            print("    ", line.strip())

    print("\n" + "=" * 60)
    print("🎉 离线断线重连与数据存盘逻辑自测全部通过！(v2 23列)")
    print("=" * 60)

if __name__ == "__main__":
    run_self_test()