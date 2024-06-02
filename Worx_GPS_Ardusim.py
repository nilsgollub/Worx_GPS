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

# Grundstückgrenzen
LAT_BOUNDS = [46.811819, 46.812107]
LON_BOUNDS = [7.132838, 7.133173]

# Simulations parameter
SIMULATION_DURATION = 5.0  # in seconds
GPS_INTERVAL = 0.1  # in seconds

# GPS-Daten
gps_data = []

# Funktion, um eine zufällige Zahl innerhalb der Grenzen zu erzeugen
def generate_random_gps():
    lat = random.uniform(*LAT_BOUNDS)
    lon = random.uniform(*LON_BOUNDS)
    return lat, lon

# Funktion zum Senden der GPS-Daten
def send_gps_data(client):
    logging.info("Sende GPS-Daten...")
    client.publish(GPS_TOPIC, json.dumps(gps_data))

# Funktion zum Senden der Problem-Daten
def send_problem_data(client):
    lat, lon = generate_random_gps()
    timestamp = int(time.time())
    payload = {"lat": lat, "lon": lon, "timestamp": timestamp, "command": "problem"}
    client.publish(STATUS_TOPIC, json.dumps(payload))

def simulate_mowing(client):
    start_time = time.time()
    lat, lon = generate_random_gps()  # Startposition
    direction = random.uniform(0, 360)  # Startrichtung in Grad
    speed = 0.00005  # Geschwindigkeit (Anpassen für realistischere Simulation)
    turn_angle = 30  # Winkel für Richtungsänderungen
    turn_time = 0  # Zeit bis zur nächsten Richtungsänderung
    max_turn_time = 10  # Maximale Zeit zwischen Richtungsänderungen

    while time.time() - start_time < SIMULATION_DURATION:
        # Bewegung in Richtung berechnen
        lat_rad = lat * (math.pi / 180)  # Umrechnung in Bogenmaß
        lon_rad = lon * (math.pi / 180)
        lat += speed * math.cos(direction * (math.pi / 180))
        lon += speed * math.sin(direction * (math.pi / 180)) / math.cos(lat_rad)

        # Begrenzung auf die Grundstücksgrenzen
        if not (LAT_BOUNDS[0] <= lat <= LAT_BOUNDS[1] and LON_BOUNDS[0] <= lon <= LON_BOUNDS[1]):
            # Richtungsänderung an den Grenzen erzwingen
            direction = random.uniform(0, 360)

        # Richtungsänderung nach zufälliger Zeit
        turn_time -= 1
        if turn_time <= 0:
            direction += random.uniform(-turn_angle, turn_angle)
            turn_time = random.randint(1, max_turn_time)

        timestamp = int(time.time())
        gps_data.append({"lat": lat, "lon": lon, "timestamp": timestamp})
        logging.debug(f"GPS-Daten: {lat:.6f}, {lon:.6f}, {timestamp}")
        time.sleep(GPS_INTERVAL)

    send_gps_data(client)

# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    logging.info(f"Connected with result code {rc}")
    client.subscribe(CONTROL_TOPIC)

def on_message(client, userdata, msg):
    global gps_data
    payload = msg.payload.decode()
    logging.info(f"Nachricht empfangen: {payload}")

    if payload == "start":
        gps_data = []
        simulate_mowing(client)
    elif payload == "stop":
        send_gps_data(client)
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
