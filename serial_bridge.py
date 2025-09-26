import serial
import threading
import requests

# Replace with your COM ports (check in Arduino IDE)
ENTRANCE_PORT = 'COM3'
EXIT_PORT = 'COM4'
BAUDRATE = 9600

BACKEND_URL = 'http://localhost:5000/rfid_tap'  # Replace if using Render or external IP

def listen(port, direction):
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        print(f"[{direction}] Listening on {port}...")
        while True:
            line = ser.readline().decode().strip()
            if line.startswith(direction + ":"):
                uid = line[len(direction)+1:]
                print(f"[{direction}] Detected UID: {uid}")
                payload = {
                    "uid": uid,
                    "direction": direction
                }
                try:
                    r = requests.post(BACKEND_URL, json=payload)
                    print(f"Response: {r.json()}")
                except Exception as e:
                    print("Error posting to server:", e)
    except Exception as e:
        print(f"Error opening {port}: {e}")

t1 = threading.Thread(target=listen, args=(ENTRANCE_PORT, "IN"))
t2 = threading.Thread(target=listen, args=(EXIT_PORT, "OUT"))
t1.start()
t2.start()
t1.join()
t2.join()