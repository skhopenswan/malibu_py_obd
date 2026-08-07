import obd
import time
import os
from obd.decoders import raw_string

PORT_NAME = "COM4"  # 记得替换为您实际的端口
BAUD_RATE = 38400

gm_tft_cmd = obd.OBDCommand("GM_TFT", "Transmission Fluid Temp", b"221940", 0, raw_string, obd.ECU.ALL, fast=False)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_gm_tft(connection):
    res = connection.query(gm_tft_cmd, force=True)
    if not res.is_null():
        raw_str = str(res.value).replace(" ", "")
        idx = raw_str.find("621940")
        if idx != -1 and len(raw_str) >= idx + 8:
            try:
                return int(raw_str[idx+6:idx+8], 16) - 40
            except ValueError:
                pass
    return None

def main():
    print("正在连接 OBD...")
    connection = obd.OBD(PORT_NAME, baudrate=BAUD_RATE, fast=False)
    if not connection.is_connected():
        print("连接失败！")
        return
    
    print("连接成功，AI 驾驶教练已上线！\n")
    time.sleep(2)

    try:
        while True:
            # 读取数据
            coolant_res = connection.query(obd.commands.COOLANT_TEMP)
            load_res = connection.query(obd.commands.ENGINE_LOAD)
            throttle_res = connection.query(obd.commands.THROTTLE_POS)
            map_res = connection.query(obd.commands.INTAKE_PRESSURE)
            rpm_res = connection.query(obd.commands.RPM)
            
            coolant = int(coolant_res.value.magnitude) if not coolant_res.is_null() else 0
            tft = get_gm_tft(connection)
            tft_val = tft if tft is not None else 0
            load = int(load_res.value.magnitude) if not load_res.is_null() else 0
            throttle = int(throttle_res.value.magnitude) if not throttle_res.is_null() else 0
            rpm = int(rpm_res.value.magnitude) if not rpm_res.is_null() else 0
            map_kpa = map_res.value.magnitude if not map_res.is_null() else 0
            
            # 计算涡轮压力 (粗略以101为标准大气压)
            boost = (map_kpa - 101) / 100.0 if map_kpa > 0 else 0.0

            # --- AI 教练逻辑判定 ---
            coach_msg = "✅ 驾驶习惯完美，保持平稳！"
            
            # 1. 冷车保护判定
            if coolant < 70 or tft_val < 40:
                if rpm > 2500 or load > 60:
                    coach_msg = "❌ 警告：冷车状态！请立刻松油门，不要暴力拉高转速！"
                else:
                    coach_msg = "ℹ️ 提示：正在热车，机油/变速箱油温偏低，请温柔驾驶。"
            
            # 2. 负荷与省油判定
            elif load > 85 and boost > 0.8:
                coach_msg = "⚠️ 提示：重负荷高增压状态！当前极度费油，除非超车请松开油门。"
            
            # 3. 变速箱过热判定
            elif tft_val > 105:
                coach_msg = "🔥 警告：变速箱油温极高！请切换手动模式低挡位，或停车散热！"

            # 4. 怠速散热判定 (假设车速基本为0，负荷低)
            elif rpm < 1000 and load < 30 and coolant >= 90:
                coach_msg = "ℹ️ 提示：正在怠速，若刚才经过激烈驾驶，请保持怠速1分钟后再熄火保护涡轮。"

            # 刷新屏幕
            clear_screen()
            print("==============================================")
            print("           迈锐宝 AI 驾驶教练面板")
            print("==============================================")
            print(f" 发动机水温   : {coolant} °C")
            print(f" 变速箱油温   : {tft_val} °C")
            print(f" 引擎实时负荷 : {load} %   (省油秘诀: 保持在40%以下)")
            print(f" 相对节气门   : {throttle} %")
            print(f" 涡轮增压压力 : {boost:.2f} Bar (正数介入，负数省油)")
            print("==============================================")
            print(f" 教练点评 : {coach_msg}")
            print("==============================================")
            print("(按 Ctrl+C 退出)")
            
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n安全退出。")
    finally:
        connection.close()

if __name__ == "__main__":
    main()