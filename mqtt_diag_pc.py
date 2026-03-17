import socket
import time
import paho.mqtt.client as mqtt
import os
import uuid
from dotenv import load_dotenv

# Lade Konfiguration
print(f"CWD: {os.getcwd()}")
load_dotenv()
print(f"MQTT_HOST from env: {os.getenv('MQTT_HOST')}")

MQTT_HOST = os.getenv("MQTT_HOST", "192.168.1.155")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASSWORD")

print("=== MQTT DIAGNOSE TOOL PC ===")
print(f"Ziel: {MQTT_HOST}:{MQTT_PORT}")
print(f"Benutzer: {MQTT_USER}")

def on_log(client, userdata, level, buf):
    print(f"   [MQTT Log]: {buf}")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"\n   ✅ MQTT VERBINDUNG ERFOLGREICH (rc=0)!")
    else:
        print(f"\n   ❌ MQTT VERBINDUNGSFEHLER: rc={rc}")

def check():
    client_id = f"diag_pc_{uuid.uuid4().hex[:6]}"
    # Teste v3.1.1 (wie in der App jetzt eingestellt)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv311)
    client.on_log = on_log
    client.on_connect = on_connect
    
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    try:
        print(f"   Sende CONNECT an {MQTT_HOST}...")
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        time.sleep(5)
        if client.is_connected():
            print("   Status: Verbunden")
        else:
            print("   Status: NICHT verbunden")
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"❌ Fehler: {e}")

if __name__ == "__main__":
    check()
