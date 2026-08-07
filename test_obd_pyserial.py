import serial
import time

PORT = "COM4"
BAUD = 38400

ser = serial.Serial(PORT, BAUD, timeout=2)

time.sleep(3)

def send(cmd, delay=1.5):

    print(f"\n>>> {cmd}")

    ser.reset_input_buffer()

    ser.write((cmd + "\r").encode())

    time.sleep(delay)

    data = ser.read_all()

    try:
        text = data.decode(errors='ignore')
    except:
        text = str(data)

    print(repr(text))

    return text

send("ATZ", 3)

send("ATE0")
send("ATL0")
send("ATS0")
send("ATH1")

send("ATI")

send("ATSP6")

send("0100", 2)

send("0902", 2)

send("22F190", 2)
send("22F187", 2)
send("22F111", 2)
send("22A6B2", 2)
send("22A6B3", 2)
send("221940", 2)