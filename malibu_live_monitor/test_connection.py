#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OBD 端口连通性自检脚本
用于快速测试电脑与雪佛兰迈锐宝 OBD 设备 (ELM327 USB/蓝牙) 的连接。
"""

import sys
import obd

# ==================== 配置区 ====================
PORT_NAME = "COM4"      # OBD 串口号
BAUD_RATE = 38400       # 常用波特率 38400 / 115200
# ================================================

def main():
    print("=" * 60)
    print("          雪佛兰迈锐宝 OBD-II 端口连通性检测器")
    print("=" * 60)
    print(f"尝试连接端口: {PORT_NAME} (波特率: {BAUD_RATE})...")
    
    try:
        connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
    except Exception as e:
        print(f"❌ 连接发生异常: {e}")
        sys.exit(1)

    if connection.is_connected():
        print("✅ 恭喜！OBD 适配器连接成功！")
        print(f"  - 协议: {connection.protocol_name()}")
        print(f"  - 适配器版本: {connection.query(obd.commands.ELM_VERSION)}")
        
        volt = connection.query(obd.commands.ELM_VOLTAGE)
        print(f"  - 当前测得电压: {volt.value if not volt.is_null() else '未知'}")
        
        rpm = connection.query(obd.commands.RPM)
        if not rpm.is_null():
            print(f"  - 当前发动机转速: {rpm.value}")
        else:
            print("  - 转速数据未返回 (可能车辆未开启点火开关/钥匙放ON档/未通电)")
            
        connection.close()
        print("\n检测完毕，连接已正常关闭。")
    else:
        print("❌ 连接失败！请排查以下原因：")
        print("  1. COM 端口号是否正确？（可在设备管理器中确认）")
        print("  2. OBD USB 线缆/蓝牙卡拉是否已被其他软件占用（如串口助手/其他 Python 脚本）？")
        print("  3. 车辆钥匙是否已开启至 ON 档或已启动点火？")
        print("  4. 波特率是否匹配（通常 USB 为 38400 或 115200）？")

if __name__ == "__main__":
    main()
