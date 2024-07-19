import paho.mqtt.client as mqtt
import json
import time
import os
from dotenv import load_dotenv
import subprocess
import platform
import requests
import random
from datetime import datetime, timedelta
from pyubx2 import UBXMessage
from serial import Serial, SerialException  # <-- Korrigierter Import
# Plattform-spezifische Imports
if platform.system() == "Linux":
    try:
        import gpsd
    except ImportError:
        gpsd = None


load_dotenv(".env")  # Laden der Umgebungsvariablen

# MQTT-Einstellungen
broker_heimnetz = os.getenv("MQTT_HOST")
port_heimnetz = int(os.getenv("MQTT_PORT", 1883))
broker_lokal = os.getenv("MQTT_HOST_LOCAL")
port_lokal = int(os.getenv("MQTT_PORT_LOCAL", 1883))
topic_control = os.getenv("MQTT_TOPIC_CONTROL")
topic_gps = os.getenv("MQTT_TOPIC_GPS")
topic_status = os.getenv("MQTT_TOPIC_STATUS")
user = os.getenv("MQTT_USER")
password = os.getenv("MQTT_PASSWORD")
user_local = os.getenv("MQTT_USER_LOCAL", None)
password_local = os.getenv("MQTT_PASSWORD_LOCAL", None)

# AssistNow Offline Einstellungen
assist_now_token = os.getenv("ASSIST_NOW_TOKEN")
assist_now_offline_url = "https://offline-live1.services.u-blox.com/GetOfflineData.ashx"
assist_now_enabled = os.getenv("ASSIST_NOW_ENABLED", "False").lower() == "true"
assist_now_path = "/dev/ttyACM0"  # Pfad zur seriellen Schnittstelle

# Grundstücksgrenzen (als Arrays für einfachere Überprüfung)
lat_bounds = [46.811819, 46.812107]
lon_bounds = [7.132838, 7.133173]

# Flags und Variablen
is_recording = False
is_fake_gps = False
gps_data_buffer = ""
test_mode = os.getenv("TEST_MODE", "False").lower() == "true"

# Verbindungsstatus
is_wifi_connected = True  # Auf dem Raspberry Pi immer verbunden
is_mqtt_connected = False

# GPS-Einstellungen
if platform.system() == "Linux":
    if gpsd is not None:  # Verbindung zum GPSD-Daemon herstellen, falls verfügbar
        gpsd.connect()
else:
    serial_port = os.getenv("SERIAL_PORT", 'COM3')
    ser = serial.Serial(serial_port, 38400)  # Windows: COM-Port anpassen (ggf. anpassen!)

last_assist_now_update = datetime.now() - timedelta(days=1)  # Initialisierung für sofortigen Download
# Funktion zum Senden von MQTT-Nachrichten mit Fehlerbehandlung
def send_mqtt_message(topic, payload):
    if is_mqtt_connected:  # Überprüfen, ob der Client verbunden ist
        try:
            mqtt_client.publish(topic, payload)
            print(f"MQTT-Nachricht gesendet an {topic}: {payload}")
        except Exception as e:
            print(f"Fehler beim Senden der MQTT-Nachricht: {e}")
    else:
        print("MQTT nicht verbunden. Nachricht nicht gesendet.")

# Funktion zum Abrufen von GPS-Daten (plattformspezifisch)
# Funktion zum Abrufen von GPS-Daten (plattformspezifisch)
# Funktion zum Abrufen von GPS-Daten (plattformspezifisch)
def get_gps_data():
    global is_fake_gps
    if is_fake_gps:  # Fake-GPS-Modus
        latitude = random.uniform(lat_bounds[0], lat_bounds[1])
        longitude = random.uniform(lon_bounds[0], lon_bounds[1])
        timestamp = time.time()
        satellites = random.randint(4, 12)  # Zufällige Anzahl Satelliten
        mode = 3  # 3D-Fix im Fake-GPS-Modus
        return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites, "mode": mode}

    elif platform.system() == "Linux":  # Linux (Raspberry Pi)
        if gpsd is not None:  # GPSD verwenden, falls verfügbar
            try:
                packet = gpsd.get_current()
                if packet.mode >= 2 and packet.sats >= 4:
                    return {
                        "lat": packet.lat,
                        "lon": packet.lon,
                        "timestamp": packet.time,
                        "satellites": packet.sats,
                        "mode": packet.mode
                    }
                else:
                    raise ValueError("Keine gültigen GPS-Daten oder zu wenige Satelliten.")
            except (gpsd.NoFixError, ValueError, AttributeError) as e:
                print(f"Fehler beim Abrufen der GPS-Daten (GPSD): {e}")

        # Direkte Kommunikation mit dem GPS-Modul, falls GPSD nicht verfügbar oder Fehler auftritt
        try:
            with Serial("/dev/ttyACM0", 9600, timeout=1) as ser:
                while True:
                    line = ser.readline().decode().strip()
                    if line.startswith("$GPGGA"):
                        parts = line.split(",")
                        if parts[6] != '0' and int(parts[7]) >= 4:
                            latitude = float(parts[2][:2]) + float(parts[2][2:]) / 60
                            longitude = float(parts[4][:3]) + float(parts[4][3:]) / 60
                            if parts[5] == 'W':
                                longitude = -longitude
                            return {
                                "lat": latitude,
                                "lon": longitude,
                                "timestamp": time.time(),
                                "satellites": int(parts[7]),
                                "mode": int(parts[6])
                            }
        except (SerialException, ValueError) as e:
            print(f"Fehler beim Abrufen der GPS-Daten (seriell): {e}")

    else:  # Windows
        try:
            with serial.Serial(serial_port, 38400) as ser:
                while True:
                    line = ser.readline().decode().strip()
                    if line.startswith("$GPGGA"):
                        parts = line.split(",")
                        if parts[6] != '0' and int(parts[7]) >= 4:
                            latitude = float(parts[2][:2]) + float(parts[2][2:]) / 60
                            longitude = float(parts[4][:3]) + float(parts[4][3:]) / 60
                            if parts[5] == 'W':
                                longitude = -longitude
                            return {
                                "lat": latitude,
                                "lon": longitude,
                                "timestamp": time.time(),
                                "satellites": int(parts[7]),
                                "mode": int(parts[6])
                            }
        except (SerialException, ValueError) as e:
            print(f"Fehler beim Abrufen der GPS-Daten (Windows): {e}")

    return None  # Keine gültigen GPS-Daten gefunden

# Funktion zum Überprüfen, ob Koordinaten innerhalb der Grundstücksgrenzen liegen
def is_inside_boundaries(lat, lon):
    return (lat >= lat_bounds[0] and lat <= lat_bounds[1] and lon >= lon_bounds[0] and lon <= lon_bounds[1])
# Funktion zum Herunterladen von AssistNow Offline-Daten
def download_assist_now_data():
    try:
        headers = {"useragent": "Thingstream Client"}
        params = {
            "token": assist_now_token,
            "gnss": "gps",
            "alm": "gps",
            "days": 7,
            "resolution": 1
        }
        response = requests.get(assist_now_offline_url, headers=headers, params=params)
        response.raise_for_status()  # Fehler auslösen, wenn der Download fehlschlägt
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
        return None  # Rückgabewert None bei Fehler

# Funktion zum Senden von AssistNow Offline-Daten an das GPS-Modul
def send_assist_now_data(data):
    if platform.system() == "Linux":
        try:
            # GPSD stoppen (falls es läuft)
            subprocess.run(["sudo", "killall", "gpsd"])

            # GPSD mit exklusivem Zugriff starten
            subprocess.Popen(["sudo", "gpsd", "-n", "-G", "/dev/ttyACM0"])
            time.sleep(2)  # Wartezeit, damit GPSD starten kann

            # AssistNow-Daten senden
            with open("/dev/ttyACM0", "wb") as f:
                f.write(data)

            print("AssistNow Offline-Daten erfolgreich gesendet.")

            # GPSD wieder mit der seriellen Schnittstelle verbinden
            subprocess.run(["sudo", "gpsctl", "/dev/ttyACM0"])
            time.sleep(2)  # Wartezeit, damit GPSD sich verbinden kann
        except Exception as e:
            print(f"Fehler beim Senden der AssistNow Offline-Daten (Linux): {e}")
    else:  # Windows
        try:
            serial_port = os.getenv("SERIAL_PORT", 'COM3')  # COM-Port anpassen
            with serial.Serial(serial_port, 38400) as ser:  # Windows: COM-Port anpassen (ggf. anpassen!)
                ser.write(data)  # UBX-Daten direkt senden
            print("AssistNow Offline-Daten erfolgreich gesendet (Windows).")
        except Exception as e:
            print(f"Fehler beim Senden der AssistNow Offline-Daten (Windows): {e}")

# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    global is_mqtt_connected
    if rc == 0:
        is_mqtt_connected = True
        print(f"Verbunden mit MQTT Broker: {'lokal' if test_mode else 'Heimnetz'}")
        client.subscribe(topic_control)
    else:
        print(f"MQTT-Verbindung fehlgeschlagen (Code: {rc})")

def on_message(client, userdata, msg):
    global is_recording, is_fake_gps, gps_data_buffer
    try:
        if msg.topic == topic_control:
            payload = msg.payload.decode()
            if payload == "start":
                is_recording = True
                gps_data_buffer = ""  # Puffer leeren beim Start
                send_mqtt_message(topic_status, "recording started")
            elif payload == "stop" and is_recording:
                is_recording = False
                # Daten in kleinere Pakete aufteilen und senden
                lines = gps_data_buffer.splitlines()
                for i in range(0, len(lines), 100):  # 100 Zeilen pro Paket
                    packet = '\n'.join(lines[i:i+100])
                    send_mqtt_message(topic_gps, packet)
                    time.sleep(0.1)  # Kurze Verzögerung
                send_mqtt_message(topic_gps, "-1")  # Ende-Marker
                gps_data_buffer = ""  # Puffer leeren nach dem Senden
                send_mqtt_message(topic_status, "recording stopped")
            elif payload == "problem":
                gps_data = get_gps_data()
                if gps_data:
                    problem_data = f"problem,{gps_data['lat']},{gps_data['lon']}"
                    send_mqtt_message(topic_status, problem_data)
            elif payload == "fakegps_on":
                is_fake_gps = True
            elif payload == "fakegps_off":
                is_fake_gps = False
            elif payload == "shutdown":
                print("Shutdown-Befehl empfangen. Fahre Raspberry Pi herunter...")
                subprocess.call(["sudo", "shutdown", "-h", "now"])

    except Exception as e:
        print(f"Fehler bei der Verarbeitung der MQTT-Nachricht: {e}")
# MQTT-Client erstellen und konfigurieren
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(user, password)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Verbindung zum Broker herstellen (abhängig vom Testmodus)
if test_mode:
    broker, port = broker_lokal, port_lokal
    if user_local and password_local:
        mqtt_client.username_pw_set(user_local, password_local)  # Anmeldedaten für lokalen Broker setzen
else:
    broker, port = broker_heimnetz, port_heimnetz
    mqtt_client.username_pw_set(user, password)  # Anmeldedaten für Heimnetz-Broker setzen

try:
    mqtt_client.connect(broker, port)
    mqtt_client.loop_start()  # MQTT-Schleife in einem separaten Thread starten
except ConnectionRefusedError:
    print(f"Verbindung mit MQTT-Broker fehlgeschlagen ({broker}:{port}).")

# Hauptschleife
while True:
    if is_recording:
        gps_data = get_gps_data()
        if gps_data:  # Nur wenn gültige GPS-Daten vorhanden sind
            # Daten im Puffer sammeln (immer, auch im Testmodus)
            gps_data_buffer += f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}\n"
        else:
            print("Keine gültigen GPS-Daten.")

    # Auch wenn keine Aufzeichnung läuft, Status-Updates senden
    gps_data = get_gps_data()
    if gps_data:
        status_message = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']},{gps_data['mode']}"  # Statusmeldung erstellen
        if is_mqtt_connected:  # Nur senden, wenn MQTT verbunden ist
            send_mqtt_message(topic_status, status_message)  # Statusmeldung senden
        else:
            print("MQTT nicht verbunden. Statusmeldung nicht gesendet.")
    else:
        print("Keine gültigen GPS-Daten.")

    # AssistNow Offline-Daten aktualisieren (einmal täglich)
    if assist_now_enabled and datetime.now() - last_assist_now_update >= timedelta(days=1):
        try:
            data = download_assist_now_data()
            if data is not None:
                send_assist_now_data(data)
                last_assist_now_update = datetime.now()
            else:
                print("AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in 24 Stunden.")
        except Exception as e:
            print(f"Fehler beim Aktualisieren der AssistNow-Daten: {e}")
            print("Die GPS-Erfassung wird fortgesetzt.")

    time.sleep(2)  # Speicherintervall von 2 Sekunden
