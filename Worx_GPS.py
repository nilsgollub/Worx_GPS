import paho.mqtt.client as mqtt
import folium
import json
import os
import time  # time-Modul importieren
import socket  # socket-Modul importieren
from collections import deque
from folium.plugins import HeatMapWithTime
from dotenv import load_dotenv

print("Skript gestartet")  # Debug-Ausgabe

# .env-Datei laden
load_dotenv()
print("Env geladen")  # Debug-Ausgabe

# MQTT-Einstellungen aus Umgebungsvariablen
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC_GPS = os.getenv("MQTT_TOPIC_GPS")
MQTT_TOPIC_STATUS = os.getenv("MQTT_TOPIC_STATUS")

print(f"MQTT-Einstellungen: {MQTT_HOST}:{MQTT_PORT}, {MQTT_USER}, {MQTT_TOPIC_GPS}, {MQTT_TOPIC_STATUS}")  # Debug-Ausgabe

# Grundstücksgrenzen, Map-Center und Dateinamen
LAT_BOUNDS = [46.811819, 46.812107]
LON_BOUNDS = [7.132838, 7.133173]
MAP_CENTER = [(LAT_BOUNDS[0] + LAT_BOUNDS[1]) / 2, (LON_BOUNDS[0] + LON_BOUNDS[1]) / 2]
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/config/www/worx_gps_tracker")  # Ausgabeverzeichnis aus .env lesen

heatmap_filename = os.path.join(OUTPUT_DIR, "heatmap_aktuell.html")
heatmap_10_maehvorgang_filename = os.path.join(OUTPUT_DIR, "heatmap_10_maehvorgang.html")
heatmap_kumuliert_filename = os.path.join(OUTPUT_DIR, "heatmap_kumuliert.html")
problemzonen_heatmap_filename = os.path.join(OUTPUT_DIR, "heatmap_problemzonen.html")


# Anzahl der zu speichernden Problemzonen (einfach anpassbar)
MAX_PROBLEMZONEN = 20

# Speicher für Heatmap-Daten
maehvorgang_data = deque(maxlen=10)
alle_maehvorgang_data = []
problemzonen_data = deque(maxlen=MAX_PROBLEMZONEN)

# Funktion zum Speichern von GPS-Daten
def save_gps_data(data, filename):
    filename = os.path.join(OUTPUT_DIR, filename)  # Pfad anpassen
    print(f"Speichere GPS-Daten in: {filename}")  # Debug-Ausgabe
    with open(filename, "w") as f:
        json.dump(data, f)

# Funktion zum Speichern von Problemzonen-Daten
def save_problemzonen_data(data):
    filename = os.path.join(OUTPUT_DIR, "problemzonen.json")  # Pfad anpassen
    print(f"Speichere Problemzonen-Daten in: {filename}")  # Debug-Ausgabe
    with open(filename, "w") as f:
        json.dump(list(data), f)  # Konvertiere deque zu Liste für JSON

# Funktion zum Erstellen der Heatmap
def create_heatmap(data, filename, show_path=False):
    print(f"Erstelle Heatmap: {filename}")

    try:
        # Überprüfen, ob Daten vorhanden sind
        if not data:
            print("Keine Daten für Heatmap vorhanden.")
            return

        m = folium.Map(location=MAP_CENTER, zoom_start=20, control_scale=True, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                      attr='Google', name='Google Maps', max_zoom=20, subdomains=['mt0', 'mt1', 'mt2', 'mt3'])

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
        folium.Rectangle(bounds=[(LAT_BOUNDS[0], LON_BOUNDS[0]), (LAT_BOUNDS[1], LON_BOUNDS[1])], color="blue", fill=False).add_to(m)

        m.save(filename)
        print(f"Heatmap gespeichert unter: {filename}")

    except Exception as e:  # Allgemeiner Fehlerbehandlungsblock
        print(f"Fehler beim Erstellen der Heatmap '{filename}': {e}")

# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc, properties=None):
    print("Verbunden mit MQTT Broker, return code:", rc)
    if rc == 0:
        print("Verbindung erfolgreich hergestellt!")
    else:
        print(f"Verbindung fehlgeschlagen, Fehlercode: {rc}")
        print(f"Fehlermeldung: {mqtt.error_string(rc)}")  # Zusätzliche Fehlermeldung
    if MQTT_TOPIC_GPS:  # Überprüfung, ob MQTT_TOPIC_GPS definiert ist
        result_gps = client.subscribe(MQTT_TOPIC_GPS)
        print(f"Abonniert auf Topic: {MQTT_TOPIC_GPS}, Ergebnis: {result_gps}")
    if MQTT_TOPIC_STATUS:
        result_status = client.subscribe(MQTT_TOPIC_STATUS)
        print(f"Abonniert auf Topic: {MQTT_TOPIC_STATUS}, Ergebnis: {result_status}")

def on_message(client, userdata, msg):
    print(f"Nachricht empfangen auf Topic: {msg.topic}")  # Statusmeldung beibehalten
    print(f"Payload: {msg.payload.decode()}")  # Vollständigen Payload ausgeben

    try:
        payload = json.loads(msg.payload.decode())

        if msg.topic == MQTT_TOPIC_GPS:
            print("GPS-Daten empfangen")  # Debug-Ausgabe

            maehvorgang_data.append(payload)
            alle_maehvorgang_data.extend(payload)

            print("Speichere GPS-Daten...")  # Debug-Ausgabe
            save_gps_data(payload, f"maehvorgang_{len(maehvorgang_data)}.json")

            print("Erstelle Heatmaps...")  # Debug-Ausgabe
            create_heatmap([payload], heatmap_filename, True)
            create_heatmap(list(maehvorgang_data), heatmap_10_maehvorgang_filename, False)
            create_heatmap([alle_maehvorgang_data], heatmap_kumuliert_filename, False)

        elif msg.topic == MQTT_TOPIC_STATUS:
            if payload.get("command") == "problem":
                print("Problemdaten empfangen")  # Debug-Ausgabe
                problemzonen_data.append(payload)
                save_problemzonen_data(problemzonen_data)
                create_heatmap([problemzonen_data], problemzonen_heatmap_filename, False)

    except json.JSONDecodeError as e:
        print(f"Fehler beim Decodieren der JSON-Nachricht: {e}")
        print(f"Empfangene Nachricht: {msg.payload.decode()}")
    except Exception as e:  # Allgemeiner Fehlerbehandlungsblock
        print(f"Unerwarteter Fehler in on_message: {e}")
# MQTT-Client erstellen und konfigurieren
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

# Verbindung zum Broker herstellen
try:
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
except ValueError as e:  # WertError für ungültigen Host abfangen
    print(f"Fehler bei der Verbindung zum MQTT-Broker: {e}")
    exit(1)
except (ConnectionRefusedError, socket.timeout) as e:
    print(f"Verbindung zum MQTT-Broker konnte nicht hergestellt werden: {e}")
    # Wiederholungsversuche oder andere Fehlerbehandlungsmaßnahmen implementieren
    while True:
        try:
            client.reconnect()
            print("Reconnected to MQTT Broker")
            break
        except ConnectionRefusedError:
            print("Reconnect failed. Retrying in 5 seconds...")
            time.sleep(5)

# Endlosschleife für MQTT
while True:
    print("MQTT-Schleife läuft...")  # Debug-Ausgabe
    client.loop(timeout=1.0)  # MQTT-Ereignisse verarbeiten
    time.sleep(1)  # Pause zwischen den Schleifendurchläufen