import obd

# 开启 DEBUG 模式，能看到底层发送的十六进制指令，帮你判断卡在哪一步
obd.logger.setLevel(obd.logging.DEBUG)

# ⚠️ 将此处的 COM4 替换为你在第四步中查找到的端口号！
# 比如 macOS/Linux 可能是 "/dev/ttyUSB0" 或 "/dev/rfcomm0"
port_name = "COM4"

print(f"尝试连接端口 {port_name} ...")
connection = obd.OBD(port_name, baudrate=38400) # 大部分 ELM327 的波特率是 38400

if connection.is_connected():
    print(">>> 恭喜！OBD 适配器连接成功！<<<")

    # 尝试读取车辆当前的电瓶电压（这个数据不需要启动发动机就能读）
    voltage = connection.query(obd.commands.ELM_VOLTAGE)
    print(f"当前车辆电压: {voltage.value}")
else:
    print(">>> 连接失败，请检查端口、蓝牙配对或车辆是否通电。<<<")