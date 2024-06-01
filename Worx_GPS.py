import paho.mqtt.client as paho
import folium
import json
import webbrowser
import os
from collections import deque
from folium.plugins import HeatMapWithTime
from dotenv import load_dotenv

load_dotenv("secrets.env")  # Geben Sie den Dateinamen explizit an

# MQTT-Einstellungen aus secrets.env
broker = os.getenv("MQTT_HOST")
port = int(os.getenv("MQTT_PORT", 1883))  # Fehlerbehandlung für fehlenden Port
topic_gps = os.getenv("MQTT_TOPIC_GPS")
topic_status = os.getenv("MQTT_TOPIC_STATUS")
user = os.getenv("MQTT_USER")
password = os.getenv("MQTT_PASSWORD")

# Sicherstellen, dass Topics Strings sind und vorhanden
topic_gps = str(topic_gps) if topic_gps else None
topic_status = str(topic_status) if topic_status else None

# Grundstücksgrenzen
lat_bounds = [46.811819, 46.812107]
lon_bounds = [7.132838, 7.133173]
map_center = [(lat_bounds[0] + lat_bounds[1]) / 2, (lon_bounds[0] + lon_bounds[1]) / 2]

# Google Maps API Key aus secrets.env
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

# Dateinamen für Heatmaps
heatmap_filename = "maehvorgang_heatmap.html"
heatmap_10_maehvorgang_filename = "10_maehvorgang_heatmap.html"
problemzonen_heatmap_filename = "problemzonen_heatmap.html"

# GPS-Daten-Speicher
maehvorgang_data = deque(maxlen=10)
problemzonen_data = []

# MQTT-Callback-Funktionen (aktualisiert für MQTTv5)
def on_connect(client, userdata, flags, rc, properties=None):  # Extra Argument properties hinzugefügt
    print("Verbunden mit MQTT Broker, return code:", rc)
    if topic_gps:  # Nur abonnieren, wenn das Topic definiert ist
        client.subscribe(topic_gps)
    if topic_status:
        client.subscribe(topic_status)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())

        if msg.topic == topic_gps:
            maehvorgang_data.append(payload)
            create_heatmap([payload], heatmap_filename, True)  # Zusätzliche Liste für Heatmap-Daten
            create_heatmap(list(maehvorgang_data), heatmap_10_maehvorgang_filename, False)
        elif msg.topic == topic_status:
            problemzonen_data.append(payload)  # Änderung rückgängig gemacht
            create_heatmap([problemzonen_data], problemzonen_heatmap_filename, False)  # Zusätzliche Liste für Heatmap-Daten

    except json.JSONDecodeError as e:
        print(f"Fehler beim Decodieren der JSON-Nachricht: {e}")
        print(f"Empfangene Nachricht: {msg.payload.decode()}")  # Ausgabe der fehlerhaften Nachricht

# Funktion zum Erstellen der Heatmap
def create_heatmap(data, filename, show_path=False):
    m = folium.Map(location=map_center, zoom_start=18, control_scale=True)

    # LayerControl hinzufügen
    folium.TileLayer('OpenStreetMap').add_to(m)
    google_layer = folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Maps',
        max_zoom=20,
        subdomains=['mt0', 'mt1', 'mt2', 'mt3']
    )
    google_layer.add_to(m)
    folium.LayerControl().add_to(m)

    # Heatmap-Layer hinzufügen (mit Zeitstempeln für HeatMapWithTime)
    heatmap_data = [[[point["lat"], point["lon"], point["timestamp"]] for point in mow_data] for mow_data in data]  # Korrigierte Datenstruktur
    HeatMapWithTime(heatmap_data, radius=15, auto_play=True, max_opacity=0.8).add_to(m)

    # Pfad anzeigen (optional)
    if show_path and data:  # Überprüfen, ob Daten vorhanden sind
        locations = [(point["lat"], point["lon"]) for point in data[0]]  # Daten aus der ersten Liste nehmen (aktueller Mähvorgang)
        folium.PolyLine(locations, color="green", weight=2.5, opacity=1).add_to(m)
        for i in range(len(locations) - 1):
            folium.RegularPolygonMarker(location=locations[i], fill_color='green', number_of_sides=3, radius=5, rotation=90).add_to(m)

    # Grundstücksgrenzen als Rechteck hinzufügen
    folium.Rectangle(bounds=[(lat_bounds[0], lon_bounds[0]), (lat_bounds[1], lon_bounds[1])], color="blue", fill=False).add_to(m)

    # Karte speichern
    m.save(filename)

    # Karte nur öffnen, wenn der aktuelle Mähvorgang angezeigt wird
    if show_path:
        webbrowser.open('file://' + os.path.realpath(filename))

# MQTT-Client erstellen und konfigurieren
client = paho.Client(client_id="", userdata=None, protocol=paho.MQTTv5) # Aktualisierter Client
client.username_pw_set(user, password)
client.on_connect = on_connect
client.on_message = on_message

try:
    # Verbindung zum Broker herstellen
    client.connect(broker, port)

    # MQTT-Schleife starten
    client.loop_forever()
except ConnectionRefusedError:
    print(f"Verbindung zum MQTT-Broker '{broker}:{port}' konnte nicht hergestellt werden. Überprüfen Sie die Einstellungen und die Erreichbarkeit des Brokers.")
