import socket
import time
import subprocess
import paho.mqtt.client as mqtt
import os
from dotenv import load_dotenv

# Lade Konfiguration
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "192.168.1.155")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASSWORD")

print("=== MQTT DIAGNOSE TOOL ===")
print(f"Ziel: {MQTT_HOST}:{MQTT_PORT}")
print(f"Benutzer: {MQTT_USER}")

def check_ping():
    print(f"\n1. Ping Test zu {MQTT_HOST}...")
    try:
        output = subprocess.check_output(["ping", "-c", "4", MQTT_HOST], stderr=subprocess.STDOUT, text=True)
        print(output)
        return True
    except Exception as e:
        print(f"❌ Ping fehlgeschlagen: {e}")
        return False

def check_tcp():
    print(f"\n2. TCP Port Test ({MQTT_PORT})...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((MQTT_HOST, MQTT_PORT))
        print(f"✅ TCP Verbindung zu {MQTT_HOST}:{MQTT_PORT} erfolgreich!")
        s.close()
        return True
    except Exception as e:
        print(f"❌ TCP Verbindung fehlgeschlagen: {e}")
        return False

def check_wifi():
    print("\n3. WLAN Signalstärke (iwconfig)...")
    try:
        output = subprocess.check_output(["iwconfig"], stderr=subprocess.STDOUT, text=True)
        print(output)
    except:
        print("iwconfig nicht verfügbar.")

def on_log(client, userdata, level, buf):
    print(f"   [Paho Log]: {buf}")

def check_mqtt():
    print(f"\n4. MQTT Handshake Test (Verbose)...")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
    client.on_log = on_log
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    try:
        print("   Verbinde...")
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=10) # Kurzes Keepalive für schnellen Test
        client.loop_start()
        
        for i in range(15):
            if client.is_connected():
                print(f"   ✅ MQTT Verbunden! (Versuch {i})")
                client.publish("worx/test/diag", f"Diagnose Lauf {time.time()}")
                time.sleep(2)
            else:
                print(f"   ... warte auf Verbindung (Sekunde {i})")
                time.sleep(1)
        
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"❌ MQTT Fehler: {e}")

if __name__ == "__main__":
    check_ping()
    check_tcp()
    check_wifi()
    check_mqtt()
    print("\n=== DIAGNOSE BEENDET ===")
