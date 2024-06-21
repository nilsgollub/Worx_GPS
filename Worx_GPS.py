import paho.mqtt.client as mqtt
import folium
import json
import webbrowser
import os
from collections import deque
from folium.plugins import HeatMapWithTime
from dotenv import load_dotenv

load_dotenv(".env")  # Laden der Umgebungsvariablen

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
heatmap_filename = "heatmap_aktuell.html"
heatmap_10_maehvorgang_filename = "heatmap_10_maehvorgang.html"
heatmap_kumuliert_filename = "heatmap_kumuliert.html"
problemzonen_heatmap_filename = "heatmap_problemzonen.html"

# Anzahl der zu speichernden Problemzonen (einfach anpassbar)
MAX_PROBLEMZONEN = 20

# Speicher für Heatmap-Daten
maehvorgang_data = deque(maxlen=10)
alle_maehvorgang_data = []
problemzonen_data = deque(maxlen=MAX_PROBLEMZONEN)
# Funktion zum Speichern von GPS-Daten
def save_gps_data(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f)

# Funktion zum Speichern von Problemzonen-Daten
def save_problemzonen_data(data):
    with open("problemzonen.json", "w") as f:
        json.dump(list(data), f)  # Konvertiere deque zu Liste für JSON

# Funktion zum Erstellen der Heatmap
def create_heatmap(data, filename, show_path=False):
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
    if show_path:
        webbrowser.open('file://' + os.path.realpath(filename))
# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    print("Verbunden mit MQTT Broker, return code:", rc)
    if topic_gps:
        client.subscribe(topic_gps)
    if topic_status:
        client.subscribe(topic_status)
def read_gps_data_from_csv_string(csv_string):
    data = []
    for line in csv_string.splitlines():
        if line and line != "-1":  # Leere Zeilen und Ende-Marker ignorieren
            parts = line.split(",")
            data.append({
                "lat": float(parts[0]),
                "lon": float(parts[1]),
                "timestamp": int(parts[2])
            })
    return data

def on_message(client, userdata, msg):
    if msg.topic == topic_gps:
        csv_data = msg.payload.decode()
        if csv_data != "-1":  # Ende-Marker ignorieren
            # CSV-Daten in Liste von Dictionaries umwandeln
            gps_data = read_gps_data_from_csv_string(csv_data)

            maehvorgang_data.append(gps_data)
            alle_maehvorgang_data.extend(gps_data)
            save_gps_data(gps_data, f"maehvorgang_{len(maehvorgang_data)}.json")
            create_heatmap([gps_data], heatmap_filename, True)  # Übergib die Daten als Liste
            create_heatmap(list(maehvorgang_data), heatmap_10_maehvorgang_filename, False)
            create_heatmap([alle_maehvorgang_data], heatmap_kumuliert_filename, False)

    elif msg.topic == topic_status:
        # Problemzonen-Daten empfangen
        csv_data = msg.payload.decode()
        print("Empfangene Problemzonen-Daten:", csv_data)

        if csv_data != "-1":  # Ende-Marker ignorieren
            # CSV-Daten in Liste von Dictionaries umwandeln
            problem_data_list = read_gps_data_from_csv_string(csv_data)

            # Nur den letzten Datenpunkt verwenden (da es immer nur eine aktuelle Problemzone gibt)
            if problem_data_list:
                problem_data = problem_data_list[-1]
                # Sicherstellen, dass nur lat und lon in problemzonen_data gespeichert werden
                problemzonen_data.append({"lat": problem_data["lat"], "lon": problem_data["lon"]})
                save_problemzonen_data(problemzonen_data)
                create_heatmap([problemzonen_data], problemzonen_heatmap_filename, False) # Übergib die Daten als Liste
# MQTT-Client erstellen und konfigurieren
client = mqtt.Client(client_id="", userdata=None, protocol=mqtt.MQTTv5)
client.username_pw_set(user, password)
client.on_connect = on_connect
client.on_message = on_message

# Überprüfen, ob MQTT-Topics definiert sind
if not topic_gps:
    print("Fehler: MQTT_TOPIC_GPS ist nicht in der secrets.env-Datei definiert.")
if not topic_status:
    print("Fehler: MQTT_TOPIC_STATUS ist nicht in der secrets.env-Datei definiert.")

try:
    # Verbindung zum Broker herstellen
    client.connect(broker, port)

    # MQTT-Schleife starten
    client.loop_forever()
except ConnectionRefusedError:
    print(f"Verbindung zum MQTT-Broker '{broker}:{port}' konnte nicht hergestellt werden. Überprüfen Sie die Einstellungen und die Erreichbarkeit des Brokers.")
