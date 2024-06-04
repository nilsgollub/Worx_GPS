import paho.mqtt.client as mqtt
import time
import random
import json
import logging
import math
from dotenv import load_dotenv
import os

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

# Grundstücksgrenzen
BOUNDS = [
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
    (46.81206171583993, 7.132939570211207)
]

# Startposition des Roboters
START_POSITION = (46.811967713094056, 7.133148222656783)

# Problemstellen
PROBLEM_AREAS = [
    (46.81209268539523, 7.132970447627758),
    (46.812018340074374, 7.133119310227487),
    (46.81191829497382, 7.1330321384355)
]

# Simulationsparameter
SIMULATION_DURATION = 5.0  # in seconds
TOTAL_MOWING_DURATION = 7200  # in seconds (2 hours)
GPS_INTERVAL = 2  # in seconds
MOWING_SPEED = 0.0011  # roughly 4 km/h in degrees per second
TURN_PROBABILITY = 0.1  # probability of turning due to an obstacle

# GPS-Daten
gps_data = []

# Funktion, um zu überprüfen, ob ein Punkt innerhalb der Grenzen liegt
def is_inside_boundaries(lat, lon):
    n = len(BOUNDS)
    inside = False
    p1x, p1y = BOUNDS[0]
    for i in range(n + 1):
        p2x, p2y = BOUNDS[i % n]
        if lon > min(p1y, p2y):
            if lon <= max(p1y, p2y):
                if lat <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lon - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lat <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# Funktion, um eine zufällige Problemposition zu generieren
def generate_problem_position():
    if random.random() < 0.7:  # 70% Wahrscheinlichkeit, dass ein Problem an einer typischen Stelle auftritt
        return random.choice(PROBLEM_AREAS)
    else:
        return generate_random_gps()

# Funktion, um eine zufällige Position innerhalb der Grenzen zu generieren
def generate_random_gps():
    while True:
        lat = random.uniform(min(lat for lat, lon in BOUNDS), max(lat for lat, lon in BOUNDS))
        lon = random.uniform(min(lon for lat, lon in BOUNDS), max(lon for lat, lon in BOUNDS))
        if is_inside_boundaries(lat, lon):
            return lat, lon

# Funktion zum Senden der GPS-Daten (nur bei "stop"-Befehl)
def send_gps_data(client):
    if gps_data:  # Nur senden, wenn Daten vorhanden sind
        logging.info("Sende GPS-Daten...")
        client.publish(GPS_TOPIC, json.dumps(gps_data))

# Funktion zum Senden der Problem-Daten
def send_problem_data(client):
    lat, lon = generate_problem_position()
    timestamp = int(time.time())
    payload = {"lat": lat, "lon": lon, "timestamp": timestamp, "command": "problem"}
    client.publish(STATUS_TOPIC, json.dumps(payload))

# Funktion zur Simulation des Mähens
def simulate_mowing(client):
    start_time = time.time()
    lat, lon = START_POSITION
    direction = random.uniform(0, 360)  # Startrichtung in Grad

    problem_count = 0

    while time.time() - start_time < SIMULATION_DURATION:
        if problem_count >= 5 and random.randint(5, 10) == 5:
            send_problem_data(client)
            client.publish(CONTROL_TOPIC, "stop")
            break

        # Berechnung der neuen Position basierend auf Richtung und Geschwindigkeit
        new_lat = lat + MOWING_SPEED * math.cos(math.radians(direction))
        new_lon = lon + MOWING_SPEED * math.sin(math.radians(direction)) / math.cos(math.radians(lat))

        # Überprüfung, ob die neue Position innerhalb der Grenzen liegt
        if is_inside_boundaries(new_lat, new_lon):
            lat, lon = new_lat, new_lon
        else:
            # Wenn die neue Position außerhalb liegt, Richtung ändern
            direction = (direction + random.uniform(90, 270)) % 360  # Umkehr der Richtung

        # Gelegentliches Hindernis
        if random.random() < TURN_PROBABILITY:
            direction = (direction + random.uniform(90, 270)) % 360

        timestamp = int(time.time())
        gps_data.append({"lat": lat, "lon": lon, "timestamp": timestamp})
        logging.debug(f"GPS-Daten: {lat:.6f}, {lon:.6f}, {timestamp}")
        time.sleep(GPS_INTERVAL)

        # Sende Statusmeldung, wenn der Status sich ändert
        if len(gps_data) % 10 == 0:  # Alle 10 Datenpunkte
            client.publish(STATUS_TOPIC, json.dumps({"status": "mowing"}))

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
        send_gps_data(client)
        gps_data = []  # Daten nach dem Senden zurücksetzen
    elif payload == "problem":  # Problemzonen-Meldung nur bei "problem"
        send_problem_data(client)
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
