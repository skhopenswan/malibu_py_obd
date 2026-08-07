import obd
import time
import os
from obd.decoders import raw_string

# ================= 配置区域 =================
# 将 COM4 替换为你实际的 ELM327 端口号
PORT_NAME = "COM4" 
BAUD_RATE = 38400
# ============================================

# 注册通用汽车(GM)专用的获取变速箱油温(TFT)的自定义指令
# 发送 221940，返回格式通常为 62 19 40 XX，其中 XX 转为十进制后减去 40 就是摄氏度
gm_tft_cmd = obd.OBDCommand(
    "GM_TFT", 
    "Transmission Fluid Temp", 
    b"221940", 
    0, 
    raw_string, 
    obd.ECU.ALL, 
    fast=False # 针对模式 22 自定义指令，建议关闭 fast 优化以保证兼容性
)

def clear_screen():
    """清屏函数，用于实现仪表盘刷新效果"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_gm_tft(connection):
    """解析通用的变速箱油温"""
    # 对于自定义指令，必须加上 force=True，否则库会认为该指令“未受支持”而直接跳过
    res = connection.query(gm_tft_cmd, force=True)
    
    if not res.is_null():
        # 获取原始字符串，通常返回的是类似 "62 19 40 5A" 的字符串
        raw_str = str(res.value).replace(" ", "")
        # 寻找头部信息 621940
        idx = raw_str.find("621940")
        if idx != -1 and len(raw_str) >= idx + 8:
            # 提取后面的两位 16 进制数 (例如 5A)
            hex_val = raw_str[idx+6 : idx+8]
            try:
                temp = int(hex_val, 16) - 40
                return f"{temp} °C"
            except ValueError:
                pass
    return "N/A (未获取)"

def main():
    print(f"正在连接到 OBD 端口 {PORT_NAME}，请确保车辆已点火...")
    # 建立连接
    connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
    
    if not connection.is_connected():
        print("连接失败！请检查端口配置及蓝牙连接。")
        return
        
    print("连接成功！即将进入实时监控模式...")
    time.sleep(2)

    try:
        while True:
            # ================= 读取各项数据 =================
            # 1. 基础发动机数据
            rpm_res = connection.query(obd.commands.RPM)
            speed_res = connection.query(obd.commands.SPEED)
            coolant_res = connection.query(obd.commands.COOLANT_TEMP)
            
            # 2. 涡轮压力相关数据 (MAP 和 BARO 默认单位是 kPa)
            map_res = connection.query(obd.commands.INTAKE_PRESSURE)
            baro_res = connection.query(obd.commands.BAROMETRIC_PRESSURE)
            
            # 3. 变速箱油温 (自定义)
            tft_str = get_gm_tft(connection)

            # ================= 数据格式化处理 =================
            rpm = f"{int(rpm_res.value.magnitude)} RPM" if not rpm_res.is_null() else "N/A"
            speed = f"{int(speed_res.value.magnitude)} km/h" if not speed_res.is_null() else "0 km/h"
            coolant = f"{int(coolant_res.value.magnitude)} °C" if not coolant_res.is_null() else "N/A"
            
            # 计算涡轮增压压力 (MAP - 大气压)
            map_kpa = map_res.value.magnitude if not map_res.is_null() else 0
            baro_kpa = baro_res.value.magnitude if not baro_res.is_null() else 101 
            
            boost_bar = "N/A"
            if map_kpa > 0:
                # 计算公式: (进气歧管压力 - 大气压) / 100 转换为 Bar
                boost = (map_kpa - baro_kpa) / 100.0
                # 如果没踩油门，发动机处于负压（吸气）状态，显示为负值是很正常的
                boost_bar = f"{boost:.2f} Bar"

            # ================= 打印仪表盘 =================
            clear_screen()
            print("==================================================")
            print("          迈锐宝 1.5T + 6AT 实时监控面板")
            print("==================================================")
            print(f" 发动机转速 (RPM)    :  {rpm}")
            print(f" 当前车速 (Speed)    :  {speed}")
            print(f" 发动机水温 (ECT)    :  {coolant}")
            print(f" 涡轮增压值 (Boost)  :  {boost_bar}")
            print(f" 变速箱油温 (TFT)    :  {tft_str}  [Mode 22]")
            print("==================================================")
            print("【提示】怠速时涡轮压力为负数是正常现象(真空状态)。")
            print("【退出】按键盘 Ctrl+C 停止监控并断开连接。")
            
            # 刷新率：每秒刷新一次
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n已接收到退出指令。")
    finally:
        connection.close()
        print("OBD 连接已断开，安全退出！")

if __name__ == "__main__":
    main()