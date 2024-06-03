import paho.mqtt.client as mqtt
import time
import random
import json
import logging
import math
from dotenv import load_dotenv
import os
import shapely.geometry as sg

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv("secrets.env")

# Get MQTT credentials from environment variables
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))  # Default-Port 1883
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# MQTT topics from secrets.env
CONTROL_TOPIC = os.getenv("MQTT_TOPIC_CONTROL")
GPS_TOPIC = os.getenv("MQTT_TOPIC_GPS")
STATUS_TOPIC = os.getenv("MQTT_TOPIC_STATUS")
# Rasenfläche als Polygon definieren (letztes Tupel hinzugefügt, um den Ring zu schließen)
rasenflaeche_coords = [
    (46.812099423685886, 7.13294504532412),
    (46.81207923114223, 7.133169680326546),
    (46.81205766182586, 7.13316565701307),
    (46.812054908295465, 7.1331294471917825),
    (46.81200809825755, 7.13312140056483),
    (46.812001214424996, 7.133160292595101),
    (46.811831412942134, 7.13314688155048),
    (46.811847475267406, 7.132844462487513),
    (46.811959452487436, 7.132857202980187),
    (46.811973679084794, 7.132917552682331),
    (46.81191814944163, 7.1329095060553795),
    (46.81191172452053, 7.133020817728223),
    (46.811929163590264, 7.133023499937206),
    (46.81192549220765, 7.133100613445501),
    (46.81202507837282, 7.133110001176946),
    (46.812027372982726, 7.133094578475288),
    (46.81205197798022, 7.133091556307457),
    (46.81206171583993, 7.132939570211207),
    (46.812099423685886, 7.13294504532412)  # Erstes Tupel wiederholt
]

rasenflaeche = sg.Polygon(rasenflaeche_coords)

# Startposition des Roboters
START_POSITION = (46.811967713094056, 7.133148222656783)

# Simulationsparameter
SIMULATION_DURATION = 5.0  # in seconds (Simulationsdauer)
REAL_MOWING_DURATION = 2 * 60 * 60  # 2 Stunden in Sekunden
TIME_FACTOR = REAL_MOWING_DURATION / SIMULATION_DURATION  # Faktor zur Zeitbeschleunigung
GPS_INTERVAL = 2 / TIME_FACTOR  # GPS-Intervall in Sekunden (beschleunigt)
SPEED = 4 / 3.6 * TIME_FACTOR  # Geschwindigkeit in m/s (beschleunigt)
TURN_ANGLE = 30  # Winkel für Richtungsänderungen
TURN_PROBABILITY = 0.1  # Wahrscheinlichkeit einer Richtungsänderung pro Schritt
PROBLEM_PROBABILITY = 0.1  # Wahrscheinlichkeit eines Problems pro Mähvorgang

# Typische Problemstellen
PROBLEM_POSITIONS = [
    (46.81209268539523, 7.132970447627758),
    (46.812018340074374, 7.133119310227487),
    (46.81191829497382, 7.1330321384355),
]

# GPS-Daten
gps_data = []
# Funktion zur Überprüfung, ob ein Punkt innerhalb der Rasenfläche liegt
def is_inside_rasenflaeche(lat, lon):
    return rasenflaeche.contains(sg.Point(lon, lat))

# Funktion, um eine zufällige GPS-Position innerhalb der Rasenfläche zu erzeugen
def generate_random_gps_in_rasenflaeche():
    while True:
        lat, lon = generate_random_gps()
        if is_inside_rasenflaeche(lat, lon):
            return lat, lon

# Funktion zum Senden der GPS-Daten (nur bei "stop"-Befehl)
def send_gps_data(client):
    if gps_data:  # Nur senden, wenn Daten vorhanden sind
        logging.info("Sende GPS-Daten...")
        client.publish(GPS_TOPIC, json.dumps(gps_data))

# Funktion zum Senden der Problem-Daten
def send_problem_data(client):
    lat, lon = random.choice(PROBLEM_POSITIONS)
    timestamp = int(time.time())
    payload = {"lat": lat, "lon": lon, "timestamp": timestamp, "command": "problem"}
    client.publish(STATUS_TOPIC, json.dumps(payload))
def simulate_mowing(client):
    start_time = time.time()
    lat, lon = START_POSITION  # Startposition
    direction = random.uniform(0, 360)  # Startrichtung in Grad

    # Problemfall simulieren (vor der Schleife)
    problem_occurred = random.random() < PROBLEM_PROBABILITY

    while time.time() - start_time < SIMULATION_DURATION:
        # Berechnung der neuen Position basierend auf Richtung und Geschwindigkeit
        new_lat = lat + SPEED * GPS_INTERVAL * math.cos(math.radians(direction))
        new_lon = lon + SPEED * GPS_INTERVAL * math.sin(math.radians(direction)) / math.cos(math.radians(lat))

        # Überprüfung, ob die neue Position innerhalb der Rasenfläche liegt
        if is_inside_rasenflaeche(new_lat, new_lon):
            lat, lon = new_lat, new_lon
        else:
            # Wenn die neue Position außerhalb liegt, Richtung zufällig ändern
            direction += random.uniform(90, 270)  # Zufälliger Winkel zwischen 90 und 270 Grad

        # Richtungsänderung mit bestimmter Wahrscheinlichkeit
        if random.random() < TURN_PROBABILITY:
            direction += random.uniform(-TURN_ANGLE, TURN_ANGLE)

        timestamp = int(time.time())
        gps_data.append({"lat": lat, "lon": lon, "timestamp": timestamp})
        logging.debug(f"GPS-Daten: {lat:.6f}, {lon:.6f}, {timestamp}")
        time.sleep(GPS_INTERVAL)

        # MQTT-Nachrichten verarbeiten (stop-Befehl)
        if client.want_write():
            client.loop_write()  # Nachrichten sofort senden

    # Sende Statusmeldung, wenn der Status sich ändert
    client.publish(STATUS_TOPIC, json.dumps({"status": "mowing"}))

    if problem_occurred:
        send_problem_data(client)
        time.sleep(0.1)  # Kurze Verzögerung

    # Stop-Befehl senden
    client.publish(CONTROL_TOPIC, "stop")
# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    logging.info(f"Connected with result code {rc}")
    client.subscribe(CONTROL_TOPIC)


def on_message(client, userdata, msg):
    global gps_data
    payload = msg.payload.decode()
    logging.info(f"Nachricht empfangen: {payload}")

    if payload == "start":
        gps_data = []  # Daten nur bei "start" zurücksetzen
        simulate_mowing(client)
    elif payload == "stop":
        send_gps_data(client)  # GPS-Daten senden
        send_problem_data(client)  # Problemdaten senden (falls vorhanden)
        gps_data = []  # Daten nach dem Senden zurücksetzen
    else:
        logging.warning(f"Unbekannter Befehl: {payload}")


# MQTT-Client erstellen und konfigurieren
client = mqtt.Client(client_id="", userdata=None, protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

# Fehlerbehandlung beim Verbinden mit dem MQTT-Broker
try:
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    logging.info(f"Verbunden mit MQTT-Broker: {MQTT_HOST}:{MQTT_PORT}")
except Exception as e:
    logging.error(f"Fehler beim Verbinden mit MQTT-Broker: {e}")
    exit(1)  # Beenden, wenn die Verbindung nicht hergestellt werden kann

# MQTT-Schleife starten
client.loop_forever()
