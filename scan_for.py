import serial
import time
import re

PORT = "COM4"
BAUD = 38400

ser = serial.Serial(PORT, BAUD, timeout=2)

time.sleep(3)

def send(cmd, delay=1.0):

    ser.reset_input_buffer()

    ser.write((cmd + "\r").encode())

    time.sleep(delay)

    data = ser.read_all().decode(errors='ignore')

    return data.strip()

def init():

    cmds = [
        "ATZ",
        "ATE0",
        "ATL0",
        "ATS0",
        "ATH1",
        "ATSP6",
        "ATAT1",
        "ATAL",
        "ATCAF0",
        "ATSH7E0",
    ]

    for c in cmds:

        r = send(c, 1.5)

        print(c, "=>", repr(r))

def parse_hex(raw):

    return re.findall(r'[0-9A-F]{2}', raw.upper())

def try_u32(payload):

    if len(payload) < 4:
        return None

    vals = [int(x,16) for x in payload[-4:]]

    return (
        (vals[0]<<24) |
        (vals[1]<<16) |
        (vals[2]<<8) |
        vals[3]
    )

# def scan(start, end):

#     for did in range(start, end + 1):

#         did_hex = f"{did:04X}"

#         try:

#             raw = send(f"22{did_hex}", 1.0)

#             if (
#                 raw == "" or
#                 "NO DATA" in raw or
#                 "7F2231" in raw
#             ):
#                 continue

#             print(f"\n===== {did_hex} =====")
#             print(raw)

#             hexs = parse_hex(raw)

#             if len(hexs) > 6:

#                 payload = hexs[4:]

#                 num = try_u32(payload)

#                 if num:

#                     print("Possible:", num)

#                     if 1000 < num < 500000:
#                         print(">>> suspicious mileage/runtime")

#             # 冷却
#             time.sleep(0.3)

#         except Exception as e:

#             print("ERROR:", e)

#             # 自动恢复
#             init()

def scan(start, end):

    for did in range(start, end + 1):

        did_hex = f"{did:04X}"

        try:

            raw = send(f"22{did_hex}", 1.0)

            print(f"\n===== {did_hex} =====")
            print(repr(raw))

            time.sleep(0.3)

        except Exception as e:

            print("ERROR:", e)

            init()

init()

# 先小范围测试
scan(0x1940, 0x1960)