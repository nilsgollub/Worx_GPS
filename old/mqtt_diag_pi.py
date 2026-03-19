import socket
import time
import subprocess
import paho.mqtt.client as mqtt
import os
import uuid
from dotenv import load_dotenv

# Lade Konfiguration
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "192.168.1.155")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASSWORD")

print("=== MQTT DIAGNOSE TOOL V2 ===")
print(f"Ziel: {MQTT_HOST}:{MQTT_PORT}")
print(f"Benutzer: {MQTT_USER}")
print(f"Client ID: diag_{uuid.uuid4().hex[:6]}")

def check_ping():
    print(f"\n1. Ping Test zu {MQTT_HOST}...")
    try:
        # -c 4 für 4 Versuche
        output = subprocess.check_output(["ping", "-c", "4", "-W", "2", MQTT_HOST], stderr=subprocess.STDOUT, text=True)
        print(output)
        return True
    except Exception as e:
        print(f"❌ Ping fehlgeschlagen (Kabel/WLAN unterbrochen?): {e}")
        return False

def check_tcp():
    print(f"\n2. TCP Port Test ({MQTT_PORT})...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((MQTT_HOST, MQTT_PORT))
        print(f"✅ TCP Verbindung zu {MQTT_HOST}:{MQTT_PORT} erfolgreich! (Port ist offen)")
        s.close()
        return True
    except Exception as e:
        print(f"❌ TCP Verbindung zu Port {MQTT_PORT} fehlgeschlagen!")
        print(f"   Hinweis: Läuft der Mosquitto Dienst auf {MQTT_HOST}?")
        print(f"   Fehler: {e}")
        return False

def check_wifi_power():
    print("\n3. WLAN Power Management Status...")
    try:
        output = subprocess.check_output(["iwconfig", "wlan0"], stderr=subprocess.STDOUT, text=True)
        if "Power Management:on" in output:
            print("⚠️  Power Management ist AN. Dies kann Lags verursachen!")
            print("   Tipp: 'sudo iw dev wlan0 set power_save off' ausführen.")
        else:
            print("✅ Power Management ist AUS.")
        
        for line in output.split('\n'):
            if "Signal level" in line:
                print(f"   Signalinfo: {line.strip()}")
    except:
        print("iwconfig nicht verfügbar.")

def on_log(client, userdata, level, buf):
    print(f"   [MQTT Log]: {buf}")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"\n   ✅✅ MQTT VERBINDUNG ERFOLGREICH (rc=0)!")
    else:
        errors = {
            1: "Falsche Protokollversion",
            2: "Client-ID abgelehnt",
            3: "Server nicht verfügbar",
            4: "Falscher Benutzername oder Passwort",
            5: "Nicht autorisiert"
        }
        err_msg = errors.get(rc, f"Unbekannter Fehler {rc}")
        print(f"\n   ❌ MQTT VERBINDUNGSFEHLER: {err_msg} (rc={rc})")

def check_mqtt():
    print(f"\n4. MQTT Handshake Test (Verbose)...")
    client_id = f"diag_{uuid.uuid4().hex[:6]}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv311)
    client.on_log = on_log
    client.on_connect = on_connect
    
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    try:
        print(f"   Sende CONNECT an {MQTT_HOST}...")
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=20)
        client.loop_start()
        
        connected = False
        for i in range(15):
            if client.is_connected():
                if not connected:
                    print(f"   (Verbunden in Sekunde {i})")
                connected = True
                client.publish("worx/test/diag", f"Diagnose Lauf V2 {time.time()}")
                time.sleep(1)
            else:
                print(f"   ... warte auf CONNACK (Sekunde {i})")
                time.sleep(1)
        
        if not connected:
            print("\n   ❌ Timeout: Keine Antwort vom Broker (CONNACK) erhalten.")
            print("   Mögliche Ursachen:")
            print("   - Falsches Passwort (manche Broker antworten dann gar nicht)")
            print("   - Firewall auf dem Home Assistant Host blockiert 1883")
            print("   - Client-ID-Konflikt oder IP-Sperre am Broker")
        
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"❌ Schwerer Fehler beim Handshake: {e}")

if __name__ == "__main__":
    check_ping()
    check_tcp()
    check_wifi_power()
    check_mqtt()
    print("\n=== DIAGNOSE BEENDET ===")
