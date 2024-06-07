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
load_dotenv()

# Get MQTT credentials from environment variables
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))  # Default-Port 1883
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# MQTT topics from .env
CONTROL_TOPIC = os.getenv("MQTT_TOPIC_CONTROL")
GPS_TOPIC = os.getenv("MQTT_TOPIC_GPS")
STATUS_TOPIC = os.getenv("MQTT_TOPIC_STATUS")

# Grundstückgrenzen
LAT_BOUNDS = [46.811819, 46.812107]
LON_BOUNDS = [7.132838, 7.133173]

# Simulations parameter
SIMULATION_DURATION = 5.0  # in seconds
GPS_INTERVAL = 0.005  # in seconds

# GPS-Daten
gps_data = []


# Funktion, um eine zufällige Zahl innerhalb der Grenzen zu erzeugen
def generate_random_gps():
    while True:
        lat = random.uniform(*LAT_BOUNDS)
        lon = random.uniform(*LON_BOUNDS)
        if is_inside_boundaries(lat, lon):  # Überprüfen, ob Punkt innerhalb liegt
            return lat, lon

# Funktion zum Senden der GPS-Daten (nur bei "stop"-Befehl)
def send_gps_data(client):
    if gps_data:  # Nur senden, wenn Daten vorhanden sind
        logging.info("Sende GPS-Daten...")
        client.publish(GPS_TOPIC, json.dumps(gps_data))

# Funktion zum Senden der Problem-Daten
def send_problem_data(client):
    lat, lon = generate_random_gps()
    timestamp = int(time.time())
    payload = {"lat": lat, "lon": lon, "timestamp": timestamp, "command": "problem"}
    client.publish(STATUS_TOPIC, json.dumps(payload))

# Funktion zur Überprüfung, ob ein Punkt innerhalb der Grenzen liegt
def is_inside_boundaries(lat, lon):
    return LAT_BOUNDS[0] <= lat <= LAT_BOUNDS[1] and LON_BOUNDS[0] <= lon <= LON_BOUNDS[1]

def simulate_mowing(client):
    start_time = time.time()
    lat, lon = generate_random_gps()  # Startposition
    direction = random.uniform(0, 360)  # Startrichtung in Grad
    speed = 0.00001  # Geschwindigkeit (Anpassen für realistischere Simulation)
    turn_angle = 30  # Winkel für Richtungsänderungen
    turn_time = 0  # Zeit bis zur nächsten Richtungsänderung
    max_turn_time = 10  # Maximale Zeit zwischen Richtungsänderungen

    while time.time() - start_time < SIMULATION_DURATION:
        # Berechnung der neuen Position basierend auf Richtung und Geschwindigkeit
        new_lat = lat + speed * math.cos(math.radians(direction))
        new_lon = lon + speed * math.sin(math.radians(direction)) / math.cos(math.radians(lat))

        # Überprüfung, ob die neue Position innerhalb der Grenzen liegt
        if is_inside_boundaries(new_lat, new_lon):
            lat, lon = new_lat, new_lon
        else:
            # Wenn die neue Position außerhalb liegt, Richtung ändern
            direction = (direction + 180) % 360  # Umkehr der Richtung

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
