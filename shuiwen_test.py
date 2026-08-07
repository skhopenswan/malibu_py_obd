import obd
import time

# 开启 DEBUG 日志可以让你看到底层发送的 AT 指令和十六进制数据（排错时很有用）
# obd.logger.setLevel(obd.logging.DEBUG)

def main():
    print("正在尝试连接到 OBD-II 适配器...")

    # 连接 ELM327
    # 如果是 USB 或蓝牙，通常可以留空让它自动寻找端口 obd.OBD()
    # 如果自动寻找失败，请手动指定端口，例如：
    # Windows 蓝牙/USB: connection = obd.OBD("COM3")
    # Mac/Linux 蓝牙: connection = obd.OBD("/dev/rfcomm0")
    # Mac/Linux USB: connection = obd.OBD("/dev/ttyUSB0")
    connection = obd.OBD()

    if not connection.is_connected():
        print("连接失败！请检查适配器是否插好，车辆是否通电，以及端口是否正确。")
        return

    print("成功连接！正在读取 2017 款迈锐宝车辆数据...\n")

    # 定义我们要读取的指令列表
    commands_to_read =[
        obd.commands.RPM,               # 发动机转速
        obd.commands.SPEED,             # 车速
        obd.commands.COOLANT_TEMP,      # 冷却液温度
        obd.commands.INTAKE_PRESSURE,   # 进气歧管绝对压力 (MAP)
        obd.commands.THROTTLE_POS,      # 节气门位置
        obd.commands.GET_DTC            # 读取故障码
    ]

    for cmd in commands_to_read:
        # 查询数据
        response = connection.query(cmd)

        # 判断是否成功获取到数据
        if not response.is_null():
            print(f"{cmd.desc}: {response.value}")
        else:
            print(f"{cmd.desc}: 车辆未返回该数据或不支持该 PID")

    # 循环读取实时数据的示例（按 Ctrl+C 退出）
    print("\n开始实时监控转速和温度（按 Ctrl+C 结束）：")
    try:
        while True:
            rpm = connection.query(obd.commands.RPM)
            temp = connection.query(obd.commands.COOLANT_TEMP)

            # 格式化输出
            rpm_val = rpm.value.magnitude if not rpm.is_null() else 0
            temp_val = temp.value.magnitude if not temp.is_null() else 0

            print(f"\r实时转速: {rpm_val:4.0f} RPM | 冷却液温度: {temp_val} °C", end="")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n监控结束。")
    finally:
        connection.close()

if __name__ == "__main__":
    main()