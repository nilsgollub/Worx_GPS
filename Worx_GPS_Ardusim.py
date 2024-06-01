import paho.mqtt.client as mqtt
import time
import random
from dotenv import load_dotenv
import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load environment variables from .env file
load_dotenv("secrets.env")

# MQTT topics
CONTROL_TOPIC = "worx/control"
GPS_TOPIC = "worx/gps"
STATUS_TOPIC = "worx/status"

# Grundstückgrenzen
LAT_BOUNDS = [46.811819, 46.812107]
LON_BOUNDS = [7.132838, 7.133173]

# GPS-Daten
gps_data = []

def on_connect(client, userdata, flags, rc):
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
        send_problem_data(client)
    elif payload == "problem":
        send_problem_data(client)

def simulate_mowing(client):
    num_points = 2 * 60 * 60 // 2
    lat_step = (LAT_BOUNDS[1] - LAT_BOUNDS[0]) / 20
    lon_step = (LON_BOUNDS[1] - LON_BOUNDS[0]) / 20

    lat = LAT_BOUNDS[0]
    lon = LON_BOUNDS[0]
    direction = 1
    timestamp = int(time.time())

    for _ in range(num_points):
        gps_data.append(f"{lat:.6f},{lon:.6f};{timestamp}\n")
        timestamp += 2

        # Bewegung simulieren
        lon += direction * lon_step
        if lon > LON_BOUNDS[1] or lon < LON_BOUNDS[0]:
            direction *= -1
            lat += lat_step

def send_gps_data(client):
    payload = "".join(gps_data)
    client.publish(GPS_TOPIC, payload)

def send_problem_data(client):
    lat = random.uniform(*LAT_BOUNDS)
    lon = random.uniform(*LON_BOUNDS)
    timestamp = int(time.time())
    payload = f"{lat:.6f},{lon:.6f};{timestamp}"
    client.publish(STATUS_TOPIC, payload)

# Get MQTT credentials from environment variables
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.connect(MQTT_HOST, MQTT_PORT, 60)

client.loop_forever()
