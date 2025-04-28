import serial
import time

port = "/dev/ttyACM0"
baud = 9600

try:
    ser = serial.Serial(port, baud, timeout=1)
    print(f"Port {port} geöffnet. Lese für 10 Sekunden...")
    start = time.time()
    while time.time() - start < 10:
        try:
            line = ser.readline()
            if line:
                print(line.decode('utf-8', errors='ignore').strip())
            else:
                print(".")  # Zeigt an, dass readline ohne Daten zurückkam
        except serial.SerialException as e:
            print(f"Fehler beim Lesen: {e}")
            break
        except Exception as e:
            print(f"Allg. Fehler: {e}")
    ser.close()
    print("Port geschlossen.")
except serial.SerialException as e:
    print(f"Fehler beim Öffnen von {port}: {e}")
except Exception as e:
    print(f"Unerwarteter Fehler: {e}")
