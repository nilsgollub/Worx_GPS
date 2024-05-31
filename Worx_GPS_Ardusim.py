import paho.mqtt.client as mqtt
import time
import random
import json

# MQTT-Einstellungen (wie im Arduino-Sketch)
broker = "192.168.1.117"
port = 1883
topic_control = "worx/control"
topic_gps = "worx/gps"
topic_status = "worx/status"
user = "nilsgollub"
password = "JhiswenP3003!"

# Grundstücksgrenzen (wie im Arduino-Sketch)
lat_bounds = [46.811819, 46.812107]
lon_bounds = [7.132838, 7.133173]

# Simulationsdauer in Sekunden
simulation_duration = 5  # Simuliert einen 2-stündigen Mähvorgang in 5 Sekunden

# GPS-Intervall in Sekunden (für die Simulation beschleunigt)
gps_interval = 0.1

# Funktion zur Generierung zufälliger GPS-Koordinaten innerhalb der Grenzen
def generate_random_gps():
    lat = random.uniform(lat_bounds[0], lat_bounds[1])
    lon = random.uniform(lon_bounds[0], lon_bounds[1])
    return lat, lon

# Funktion zur Simulation des Mähvorgangs
def simulate_mowing(client):
    gps_data = []
    start_time = time.time()

    while time.time() - start_time < simulation_duration:
        lat, lon = generate_random_gps()
        timestamp = int(time.time())
        gps_data.append({"lat": lat, "lon": lon, "timestamp": timestamp})
        time.sleep(gps_interval)

    client.publish(topic_gps, json.dumps(gps_data))

# Funktion zur Simulation eines Problems
def simulate_problem(client):
    lat, lon = generate_random_gps()
    timestamp = int(time.time())
    problem_data = {"lat": lat, "lon": lon, "timestamp": timestamp}
    client.publish(topic_status, json.dumps(problem_data))

# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc):
    print("Verbunden mit MQTT Broker")
    client.subscribe(topic_control)

def on_message(client, userdata, msg):
    payload = msg.payload.decode()

    if payload == "start":
        print("Mähvorgang simulieren...")
        simulate_mowing(client)
    elif payload == "stop":
        print("Mähvorgang beendet.")
    elif payload == "problem":
        print("Problem simulieren...")
        simulate_problem(client)

# MQTT-Client erstellen und konfigurieren
client = mqtt.Client()
client.username_pw_set(user, password)
client.on_connect = on_connect
client.on_message = on_message

# Verbindung zum Broker herstellen
client.connect(broker, port)

# MQTT-Schleife starten
client.loop_forever()
