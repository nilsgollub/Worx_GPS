import paho.mqtt.client as mqtt
import folium
import json
import webbrowser
import os
from collections import deque

# MQTT-Einstellungen
broker = "192.168.1.117"
port = 1883
topic_gps = "worx/gps"
topic_status = "worx/status"
user = "nilsgollub"
password = "JhiswenP3003!"

# Grundstücksgrenzen
lat_bounds = [46.811819, 46.812107]
lon_bounds = [7.132838, 7.133173]
map_center = [(lat_bounds[0] + lat_bounds[1]) / 2, (lon_bounds[0] + lon_bounds[1]) / 2]

# Google Maps API Key
google_maps_api_key = "AIzaSyCeUl8GA9G9XnnbxMgljrc1i1utlz3jm1o"

# Dateinamen für Heatmaps
heatmap_filename = "maehvorgang_heatmap.html"
heatmap_10_maehvorgang_filename = "10_maehvorgang_heatmap.html"
problemzonen_heatmap_filename = "problemzonen_heatmap.html"

# GPS-Daten-Speicher
maehvorgang_data = deque(maxlen=10)
problemzonen_data = []

# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc):
    print("Verbunden mit MQTT Broker")
    client.subscribe(topic_gps)
    client.subscribe(topic_status)

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())

    if msg.topic == topic_gps:
        maehvorgang_data.append(payload)
        create_heatmap(payload, heatmap_filename, True)
        create_heatmap(list(maehvorgang_data), heatmap_10_maehvorgang_filename, False)
    elif msg.topic == topic_status:
        problemzonen_data.append(payload)
        create_heatmap(problemzonen_data, problemzonen_heatmap_filename, False)

# Funktion zum Erstellen der Heatmap
def create_heatmap(data, filename, show_path=False):
    m = folium.Map(location=map_center, zoom_start=18, control_scale=True)

    # LayerControl hinzufügen
    folium.TileLayer('OpenStreetMap').add_to(m)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Maps',
        max_zoom=20,
        subdomains=['mt0', 'mt1', 'mt2', 'mt3']
    ).add_to(m)
    folium.LayerControl().add_to(m)

    # Heatmap-Layer hinzufügen
    heatmap_data = [(point["lat"], point["lon"]) for point in data]
    folium.plugins.HeatMap(heatmap_data, radius=15).add_to(m)

    # Pfad anzeigen (optional)
    if show_path:
        locations = [(point["lat"], point["lon"]) for point in data]
        folium.PolyLine(locations, color="green", weight=2.5, opacity=1).add_to(m)
        for i in range(len(locations) - 1):
            folium.RegularPolygonMarker(location=locations[i], fill_color='green', number_of_sides=3, radius=5, rotation=90).add_to(m)

    # Grundstücksgrenzen als Rechteck hinzufügen
    folium.Rectangle(bounds=[(lat_bounds[0], lon_bounds[0]), (lat_bounds[1], lon_bounds[1])], color="blue", fill=False).add_to(m)

    # Karte speichern und im Browser öffnen
    m.save(filename)
    if show_path:  # Nur die Heatmap des aktuellen Mähvorgangs öffnen
        webbrowser.open('file://' + os.path.realpath(filename))

# MQTT-Client erstellen und konfigurieren
client = mqtt.Client()
client.username_pw_set(user, password)
client.on_connect = on_connect
client.on_message = on_message

# Verbindung zum Broker herstellen
client.connect(broker, port)

# MQTT-Schleife starten
client.loop_forever()
