# live_gps_map.py
import logging
import os
import sys
import threading
import json
from pathlib import Path

import paho.mqtt.client as mqtt
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO
import folium # Wird für initiale Karteneinstellungen genutzt

# Importiere Konfiguration aus dem Projekt
try:
    import config
except ImportError:
    print("Fehler: config.py nicht gefunden. Stellen Sie sicher, dass sie im PYTHONPATH liegt.")
    sys.exit(1)

# --- Logging Konfiguration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Globale Variablen ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Wichtig für Flask Sessions/SocketIO
# Verwende eventlet für bessere WebSocket-Performance
socketio = SocketIO(app, async_mode='eventlet')
current_position = {'lat': config.GEO_CONFIG.get("map_center", (0, 0))[0],
                    'lon': config.GEO_CONFIG.get("map_center", (0, 0))[1]} # Startposition
position_lock = threading.Lock() # Für Thread-sicheren Zugriff auf current_position
mqtt_client = None

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc, properties=None):
    """Wird aufgerufen, wenn die Verbindung zum MQTT Broker hergestellt wurde."""
    if rc == 0:
        logger.info(f"Erfolgreich mit MQTT Broker verbunden: {config.MQTT_CONFIG['host']}")
        status_topic = config.MQTT_CONFIG.get("topic_status")
        if status_topic:
            client.subscribe(status_topic)
            logger.info(f"Subscribed auf Topic: {status_topic}")
        else:
            logger.error("MQTT Status Topic ('topic_status') ist nicht in config.py definiert!")
    else:
        logger.error(f"Verbindung zum MQTT Broker fehlgeschlagen mit Code: {rc}")

def on_disconnect(client, userdata, rc, properties=None):
    """Wird aufgerufen, wenn die Verbindung zum MQTT Broker getrennt wird."""
    logger.warning(f"Verbindung zum MQTT Broker getrennt mit Code: {rc}. Versuche erneuten Verbindungsaufbau...")
    # Hier könnte eine Logik zum Wiederverbinden implementiert werden,
    # Paho-MQTT versucht es aber oft schon selbstständig nach loop_start()

def on_message(client, userdata, msg):
    """Wird aufgerufen, wenn eine Nachricht auf einem abonnierten Topic empfangen wird."""
    global current_position
    try:
        payload = msg.payload.decode('utf-8')
        logger.debug(f"Nachricht empfangen auf Topic '{msg.topic}': {payload}")

        # Beispiel-Format: "status,GPS Fix (SPS),9,46.81189983,7.13316450,AGPS: OK (27.7h ago)"
        if msg.topic == config.MQTT_CONFIG.get("topic_status") and payload.startswith("status,"):
            parts = payload.split(',')
            if len(parts) >= 5:
                try:
                    lat = float(parts[3])
                    lon = float(parts[4])

                    # Prüfen, ob Koordinaten gültig erscheinen (optional, aber empfohlen)
                    # Hier könnten die Bounds aus config.py verwendet werden
                    lat_bounds = config.GEO_CONFIG.get("lat_bounds")
                    lon_bounds = config.GEO_CONFIG.get("lon_bounds")
                    valid = True
                    if lat_bounds and not (lat_bounds[0] <= lat <= lat_bounds[1]):
                        logger.warning(f"Ungültige Latitude empfangen: {lat}")
                        valid = False
                    if lon_bounds and not (lon_bounds[0] <= lon <= lon_bounds[1]):
                        logger.warning(f"Ungültige Longitude empfangen: {lon}")
                        valid = False

                    if valid:
                        with position_lock:
                            current_position = {'lat': lat, 'lon': lon}
                        logger.info(f"Neue Position empfangen: Lat={lat}, Lon={lon}")
                        # Sende Update an alle verbundenen Web-Clients
                        socketio.emit('update_position', {'lat': lat, 'lon': lon})
                    else:
                         logger.warning(f"Ignoriere ungültige Koordinaten: Lat={lat}, Lon={lon}")

                except ValueError:
                    logger.warning(f"Konnte Lat/Lon nicht aus Nachricht extrahieren: {payload}")
                except Exception as e:
                    logger.error(f"Fehler beim Verarbeiten der Nachricht: {payload} - {e}", exc_info=True)
            else:
                logger.debug(f"Ignoriere Statusnachricht (falsches Format?): {payload}")
        else:
            logger.debug(f"Ignoriere Nachricht auf anderem Topic oder nicht-Status-Nachricht: {msg.topic}")

    except Exception as e:
        logger.error(f"Fehler in on_message: {e}", exc_info=True)

def setup_mqtt():
    """Konfiguriert und startet den MQTT Client."""
    global mqtt_client
    host = config.MQTT_CONFIG.get("host_lokal") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get("host")
    port = config.MQTT_CONFIG.get("port_lokal") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get("port")
    user = config.MQTT_CONFIG.get("user_local") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get("user")
    password = config.MQTT_CONFIG.get("password_local") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get("password")

    if not host or not port:
        logger.error("MQTT Host oder Port nicht konfiguriert. Bitte config.py prüfen.")
        sys.exit(1)

    client_id = f"live-gps-map-{os.getpid()}"
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    if user and password:
        mqtt_client.username_pw_set(user, password)
        logger.info("MQTT Authentifizierung konfiguriert.")

    try:
        logger.info(f"Versuche Verbindung zu MQTT Broker: {host}:{port}")
        mqtt_client.connect(host, port, 60)
        mqtt_client.loop_start() # Startet einen Hintergrundthread für Netzwerk-Loop und Wiederverbindung
        logger.info("MQTT Client Loop gestartet.")
    except Exception as e:
        logger.error(f"Verbindung zum MQTT Broker fehlgeschlagen: {e}", exc_info=True)
        sys.exit(1)

# --- Flask Routen ---
@app.route('/')
def index():
    """Liefert die Haupt-HTML-Seite mit der Karte."""
    # Verwende folium, um die Kachel-URLs und Optionen einfach zu erhalten
    # Die Karte selbst wird dann in JS mit Leaflet erstellt
    initial_zoom = 20
    max_zoom = config.GEO_CONFIG.get("max_zoom", 22)
    center_lat = config.GEO_CONFIG.get("map_center", (0, 0))[0]
    center_lon = config.GEO_CONFIG.get("map_center", (0, 0))[1]

    # Kachel-Layer Konfiguration (wie in heatmap_generator)
    google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    google_attr = 'Google Satellite'
    osm_tiles_url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
    osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

    with position_lock:
      start_pos = current_position.copy()

    return render_template('live_map.html',
                           initial_lat=start_pos['lat'],
                           initial_lon=start_pos['lon'],
                           initial_zoom=initial_zoom,
                           max_zoom=max_zoom,
                           google_tiles_url=google_tiles_url,
                           google_attr=google_attr,
                           osm_tiles_url=osm_tiles_url,
                           osm_attr=osm_attr)

@app.route('/static/<path:filename>')
def static_files(filename):
    """Liefert statische Dateien (z.B. ein Icon für den Marker)."""
    return send_from_directory('static', filename)


# --- SocketIO Events ---
@socketio.on('connect')
def handle_connect():
    """Wird aufgerufen, wenn sich ein Browser per WebSocket verbindet."""
    logger.info('Web-Client verbunden')
    # Sende die aktuell bekannte Position sofort an den neuen Client
    with position_lock:
        pos = current_position.copy()
    socketio.emit('update_position', pos)

@socketio.on('disconnect')
def handle_disconnect():
    """Wird aufgerufen, wenn die WebSocket-Verbindung getrennt wird."""
    logger.info('Web-Client getrennt')

# --- Hauptteil ---
if __name__ == '__main__':
    # Erstelle benötigte Verzeichnisse, falls nicht vorhanden
    Path("templates").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    # (Optional: Kopiere ein Icon für den Marker nach static/marker-icon.png)

    logger.info("Starte MQTT Client Setup...")
    setup_mqtt()

    port = 5001 # Wähle einen freien Port
    logger.info(f"Starte Flask-SocketIO Server auf http://0.0.0.0:{port}")
    # Verwende socketio.run für korrekten Start mit async_mode
    try:
        socketio.run(app, host='0.0.0.0', port=port, use_reloader=False)
         # use_reloader=False ist wichtig, wenn man Threads wie den MQTT Loop startet
    except KeyboardInterrupt:
        logger.info("Server wird beendet.")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            logger.info("MQTT Client gestoppt und getrennt.")