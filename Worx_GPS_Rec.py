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

# Plattform-spezifischer Import für serielle Kommunikation
import serial

# Import für NMEA-Parsing
import pynmea2

from pyubx2 import UBXMessage
from pyubx2.ubxtypes_core import SET

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

# GPS-Einstellungen und Verbindung
serial_port = os.getenv("SERIAL_PORT", '/dev/ttyACM0')  # Linux: Pfad anpassen, Windows: COM-Port anpassen
baudrate = int(os.getenv("BAUDRATE", 9600))  # Baudrate anpassen, falls erforderlich
ser_gps = serial.Serial(serial_port, baudrate, timeout=1)  # Timeout hinzufügen, um Endlosschleifen zu vermeiden

# Funktion zum Konfigurieren des GPS-Moduls, um NMEA-Nachrichten zu senden (falls erforderlich)
def configure_gps_module():
    # Überprüfen, ob das Modul bereits NMEA-Nachrichten sendet (optional)
    # ...

    # Wenn nicht, sende UBX-CFG-PRT-Nachricht, um NMEA-Ausgabe zu aktivieren
    # ...

    print("GPS-Modul konfiguriert, um NMEA-Nachrichten zu senden.")

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

# Funktion zum Abrufen von GPS-Daten (NMEA)
def get_gps_data():
    global is_fake_gps
    if is_fake_gps:  # Fake-GPS-Modus
        latitude = random.uniform(lat_bounds[0], lat_bounds[1])
        longitude = random.uniform(lon_bounds[0], lon_bounds[1])
        timestamp = time.time()
        satellites = random.randint(4, 12)  # Zufällige Anzahl Satelliten
        return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites}

    else:  # Linux oder Windows (NMEA-Kommunikation)
        try:
            line = ser_gps.readline().decode('latin-1').strip()
            if line.startswith('$GPGGA'):  # GGA-Nachricht enthält Positionsdaten
                msg = pynmea2.parse(line)
                if msg.gps_qual > 0:  # GPS-Fix vorhanden
                    latitude = msg.latitude
                    longitude = msg.longitude
                    timestamp = msg.timestamp
                    satellites = msg.num_sats
                    return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites}
                else:
                    raise ValueError("Keine gültigen GPS-Daten.")
            else:
                return None  # Andere NMEA-Nachrichten ignorieren

        except (serial.SerialException, ValueError, pynmea2.ParseError) as e:
            print(f"Fehler beim Abrufen der GPS-Daten: {e}")
            # send_mqtt_message(topic_status, "error_gps")
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
        if e.response is not None:
            print(f"Statuscode: {e.response.status_code}")  # Statuscode ausgeben
            print(f"Antworttext: {e.response.text}")        # Antworttext ausgeben
            print(f"Header: {e.response.headers}")          # Header ausgeben
        return None  # Rückgabewert None bei Fehler

# Funktion zum Senden von AssistNow Offline-Daten an das GPS-Modul
def send_assist_now_data(data):
    if platform.system() == "Linux":
        try:
            with open("/dev/ttyACM0", "wb") as f:  # Pfad zur seriellen Schnittstelle anpassen
                f.write(data)  # UBX-Daten direkt senden
                print("AssistNow Offline-Daten erfolgreich gesendet.")
        except Exception as e:
            print(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")
    else:
        try:
            ser.write(data)  # UBX-Daten direkt senden
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
last_assist_now_update = datetime.now() - timedelta(days=1)  # Initialisierung für sofortigen Download
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
        status_message = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"  # Statusmeldung erstellen (ohne mode)
        if is_mqtt_connected:  # Nur senden, wenn MQTT verbunden ist
            send_mqtt_message(topic_status, status_message)  # Statusmeldung senden
        else:
            print("MQTT nicht verbunden. Statusmeldung nicht gesendet.")
    else:
        print("Keine gültigen GPS-Daten.")

    # AssistNow Offline-Daten aktualisieren (einmal täglich)
    if assist_now_enabled and datetime.now() - last_assist_now_update >= timedelta(days=1):
        data = download_assist_now_data()
        if data is not None:
            send_assist_now_data(data)
            last_assist_now_update = datetime.now()
        else:
            print("AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in 2 Sekunden.")
            time.sleep(2) # Warte 2 Sekunden bis zum nächsten Versuch
            continue # Springe zum nächsten Schleifendurchlauf

    time.sleep(2)  # Speicherintervall von 2 Sekunden