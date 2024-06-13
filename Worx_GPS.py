import paho.mqtt.client as mqtt
import folium
import json
import os
from collections import deque
from folium.plugins import HeatMapWithTime
from dotenv import load_dotenv

# .env-Datei laden
load_dotenv()

# MQTT-Einstellungen aus Umgebungsvariablen
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))  # Standardmäßig Port 1883
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC_GPS = os.getenv("MQTT_TOPIC_GPS")
MQTT_TOPIC_STATUS = os.getenv("MQTT_TOPIC_STATUS")

# Grundstücksgrenzen, Map-Center und Dateinamen
lat_bounds = [46.811819, 46.812107]
lon_bounds = [7.132838, 7.133173]
MAP_CENTER = [(lat_bounds[0] + lat_bounds[1]) / 2, (lon_bounds[0] + lon_bounds[1]) / 2]
OUTPUT_DIR = "/config/www/worx_gps_tracker"

heatmap_filename = os.path.join(OUTPUT_DIR, "heatmap_aktuell.html")
heatmap_10_maehvorgang_filename = os.path.join(OUTPUT_DIR, "heatmap_10_maehvorgang.html")
heatmap_kumuliert_filename = os.path.join(OUTPUT_DIR, "heatmap_kumuliert.html")
problemzonen_heatmap_filename = os.path.join(OUTPUT_DIR, "heatmap_problemzonen.html")

# Anzahl der zu speichernden Daten
MAX_MAEHVORGAENGE = 10
MAX_PROBLEMZONEN = 20

# Speicher für Heatmap-Daten
maehvorgang_data = deque(maxlen=MAX_MAEHVORGAENGE)
alle_maehvorgang_data = []
problemzonen_data = deque(maxlen=MAX_PROBLEMZONEN)

# Funktion zum Speichern von GPS-Daten
def save_gps_data(data, filename):
    filename = os.path.join(OUTPUT_DIR, filename)
    with open(filename, "w") as f:
        json.dump(data, f)

# Funktion zum Speichern von Problemzonen-Daten
def save_problemzonen_data(data):
    filename = os.path.join(OUTPUT_DIR, "problemzonen.json")
    with open(filename, "w") as f:
        json.dump(list(data), f)

# Funktion zum Erstellen der Heatmap
def create_heatmap(data, filename, show_path=False):
    print(f"Erstelle Heatmap: {filename}")
    m = folium.Map(location=MAP_CENTER, zoom_start=20, control_scale=True, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                  attr='Google', name='Google Maps', max_zoom=20, subdomains=['mt0', 'mt1', 'mt2', 'mt3'])

    if data:
        # Heatmap-Layer hinzufügen
        heatmap_data = [[[point["lat"], point["lon"], point.get("timestamp", 0)] for point in mow_data] for mow_data in data]
        HeatMapWithTime(heatmap_data, radius=15, auto_play=True, max_opacity=0.8).add_to(m)

        # Pfad anzeigen (optional)
        if show_path:
            locations = [(point["lat"], point["lon"]) for point in data[0]]
            folium.PolyLine(locations, color="green", weight=2.5, opacity=1).add_to(m)
            for i in range(len(locations) - 1):
                folium.RegularPolygonMarker(location=locations[i], fill_color='green', number_of_sides=3, radius=5, rotation=90).add_to(m)

    # Grundstücksgrenzen als Rechteck hinzufügen
    folium.Rectangle(bounds=[(lat_bounds[0], lon_bounds[0]), (lat_bounds[1], lon_bounds[1])], color="blue", fill=False).add_to(m)

    m.save(filename)

# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    print("Verbunden mit MQTT Broker, return code:", rc)
    if MQTT_TOPIC_GPS:
        client.subscribe(MQTT_TOPIC_GPS)
        print(f"Abonniert auf Topic: {MQTT_TOPIC_GPS}")
    if MQTT_TOPIC_STATUS:
        client.subscribe(MQTT_TOPIC_STATUS)
        print(f"Abonniert auf Topic: {MQTT_TOPIC_STATUS}")

def on_message(client, userdata, msg):
    print(f"Nachricht empfangen auf Topic: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())

        if msg.topic == MQTT_TOPIC_GPS:
            maehvorgang_data.append(payload)
            alle_maehvorgang_data.extend(payload)
            save_gps_data(payload, f"maehvorgang_{len(maehvorgang_data)}.json")
            create_heatmap([payload], heatmap_filename, True)
            create_heatmap(list(maehvorgang_data), heatmap_10_maehvorgang_filename, False)
            create_heatmap([alle_maehvorgang_data], heatmap_kumuliert_filename, False)
        elif msg.topic == MQTT_TOPIC_STATUS:
            if payload.get("command") == "problem":
                problemzonen_data.append(payload)
                save_problemzonen_data(problemzonen_data)
                create_heatmap([problemzonen_data], problemzonen_heatmap_filename, False)

    except json.JSONDecodeError as e:
        print(f"Fehler beim Decodieren der JSON-Nachricht: {e}")
        print(f"Empfangene Nachricht: {msg.payload.decode()}")

# MQTT-Client erstellen und konfigurieren
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

# Verbindung zum Broker herstellen
client.connect(MQTT_HOST, MQTT_PORT)

# Endlosschleife für MQTT
client.loop_forever()
