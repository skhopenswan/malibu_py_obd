import obd
import time
from obd.decoders import raw_string

# ================= 配置区域 =================
PORT_NAME = "COM4"  # 请替换为您的实际端口
BAUD_RATE = 38400
# ============================================

# 通用 Mode 22 变速箱油温指令
gm_tft_cmd = obd.OBDCommand("GM_TFT", "Transmission Fluid Temp", b"221940", 0, raw_string, obd.ECU.ALL, fast=False)

def get_gm_tft(connection):
    res = connection.query(gm_tft_cmd, force=True)
    if not res.is_null():
        raw_str = str(res.value).replace(" ", "")
        idx = raw_str.find("621940")
        if idx != -1 and len(raw_str) >= idx + 8:
            hex_val = raw_str[idx+6 : idx+8]
            try:
                temp = int(hex_val, 16) - 40
                return f"{temp} °C"
            except ValueError:
                pass
    return "未获取"

def check_dtc(connection, cmd, title):
    print(f"\n[{title}]")
    res = connection.query(cmd)
    if res.is_null() or not res.value:
        print("  ✅ 完美：未发现任何故障码")
    else:
        print(f"  ❌ 警告：发现 {len(res.value)} 个故障码！")
        for dtc in res.value:
            # dtc 通常是一个元组 (故障码, 描述)
            print(f"    - {dtc[0]}: {dtc[1]}")

def main():
    print("==================================================")
    print("      迈锐宝 1.5T 二手车深度体检程序启动")
    print("==================================================")
    print("提示：体检前，请确保车辆已点火启动，且怠速平稳。")
    
    connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
    if not connection.is_connected():
        print("连接失败！请检查端口和 OBD 设备。")
        return

    print("连接成功，正在读取车辆底层数据，请稍候...\n")
    time.sleep(2)

    # 1. 读取故障码
    # Mode 03: 已经确诊并点亮故障灯的码
    check_dtc(connection, obd.commands.GET_DTC, "已确认的发动机/变速箱故障码")
    # Mode 07: 偶发、初次检测到，但还没点亮故障灯的隐性码
    check_dtc(connection, obd.commands.GET_CURRENT_DTC, "待定/隐藏的故障码 (重点关注)")

    # 2. 读取“二手车测谎”指标：清除故障码后的行驶里程
    dist_res = connection.query(obd.commands.DISTANCE_SINCE_DTC_CLEAR)
    print("\n[二手车测谎仪]")
    if not dist_res.is_null():
        dist = int(dist_res.value.magnitude)
        print(f"  自上次清除故障码后行驶里程: {dist} 公里")
        if dist < 100:
            print("  ⚠️ 警告：该车近期刚刚清过故障码！可能是在掩盖暗病，建议多试驾几圈。")
        else:
            print("  ✅ 正常：近期未进行过清码操作，数据较真实。")
    else:
        print("  不支持读取清除故障码后里程。")

    # 3. 发动机核心健康状态 (怠速下读取)
    print("\n[发动机健康指标 (怠速状态)]")
    
    # 燃油修正
    stft_res = connection.query(obd.commands.SHORT_FUEL_TRIM_1)
    ltft_res = connection.query(obd.commands.LONG_FUEL_TRIM_1)
    
    stft = f"{stft_res.value.magnitude:.2f} %" if not stft_res.is_null() else "未获取"
    ltft = f"{ltft_res.value.magnitude:.2f} %" if not ltft_res.is_null() else "未获取"
    
    print(f"  短期燃油修正 (STFT) : {stft}")
    print(f"  长期燃油修正 (LTFT) : {ltft}")
    if not ltft_res.is_null():
        ltft_val = ltft_res.value.magnitude
        if abs(ltft_val) > 10:
            print("  ⚠️ 警告：长期燃油修正偏差过大！可能存在积碳严重、漏气、氧传感器老化或喷油嘴问题。")
        else:
            print("  ✅ 发动机燃烧状态良好。")

    # 节气门开度 (判断积碳)
    throttle_res = connection.query(obd.commands.THROTTLE_POS)
    if not throttle_res.is_null():
        throttle = throttle_res.value.magnitude
        print(f"  相对节气门开度      : {throttle:.2f} %")
        if throttle > 15: # 怠速时开度偏大，通常是因为积碳严重，电脑在自动补油
            print("  ⚠️ 提示：怠速节气门开度偏大，节气门或进气道可能需要清洗。")

    # 4. 电瓶与冷却系统
    print("\n[外围与变速箱系统]")
    volt_res = connection.query(obd.commands.ELM_VOLTAGE)
    print(f"  电瓶当前电压        : {volt_res.value if not volt_res.is_null() else '未获取'}")
    
    coolant_res = connection.query(obd.commands.COOLANT_TEMP)
    print(f"  发动机冷却液温度    : {coolant_res.value if not coolant_res.is_null() else '未获取'}")

    # 变速箱油温
    tft_str = get_gm_tft(connection)
    print(f"  通用 6AT 变速箱油温 : {tft_str}")

    print("\n==================================================")
    print("体检结束。请结合以上数据与实际路试感受进行综合判断。")
    print("==================================================")
    
    connection.close()

if __name__ == "__main__":
    main()