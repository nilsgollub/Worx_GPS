import paho.mqtt.client as mqtt  # Import unter dem korrekten Namen
import time
import random
import json
from dotenv import load_dotenv
import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load environment variables from .env file
load_dotenv("secrets.env")

# MQTT topics from secrets.env
CONTROL_TOPIC = os.getenv("MQTT_TOPIC_CONTROL")
GPS_TOPIC = os.getenv("MQTT_TOPIC_GPS")
STATUS_TOPIC = os.getenv("MQTT_TOPIC_STATUS")

# Grundstückgrenzen
LAT_BOUNDS = [46.811819, 46.812107]
LON_BOUNDS = [7.132838, 7.133173]

# GPS-Daten
gps_data = []

def on_connect(client, userdata, flags, rc, properties=None):  # Extra Argument properties hinzugefügt
    print(f"Connected with result code {rc}")
    client.subscribe(CONTROL_TOPIC)

def on_message(client, userdata, msg):
    global gps_data
    payload = msg.payload.decode()

    if payload == "start":
        gps_data = []
        simulate_mowing(client)
    elif payload == "stop":
        send_gps_data(client)
    elif payload == "problem":  # Problemkoordinaten nur bei "problem"-Befehl senden
        send_problem_data(client)
    else:
        print(f"Unbekannter Befehl: {payload}")


def simulate_mowing(client):
    num_points = 2 * 60 * 60 // 2
    lat_step = (LAT_BOUNDS[1] - LAT_BOUNDS[0]) / 20
    lon_step = (LON_BOUNDS[1] - LON_BOUNDS[0]) / 20

    lat = LAT_BOUNDS[0]
    lon = LON_BOUNDS[0]
    direction = 1
    timestamp = int(time.time())

    for _ in range(num_points):
        gps_data.append({"lat": lat, "lon": lon, "timestamp": timestamp})  # Dictionary für GPS-Daten
        timestamp += 2

        # Bewegung simulieren
        lon += direction * lon_step
        if lon > LON_BOUNDS[1] or lon < LON_BOUNDS[0]:
            direction *= -1
            lat += lat_step

def send_gps_data(client):
    client.publish(GPS_TOPIC, json.dumps(gps_data))

def send_problem_data(client):
    lat = random.uniform(*LAT_BOUNDS)
    lon = random.uniform(*LON_BOUNDS)
    timestamp = int(time.time())
    payload = {"lat": lat, "lon": lon, "timestamp": timestamp, "command": "problem"} # Dictionary für Problem-Daten
    client.publish(STATUS_TOPIC, json.dumps(payload))  # JSON senden

# Get MQTT credentials from environment variables
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

client = mqtt.Client(client_id="", userdata=None, protocol=mqtt.MQTTv5)  # mqtt anstelle von paho
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.connect(MQTT_HOST, MQTT_PORT, 60)

client.loop_forever()
