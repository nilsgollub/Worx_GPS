import paho.mqtt.client as mqtt
import folium
import json
import webbrowser
import os
from collections import deque
from folium.plugins import HeatMapWithTime
from dotenv import load_dotenv, find_dotenv

# Umgebung und Ausführungspfad anzeigen
if os.getenv("HASSIO_TOKEN"):
    print("Skript wird in Home Assistant ausgeführt.")
else:
    print("Skript wird lokal ausgeführt.")

# Pfad zur .env-Datei ermitteln und laden
env_path = find_dotenv()
if env_path:
    print(f".env-Datei gefunden unter: {env_path}")
    load_dotenv(env_path)
else:
    print("Fehler: .env-Datei nicht gefunden.")
    exit(1)  # Beenden, wenn die .env-Datei nicht gefunden wird

# MQTT-Einstellungen
broker = os.getenv("MQTT_HOST")
port = int(os.getenv("MQTT_PORT", 1883))  # Fehlerbehandlung für fehlenden Port
topic_gps = os.getenv("MQTT_TOPIC_GPS")
topic_status = os.getenv("MQTT_TOPIC_STATUS")
user = os.getenv("MQTT_USER")
password = os.getenv("MQTT_PASSWORD")

# Sicherstellen, dass Topics Strings sind und vorhanden
topic_gps = str(topic_gps) if topic_gps else None
topic_status = str(topic_status) if topic_status else None

# Grundstücksgrenzen, Map-Center und Dateinamen
lat_bounds = [46.811819, 46.812107]
lon_bounds = [7.132838, 7.133173]
map_center = [(lat_bounds[0] + lat_bounds[1]) / 2, (lon_bounds[0] + lon_bounds[1]) / 2]

# Ausgabeverzeichnis (Standardmäßig im Add-on-Ordner)
output_dir = os.getenv("OUTPUT_DIR", "/home/homeassistant/www/worx_gps_tracker") 
heatmap_filename = os.path.join(output_dir, "heatmap_aktuell.html")
heatmap_10_maehvorgang_filename = os.path.join(output_dir, "heatmap_10_maehvorgang.html")
heatmap_kumuliert_filename = os.path.join(output_dir, "heatmap_kumuliert.html")
problemzonen_heatmap_filename = os.path.join(output_dir, "heatmap_problemzonen.html")

# Anzahl der zu speichernden Problemzonen
MAX_PROBLEMZONEN = 20

# Speicher für Heatmap-Daten
maehvorgang_data = deque(maxlen=10)
alle_maehvorgang_data = []
problemzonen_data = deque(maxlen=MAX_PROBLEMZONEN)
# Funktion zum Speichern von GPS-Daten
def save_gps_data(data, filename):
    filename = os.path.join(output_dir, filename)  # Pfad anpassen
    with open(filename, "w") as f:
        json.dump(data, f)

# Funktion zum Speichern von Problemzonen-Daten
def save_problemzonen_data(data):
    filename = os.path.join(output_dir, "problemzonen.json")  # Pfad anpassen
    with open(filename, "w") as f:
        json.dump(list(data), f)  # Konvertiere deque zu Liste für JSON

# Funktion zum Erstellen der Heatmap
def create_heatmap(data, filename, show_path=False):
    print(f"Erstelle Heatmap: {filename}")  # Statusmeldung hinzufügen
    m = folium.Map(location=map_center, zoom_start=20, control_scale=True, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Maps',
        max_zoom=20,
        subdomains=['mt0', 'mt1', 'mt2', 'mt3'])  # Google Maps Satellitenansicht

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
    # Nur öffnen, wenn nicht auf Home Assistant ausgeführt wird
    if not os.getenv("HASSIO_TOKEN"):
        if show_path:
            webbrowser.open('file://' + os.path.realpath(filename))# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    print("Verbunden mit MQTT Broker, return code:", rc)
    if topic_gps:
        client.subscribe(topic_gps)
        print(f"Abonniert auf Topic: {topic_gps}")  # Statusmeldung hinzufügen
    if topic_status:
        client.subscribe(topic_status)
        print(f"Abonniert auf Topic: {topic_status}")  # Statusmeldung hinzufügen

def on_message(client, userdata, msg):
    print(f"Nachricht empfangen auf Topic: {msg.topic}")  # Statusmeldung hinzufügen
    try:
        payload = json.loads(msg.payload.decode())

        if msg.topic == topic_gps:
            maehvorgang_data.append(payload)
            alle_maehvorgang_data.extend(payload)  # Zur kumulierten Liste hinzufügen
            save_gps_data(payload, f"maehvorgang_{len(maehvorgang_data)}.json")
            create_heatmap([payload], heatmap_filename, True)
            create_heatmap(list(maehvorgang_data), heatmap_10_maehvorgang_filename, False)
            create_heatmap([alle_maehvorgang_data], heatmap_kumuliert_filename, False)  # Kumulierte Heatmap
        elif msg.topic == topic_status:
            if payload.get("command") == "problem":
                problemzonen_data.append(payload)
                save_problemzonen_data(problemzonen_data)
                create_heatmap([problemzonen_data], problemzonen_heatmap_filename, False)

    except json.JSONDecodeError as e:
        print(f"Fehler beim Decodieren der JSON-Nachricht: {e}")
        print(f"Empfangene Nachricht: {msg.payload.decode()}")

# MQTT-Client erstellen und konfigurieren
client = mqtt.Client()

# Callbacks setzen (neue Methode)
client.on_connect = on_connect
client.on_message = on_message

client.username_pw_set(user, password)

# Überprüfen, ob MQTT-Topics definiert sind
if not topic_gps:
    print("Fehler: MQTT_TOPIC_GPS ist nicht in der .env-Datei definiert.")
if not topic_status:
    print("Fehler: MQTT_TOPIC_STATUS ist nicht in der .env-Datei definiert.")

try:
    # Verbindung zum Broker herstellen
    client.connect(broker, port)

    # MQTT-Schleife starten
    client.loop_forever()
except ConnectionRefusedError:
    print(f"Verbindung zum MQTT-Broker '{broker}:{port}' konnte nicht hergestellt werden. Überprüfen Sie die Einstellungen und die Erreichbarkeit des Brokers.")