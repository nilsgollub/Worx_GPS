import paho.mqtt.client as mqtt
import time
import random
import json
import logging
import math
from dotenv import load_dotenv
import os
from shapely.geometry import Point, Polygon

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

# Grundstück und Hindernisse als Polygone
grundstueck = Polygon([
    (46.812107, 7.132857), (46.812085, 7.133173),
    (46.811819, 7.133167), (46.811838, 7.132838)
])
haus = Polygon([
    (46.8120556456017, 7.132959800517059), (46.81205289207122, 7.1331019575932215),
    (46.81194366858195, 7.132953094994599)
])
gartenhuette = Polygon([
    (46.81204241084189, 7.133116853854645), (46.8120414436835, 7.133164194731294),
    (46.81200324091312, 7.133114734113899), (46.81200275733357, 7.133163488151045)
])
parkplatz = Polygon([
    (46.8121055351934, 7.1328510893279615), (46.812102781665494, 7.1329637421052965),
    (46.811983461986756, 7.132942284433424), (46.81195959801924, 7.132840360492025)
])

# Typische Problemstellen
problemstellen = [
    (46.81209268539523, 7.132970447627758), (46.812018340074374, 7.133119310227487),
    (46.81191829497382, 7.1330321384355)
]

# Simulations parameter (angepasst)
SIMULATION_DURATION = 5.0  # in seconds
GPS_INTERVAL = 2.0  # Alle 2 Sekunden ein Messwert
speed = 4 / 3.6 * GPS_INTERVAL  # Geschwindigkeit in m/s (4 km/h umgerechnet)

# GPS-Daten
gps_data = []

# Funktion, um eine zufällige Zahl innerhalb der Grenzen zu erzeugen
def generate_random_gps():
    while True:
        lat = random.uniform(min(p[0] for p in grundstueck.exterior.coords), max(p[0] for p in grundstueck.exterior.coords))
        lon = random.uniform(min(p[1] for p in grundstueck.exterior.coords), max(p[1] for p in grundstueck.exterior.coords))
        if grundstueck.contains(Point(lat, lon)) and not any(hindernis.contains(Point(lat, lon)) for hindernis in [haus, gartenhuette, parkplatz]):
            return lat, lon

# Funktion zum Senden der GPS-Daten (nur bei "stop"-Befehl)
def send_gps_data(client):
    if gps_data:  # Nur senden, wenn Daten vorhanden sind
        logging.info("Sende GPS-Daten...")
        client.publish(GPS_TOPIC, json.dumps(gps_data))

# Funktion zum Senden der Problem-Daten
def send_problem_data(client):
    lat, lon = random.choice(problemstellen) if random.random() < 0.8 else generate_random_gps()
    timestamp = int(time.time())
    payload = {"lat": lat, "lon": lon, "timestamp": timestamp, "command": "problem"}
    client.publish(STATUS_TOPIC, json.dumps(payload))

# Funktion zur Überprüfung, ob ein Punkt innerhalb der Grenzen liegt
def is_inside_boundaries(lat, lon):
    return grundstueck.contains(Point(lat, lon)) and not any(hindernis.contains(Point(lat, lon)) for hindernis in [haus, gartenhuette, parkplatz])  # Schließende Klammer hinzugefügt


def simulate_mowing(client):
    start_time = time.time()
    lat, lon = generate_random_gps()  # Startposition
    direction = random.uniform(0, 360)  # Startrichtung in Grad
    turn_angle = 30  # Winkel für Richtungsänderungen
    turn_time = 0  # Zeit bis zur nächsten Richtungsänderung
    max_turn_time = 10  # Maximale Zeit zwischen Richtungsänderungen

    while time.time() - start_time < SIMULATION_DURATION:
        # Berechnung der neuen Position basierend auf Richtung und Geschwindigkeit
        new_lat = lat + speed * math.cos(math.radians(direction))
        new_lon = lon + speed * math.sin(math.radians(direction)) / math.cos(math.radians(lat))

        # Kollisionserkennung mit Hindernissen und Grundstück
        current_point = Point(new_lat, new_lon)
        if not grundstueck.contains(current_point) or any(hindernis.contains(current_point) for hindernis in [haus, gartenhuette, parkplatz]):
            # Kollision: Richtung zufällig ändern
            direction = (direction + random.uniform(90, 270)) % 360

        else:
            lat, lon = new_lat, new_lon

        # Richtungsänderung nach zufälliger Zeit
        turn_time -= 1
        if turn_time <= 0:
            direction += random.uniform(-turn_angle, turn_angle)
            turn_time = random.randint(1, max_turn_time)

        timestamp = int(time.time())
        gps_data.append({"lat": lat, "lon": lon, "timestamp": timestamp})
        logging.debug(f"GPS-Daten: {lat:.6f}, {lon:.6f}, {timestamp}")
        time.sleep(GPS_INTERVAL)

        # Sende Statusmeldung, wenn der Status sich ändert
        if len(gps_data) % 10 == 0:  # Alle 10 Datenpunkte
            client.publish(STATUS_TOPIC, json.dumps({"status": "mowing"}))

        # Problemmeldung an zufälligen Stellen und häufiger an Problemstellen
        if random.random() < 0.05 or current_point.distance(Point(random.choice(problemstellen))) < 0.0001:  # 5% Wahrscheinlichkeit oder nahe Problemstelle
            send_problem_data(client)


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
