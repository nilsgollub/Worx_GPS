import paho.mqtt.client as mqtt
import json
import time
import os
from dotenv import load_dotenv
import subprocess
import platform
import requests
from datetime import datetime, timedelta

# Plattform-spezifische Imports
if platform.system() == "Linux":
    import gpsd
else:
    import serial

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

# AssistNow Offline Einstellungen
assist_now_token = os.getenv("ASSIST_NOW_TOKEN")
assist_now_offline_url = "https://online-live1.services.u-blox.com/GetOfflineData.ashx"

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
serial_port = os.getenv("SERIAL_PORT", 'COM3')  # Serielle Schnittstelle aus .env lesen (Standard: COM3)
if platform.system() == "Linux":
    gpsd.connect()  # Verbindung zum GPSD-Daemon herstellen (Raspberry Pi)
else:
    ser = serial.Serial(serial_port, 38400)  # Windows: COM-Port anpassen (ggf. anpassen!)
# Funktion zum Senden von MQTT-Nachrichten mit Fehlerbehandlung
def send_mqtt_message(topic, payload):
    try:
        if mqtt_client.connected():
            mqtt_client.publish(topic, payload)
            print(f"MQTT-Nachricht gesendet an {topic}: {payload}")
        else:
            raise ConnectionError("MQTT nicht verbunden.")
    except ConnectionError as e:
        print(f"Fehler beim Senden der MQTT-Nachricht: {e}")

# Funktion zum Abrufen von GPS-Daten (plattformspezifisch)
def get_gps_data():
    if platform.system() == "Linux":
        try:
            packet = gpsd.get_current()
            if packet.mode >= 2:
                latitude = packet.lat
                longitude = packet.lon
                timestamp = packet.time
                satellites = packet.sats
                return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites}
            else:
                raise ValueError("Keine gültigen GPS-Daten.")
        except (gpsd.NoFixError, ValueError) as e:
            print(f"Fehler beim Abrufen der GPS-Daten (Linux): {e}")
            send_mqtt_message(topic_status, "error_gps")
            return None

    else:  # Windows
        try:
            line = ser.readline().decode().strip()
            if line.startswith("$GPGGA"):
                parts = line.split(",")
                if parts[6] != '0':  # GPS-Fix-Qualität prüfen
                    latitude = float(parts[2][:2]) + float(parts[2][2:]) / 60
                    longitude = float(parts[4][:3]) + float(parts[4][3:]) / 60
                    if parts[5] == 'W':
                        longitude = -longitude
                    timestamp = time.time()  # Kein Zeitstempel in NMEA, aktuelle Zeit verwenden
                    satellites = int(parts[7])
                    return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites}
            return None  # Keine gültigen Daten oder falsche NMEA-Nachricht
        except (serial.SerialException, ValueError) as e:
            print(f"Fehler beim Abrufen der GPS-Daten (Windows): {e}")
            send_mqtt_message(topic_status, "error_gps")
            return None

# Funktion zum Überprüfen, ob Koordinaten innerhalb der Grundstücksgrenzen liegen
def is_inside_boundaries(lat, lon):
    return (lat >= lat_bounds[0] and lat <= lat_bounds[1] and lon >= lon_bounds[0] and lon <= lon_bounds[1])

# Funktion zum Herunterladen von AssistNow Offline-Daten
def download_assist_now_data():
    try:
        headers = {"useragent": "Thingstream Client"}
        params = {
            "token": assist_now_token,
            "gnss": "gps,glo",  # GPS und GLONASS Daten anfordern
            "format": "mga"     # UBX-Format anfordern
        }
        response = requests.get(assist_now_offline_url, headers=headers, params=params)
        response.raise_for_status()  # Fehler auslösen, wenn der Download fehlschlägt
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
        return None
# Funktion zum Senden von AssistNow Offline-Daten an das GPS-Modul
def send_assist_now_data(data):
    if platform.system() == "Linux":
        try:
            with open("/dev/ttyACM0", "wb") as f:  # Pfad zur seriellen Schnittstelle anpassen
                f.write(data)
            print("AssistNow Offline-Daten erfolgreich gesendet.")
        except Exception as e:
            print(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")
    else:
        try:
            ser.write(data)
            print("AssistNow Offline-Daten erfolgreich gesendet.")
        except Exception as e:
            print(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")

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
                send_mqtt_message(topic_gps, gps_data_buffer)
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
else:
    broker, port = broker_heimnetz, port_heimnetz

try:
    mqtt_client.connect(broker, port)
    mqtt_client.loop_start()  # MQTT-Schleife in einem separaten Thread starten
except ConnectionRefusedError:
    print(f"Verbindung mit MQTT-Broker fehlgeschlagen ({broker}:{port}).")

# Hauptschleife
last_assist_now_update = datetime.now() - timedelta(days=1)  # Initialisierung für sofortigen Download
while True:
    if is_recording:
        gps_data = get_gps_data()
        if gps_data and (not test_mode or is_inside_boundaries(gps_data['lat'], gps_data['lon'])):
            # Daten im Puffer sammeln (nur wenn im Testmodus oder innerhalb der Grenzen)
            gps_data_buffer += f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}\n"
        else:
            if gps_data is None:
                print("Keine gültigen GPS-Daten.")
            else:
                print("GPS-Daten außerhalb der Grundstücksgrenzen (Testmodus).")

    # AssistNow Offline-Daten aktualisieren (einmal täglich)
    if datetime.now() - last_assist_now_update >= timedelta(days=1):
        data = download_assist_now_data()
        if data:
            send_assist_now_data(data)
            last_assist_now_update = datetime.now()

    time.sleep(2)  # Speicherintervall von 2 Sekunden
