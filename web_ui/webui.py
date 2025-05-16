# webui.py
import eventlet

eventlet.monkey_patch()

import logging
import os
import sys
import threading
import json
import time  # Für sleep im Thread
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from dotenv import set_key, find_dotenv, dotenv_values

# Importiere psutil
try:
    import psutil

    psutil_available = True
except ImportError:
    psutil_available = False
    logging.warning(
        "psutil nicht gefunden. Systeminformationen sind nicht verfügbar. Installiere mit 'pip install psutil'")

# Importiere pandas und geopy für Statistiken
try:
    import pandas as pd
    import glob
    from geopy.distance import geodesic

    stats_libs_available = True
except ImportError:
    stats_libs_available = False
    logging.warning(
        "pandas oder geopy nicht gefunden. Statistiken sind nicht verfügbar. Installiere mit 'pip install pandas geopy'")

# Füge das übergeordnete Verzeichnis zum Suchpfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
# config importieren, um Standardwerte und das neue Topic zu kennen
import config  # Enthält jetzt auch PI_STATUS_CONFIG

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Flask & SocketIO Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback-sehr-geheim')
app.template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app.static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
socketio = SocketIO(app, async_mode='eventlet', ping_timeout=20, ping_interval=10)

# --- Globale Variablen & Sperren ---
current_status = {
    "lat": config.GEO_CONFIG.get("map_center", (0, 0))[0],
    "lon": config.GEO_CONFIG.get("map_center", (0, 0))[1],
    "status_text": "Warte auf Daten...",
    "satellites": 0,
    "agps_status": "Unbekannt",
    "is_recording": False,
    "mower_status": "Unbekannt",
    "last_update": "Noch keine Daten"
}
status_lock = threading.Lock()
mqtt_client = None

# Globale Variable für Systemstatus (Webserver)
current_system_stats = {
    "cpu_load": 0.0,
    "ram_usage": 0.0,
    "cpu_temp": None
}
system_stats_lock = threading.Lock()
system_stats_thread = None
stop_system_stats_thread = threading.Event()

# NEU: Globale Variable für Pi-Status
current_pi_status = {
    "temperature": None,
    "last_update": "Noch keine Daten"
}
pi_status_lock = threading.Lock()


# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc, properties=None):
    global cleaned_pi_status_topic # Stores the topic used for subscription
    """Wird aufgerufen, wenn die Verbindung zum MQTT Broker hergestellt wurde."""
    if rc == 0:
        logger.info(f"Erfolgreich mit MQTT Broker verbunden")
        mqtt_config_dict = getattr(config, "MQTT_CONFIG", {})
        pi_status_config_dict = getattr(config, "PI_STATUS_CONFIG", {})

        # Bisherige Topics abonnieren
        status_topic = mqtt_config_dict.get("topic_status")
        if status_topic:
            client.subscribe(status_topic)
            logger.info(f"Abonniert auf Topic: {status_topic}")
        else:
            logger.error("MQTT Status Topic ('topic_status') ist nicht in config.py definiert!")

        gps_topic = mqtt_config_dict.get("topic_gps")
        if gps_topic:
            client.subscribe(gps_topic)
            logger.info(f"Abonniert auf Topic: {gps_topic}")

        # NEU: Pi-Status Topic abonnieren
        pi_status_topic_raw = pi_status_config_dict.get("topic_pi_status")
        cleaned_pi_status_topic = None # Initialisieren
        if pi_status_topic_raw:
            # Bereinige den Topic-String, um Kommentare oder überflüssige Leerzeichen zu entfernen.
            cleaned_pi_status_topic = str(pi_status_topic_raw).split("#")[0].strip()

            if cleaned_pi_status_topic:  # Prüfen, ob nach der Bereinigung nicht leer
                try:
                    client.subscribe(cleaned_pi_status_topic)
                    logger.info(f"Abonniert auf Pi Status Topic: {cleaned_pi_status_topic}")
                    if pi_status_topic_raw != cleaned_pi_status_topic:
                        logger.warning(f"Ursprünglicher Pi Status Topic '{pi_status_topic_raw}' wurde vor dem Abonnement zu '{cleaned_pi_status_topic}' bereinigt. "
                                       "Bitte den Wert in der .env Datei oder config.py korrigieren.")
                except ValueError as ve:
                    logger.error(f"ValueError beim Abonnieren des Pi Status Topics '{cleaned_pi_status_topic}': {ve}. "
                                 "Der Topic könnte ungültig sein (z.B. Nullzeichen, falsch formatierte Wildcards).")
                except Exception as e:
                    logger.error(f"Unerwarteter Fehler beim Abonnieren des Pi Status Topics '{cleaned_pi_status_topic}': {e}", exc_info=True)
            else:
                logger.warning(f"Pi Status Topic ('{pi_status_topic_raw}') wurde nach Bereinigung zu einem leeren String. Abonnement übersprungen. cleaned_pi_status_topic wird None.")
                cleaned_pi_status_topic = None # Sicherstellen, dass es None ist, wenn leer
        else:
            logger.warning("Pi Status Topic ('topic_pi_status') ist nicht in config.py definiert oder ist leer!")
        # --- ENDE NEU ---
    else:
        logger.error(f"Verbindung zum MQTT Broker fehlgeschlagen mit Code: {rc}")


def on_disconnect(client, userdata, flags, rc, properties=None):
    """Wird aufgerufen, wenn die Verbindung zum MQTT Broker getrennt wird."""
    # Das 'flags'-Argument wird von paho-mqtt V2 übergeben, auch wenn wir es hier nicht explizit verwenden.
    # rc ist der reason_code.
    logger.warning(
        f"Verbindung zum MQTT Broker getrennt. Flags: {flags}, Reason Code: {rc}. Paho-MQTT versucht automatischen Reconnect.")


def on_message(client, userdata, msg):
    """Wird aufgerufen, wenn eine Nachricht auf einem abonnierten Topic empfangen wird.""" # noqa: E501
    global current_status, current_pi_status  # NEU: current_pi_status hinzugefügt
    try:
        payload = msg.payload.decode('utf-8')
        logger.debug(f"Nachricht empfangen auf Topic '{msg.topic}': {payload}")
        mqtt_config_dict = getattr(config, "MQTT_CONFIG", {})

        # --- Verarbeite Status-Nachrichten vom Status-Topic ---
        if msg.topic == mqtt_config_dict.get("topic_status"):
            if payload.startswith("status,"):
                parts = payload.split(',')
                if len(parts) >= 5:
                    try:
                        status_text = parts[1]
                        satellites = int(parts[2]) if parts[2].isdigit() else 0 # Satellites should be convertible even without fix
                        agps_status = parts[5] if len(parts) > 5 else "Unbekannt"
                        mower_status_text = parts[6] if len(parts) > 6 else "Unbekannt"

                        # --- NEU: Prüfen, ob Lat/Lon-Werte vorhanden sind, bevor konvertiert wird ---
                        lat_str = parts[3]
                        lon_str = parts[4]
                        # Initialisiere lat_val und lon_val als None
                        lat_val = None
                        lon_val = None

                        # Verarbeite Lat/Lon nur, wenn sie nicht leer und nicht "N/A" sind
                        if lat_str and lat_str.lower() != 'n/a' and \
                           lon_str and lon_str.lower() != 'n/a':
                            try:
                                temp_lat = float(lat_str)
                                temp_lon = float(lon_str)
                                # Prüfe, ob innerhalb der definierten Grenzen (falls konfiguriert)
                                lat_bounds = config.GEO_CONFIG.get("lat_bounds")
                                lon_bounds = config.GEO_CONFIG.get("lon_bounds")
                                if (not lat_bounds or (lat_bounds[0] <= temp_lat <= lat_bounds[1])) and \
                                   (not lon_bounds or (lon_bounds[0] <= temp_lon <= lon_bounds[1])):
                                    lat_val = temp_lat
                                    lon_val = temp_lon
                                else:
                                    logger.warning(f"Koordinaten außerhalb der Grenzen: Lat '{temp_lat}', Lon '{temp_lon}'")
                            except ValueError:
                                logger.warning(f"Konnte Lat/Lon nicht in Float konvertieren: '{lat_str}', '{lon_str}'")

                        from datetime import datetime
                        with status_lock:
                            current_status.update({
                                'status_text': status_text,
                                'satellites': satellites,
                                'agps_status': agps_status,
                                'mower_status': mower_status_text,
                                'last_update': datetime.now().strftime("%H:%M:%S"),
                                'lat': lat_val,  # Aktualisiere mit lat_val (kann None sein)
                                'lon': lon_val   # Aktualisiere mit lon_val (kann None sein)
                            })

                        socketio.emit('status_update', current_status)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Konnte Daten nicht aus Status-Nachricht extrahieren: {payload}, Fehler: {e}")
                    except Exception as e:
                        logger.error(f"Fehler beim Verarbeiten der Status-Nachricht: {payload} - {e}", exc_info=True)
                else:
                    logger.debug(f"Ignoriere Statusnachricht (falsches Format?): {payload}")

            # --- NEU: Aufzeichnung Status explizit behandeln ---
            elif payload == "recording started":
                logger.info("Aufzeichnungsstatus von MQTT empfangen: Gestartet")
                with status_lock:
                    if not current_status['is_recording']:  # Nur ändern, wenn nicht schon True
                        current_status['is_recording'] = True
                        # Sende sofort ein Update an die UI
                        socketio.emit('status_update', current_status)
            elif payload == "recording stopped":
                logger.info("Aufzeichnungsstatus von MQTT empfangen: Gestoppt")
                with status_lock:
                    if current_status['is_recording']:  # Nur ändern, wenn nicht schon False
                        current_status['is_recording'] = False
                        # Sende sofort ein Update an die UI
                        socketio.emit('status_update', current_status)
            # --- ENDE NEU ---

            elif payload.startswith("problem,"):
                logger.debug(f"Empfangene Problem-Nachricht (wird hier nicht weiter verarbeitet): {payload}")
            else:
                logger.debug(f"Unbekannte Nachricht auf Status-Topic: {payload}")

        # --- Verarbeite GPS-Nachrichten (falls nötig) ---
        elif msg.topic == mqtt_config_dict.get("topic_gps"):
            logger.debug(f"Nachricht auf GPS-Topic (wird hier nicht weiter verarbeitet): {payload}")

        # --- NEU: Verarbeite Pi-Status Nachrichten ---
        # Verwende das global bereinigte Topic für den Vergleich
        elif cleaned_pi_status_topic and msg.topic == cleaned_pi_status_topic:
            try:
                # Versuche, den Payload als Fließkommazahl zu interpretieren
                temp_value = float(payload)
                from datetime import datetime
                with pi_status_lock:
                    current_pi_status['temperature'] = round(temp_value, 1)
                    current_pi_status['last_update'] = datetime.now().strftime("%H:%M:%S")
                # Sende Update an alle verbundenen Clients über neues Event
                socketio.emit('pi_status_update', current_pi_status)
                logger.debug(f"Pi-Temperatur aktualisiert: {current_pi_status['temperature']}°C")
            except ValueError:
                logger.warning(f"Konnte Pi-Status-Payload nicht als Zahl interpretieren: {payload}")
            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten der Pi-Status-Nachricht: {payload} - {e}", exc_info=True)
        # --- ENDE NEU ---

    except Exception as e:
        logger.error(f"Fehler in on_message: {e}", exc_info=True)

# Globale Variable für das bereinigte Pi-Status-Topic
# Wird in on_connect gesetzt und in on_message verwendet.
cleaned_pi_status_topic = None


# --- setup_mqtt (unverändert) ---
def setup_mqtt():
    # ... (Code wie vorher) ...
    global mqtt_client
    mqtt_config_dict = getattr(config, "MQTT_CONFIG", {})
    rec_config_dict = getattr(config, "REC_CONFIG", {})

    is_test_mode = rec_config_dict.get("test_mode", False) # Default zu False, falls REC_CONFIG oder test_mode fehlt
    host = mqtt_config_dict.get("host_lokal") if is_test_mode else mqtt_config_dict.get("host")
    port = mqtt_config_dict.get("port_lokal") if is_test_mode else mqtt_config_dict.get("port")
    user = mqtt_config_dict.get("user_local") if is_test_mode else mqtt_config_dict.get("user")
    password = mqtt_config_dict.get("password_local") if is_test_mode else mqtt_config_dict.get("password")

    if not host or not port:
        logger.error("MQTT Host oder Port nicht konfiguriert. Bitte config.py prüfen.")
        return False

    client_id = f"worx-webui-{os.getpid()}"
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
        mqtt_client.loop_start()
        logger.info("MQTT Client Loop gestartet.")
        return True
    except Exception as e:
        logger.error(f"Verbindung zum MQTT Broker fehlgeschlagen: {e}", exc_info=True)
        return False


# --- Hilfsfunktionen (get_available_heatmaps, get_problem_zones, get_editable_config unverändert) ---
def get_available_heatmaps():
    # ... (Code wie vorher) ...
    heatmap_dir = os.path.join(project_root, 'heatmaps')
    heatmaps = []
    try:
        filenames = sorted(os.listdir(heatmap_dir))
        for filename in filenames:
            if filename.endswith('.html'):
                name = os.path.splitext(filename)[0]
                png_exists = os.path.exists(os.path.join(heatmap_dir, f"{name}.png"))
                heatmaps.append({
                    'id': name,
                    'name': name.replace('_', ' ').title(),
                    'html_path': f"/heatmaps/{filename}",
                    'png_path': f"/heatmaps/{name}.png" if png_exists else None
                })
    except FileNotFoundError:
        logger.warning(f"Heatmap-Verzeichnis nicht gefunden: {heatmap_dir}")
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Heatmaps: {e}")
    return heatmaps


def get_problem_zones():
    # ... (Code wie vorher) ...
    problem_config_dict = getattr(config, "PROBLEM_CONFIG", {})
    problem_file_name = problem_config_dict.get("problem_json", "data/problemzonen.json") # Default mit data/
    problem_file = os.path.join(project_root, problem_file_name)
    if os.path.exists(problem_file):
        try:
            with open(problem_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Fehler beim Parsen der Problemzonen-JSON-Datei ({problem_file}): {e}")
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Problemzonen ({problem_file}): {e}")
    else:
        logger.warning(f"Problemzonen-Datei nicht gefunden: {problem_file}")
    return []


def get_editable_config():
    # ... (Code wie vorher) ...
    env_values = dotenv_values(find_dotenv())
    heatmap_config_dict = getattr(config, "HEATMAP_CONFIG", {})
    geo_config_dict = getattr(config, "GEO_CONFIG", {})
    rec_config_dict = getattr(config, "REC_CONFIG", {})

    def get_config_value(env_key, default, value_type=str):
        value_str = env_values.get(env_key)
        if value_str is None:
            # Verwende die abgesicherten Dictionaries
            if env_key == 'HEATMAP_RADIUS':
                default = heatmap_config_dict.get('heatmap_aktuell', {}).get('radius', 5)
            elif env_key == 'HEATMAP_BLUR':
                default = heatmap_config_dict.get('heatmap_aktuell', {}).get('blur', 10)
            elif env_key == 'HEATMAP_GENERATE_PNG':
                default = heatmap_config_dict.get('heatmap_aktuell', {}).get('generate_png', False)
            elif env_key == 'GEO_ZOOM_START':
                default = geo_config_dict.get('zoom_start', 19) # Konsistent mit live_view Default
            elif env_key == 'GEO_MAX_ZOOM':
                default = geo_config_dict.get('max_zoom', 22)
            elif env_key == 'REC_STORAGE_INTERVAL':
                default = rec_config_dict.get('storage_interval', 1)
            elif env_key == 'TEST_MODE':
                default = rec_config_dict.get('test_mode', False)
            else: # Fallback, falls ein neuer Schlüssel ohne explizite config-Logik hier landet
                pass # default bleibt der übergebene default
            value_str = str(default)
        try:
            if value_type == bool:
                return value_str.lower() in ['true', '1', 'yes', 'on']
            elif value_type == int:
                return int(value_str)
            elif value_type == float:
                return float(value_str)
            return str(value_str)
        except (ValueError, TypeError):
            logger.warning(
                f"Konnte Wert für {env_key} ('{value_str}') nicht nach {value_type} konvertieren, verwende Standard: {default}")
            return default

    return {
        'HEATMAP': {
            'HEATMAP_RADIUS': get_config_value('HEATMAP_RADIUS', 5, int),
            'HEATMAP_BLUR': get_config_value('HEATMAP_BLUR', 10, int),
            'HEATMAP_GENERATE_PNG': get_config_value('HEATMAP_GENERATE_PNG', False, bool),
        },
        'GEO': {
            'GEO_ZOOM_START': get_config_value('GEO_ZOOM_START', 19, int), # Konsistenter Default
            # Keep default here for consistency if needed elsewhere
            'GEO_MAX_ZOOM': get_config_value('GEO_MAX_ZOOM', 22, int),
        },
        'REC': {
            'REC_STORAGE_INTERVAL': get_config_value('REC_STORAGE_INTERVAL', 1, int),
            'TEST_MODE': get_config_value('TEST_MODE', False, bool),
        },
        # HINWEIS: Der env_key für TEST_MODE in get_config_value ist 'TEST_MODE'.
        # In save_config wird 'rec_test_mode' aus dem Formular auf die .env Variable 'TEST_MODE' gemappt. Das ist korrekt.
    }


# --- system_stats_updater (unverändert) ---
def system_stats_updater():
    # ... (Code wie vorher) ...
    global current_system_stats
    if not psutil_available:
        logger.warning("psutil nicht verfügbar, Systemstatistiken können nicht gesammelt werden.")
        return

    logger.info("Starte Thread für Systemstatistiken...")
    while not stop_system_stats_thread.is_set():
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            temp = None
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                for name, entries in temps.items():
                    for entry in entries:
                        if 'current' in entry._fields and (
                                'core' in name.lower() or 'cpu' in name.lower() or 'package' in entry.label.lower()):
                            temp = entry.current
                            break
                    if temp is not None: break

            with system_stats_lock:
                current_system_stats = {
                    "cpu_load": cpu, "ram_usage": ram,
                    "cpu_temp": round(temp, 1) if temp is not None else None
                }
            socketio.emit('system_update', current_system_stats)
            logger.debug(f"Systemstatistiken gesendet: {current_system_stats}")
        except Exception as e: # Bessere Fehlerdiagnose mit exc_info=True
            logger.error(f"Fehler im Systemstatistiken-Thread: {e}", exc_info=True)
        stop_system_stats_thread.wait(5.0)
    logger.info("Thread für Systemstatistiken beendet.")


# --- Flask Routen ---
@app.route('/')
def index():
    """Hauptseite / Dashboard"""
    with status_lock:
        status_data = current_status.copy()
    with system_stats_lock:
        system_data = current_system_stats.copy()
    # NEU: Pi-Status holen
    with pi_status_lock:
        pi_data = current_pi_status.copy()
    heatmaps = get_available_heatmaps()
    current_heatmap_html = None
    for hm in heatmaps:
        if hm['id'] == 'heatmap_aktuell':
            current_heatmap_html = hm['html_path']
            break

    return render_template('index.html',
                           status=status_data,
                           system=system_data,
                           pi_status=pi_data,  # NEU: Pi-Status übergeben
                           heatmaps=heatmaps[:3],
                           current_heatmap_html=current_heatmap_html,
                           mqtt_connected=mqtt_client is not None and mqtt_client.is_connected())


# --- /maps, /heatmaps/<filename>, /config, /config/save (unverändert) ---
@app.route('/maps')
def maps():
    # ... (Code wie vorher) ...
    heatmaps = get_available_heatmaps()
    selected = request.args.get('map', '')
    if not selected or not any(h['id'] == selected for h in heatmaps):
        selected = heatmaps[0]['id'] if heatmaps else ''
    template_path = os.path.join(app.template_folder, 'maps.html')
    if not os.path.exists(template_path):
        logger.error(f"Template 'maps.html' nicht gefunden in {app.template_folder}")
        return "Fehler: Template 'maps.html' nicht gefunden.", 500
    return render_template('maps.html', heatmaps=heatmaps, selected=selected)


@app.route('/heatmaps/<path:filename>')
def serve_heatmap(filename):
    # ... (Code wie vorher) ...
    heatmap_dir = os.path.join(project_root, 'heatmaps')
    if '..' in filename or filename.startswith('/'): return "Ungültiger Dateiname", 400
    return send_from_directory(heatmap_dir, filename)


@app.route('/config')
def config_page():
    # ... (Code wie vorher) ...
    editable_config = get_editable_config()
    env_values = dotenv_values(find_dotenv())
    info = {
        'mqtt_host': env_values.get("MQTT_HOST", "N/A"),
        'mqtt_port': env_values.get("MQTT_PORT", "N/A"),
        'mqtt_topic_status': env_values.get("MQTT_TOPIC_STATUS", "N/A"),
        'mqtt_topic_gps': env_values.get("MQTT_TOPIC_GPS", "N/A"),
        'mqtt_topic_control': env_values.get("MQTT_TOPIC_CONTROL", "N/A"),
        'test_mode': "Aktiv" if str(env_values.get("TEST_MODE")).lower() == 'true' else "Inaktiv",
        'assist_now': "Aktiviert" if str(env_values.get("ASSIST_NOW_ENABLED")).lower() == 'true' else "Deaktiviert",
        'gps_serial_port': env_values.get("GPS_SERIAL_PORT", "N/A"),
    }
    template_path = os.path.join(app.template_folder, 'config.html')
    if not os.path.exists(template_path):
        logger.error(f"Template 'config.html' nicht gefunden in {app.template_folder}")
        return "Fehler: Template 'config.html' nicht gefunden.", 500
    return render_template('config.html', config=editable_config, info=info)


@app.route('/config/save', methods=['POST'])
def save_config():
    # ... (Code wie vorher) ...
    try:
        data = request.form.to_dict()
        logger.info(f"Empfangene Konfigurationsänderungen: {data}")
        env_file_path = find_dotenv()
        if not env_file_path:
            env_file_path = os.path.join(project_root, '.env')
            logger.warning(f".env Datei nicht gefunden, versuche sie unter: {env_file_path} zu erstellen/verwenden.")
            if not os.path.exists(env_file_path): Path(env_file_path).touch()

        allowed_keys = {
            'heatmap_radius': 'HEATMAP_RADIUS', 'heatmap_blur': 'HEATMAP_BLUR',
            'heatmap_generate_png': 'HEATMAP_GENERATE_PNG', 'geo_zoom_start': 'GEO_ZOOM_START',
            'geo_max_zoom': 'GEO_MAX_ZOOM', 'rec_storage_interval': 'REC_STORAGE_INTERVAL',
            'rec_test_mode': 'TEST_MODE',
        }
        saved_keys, error_messages = [], []
        for form_key, form_value in data.items():
            if form_key in allowed_keys:
                env_key = allowed_keys[form_key]
                is_checkbox = form_key in ['heatmap_generate_png', 'rec_test_mode']
                env_value = 'True' if is_checkbox and form_value == 'on' else (
                    'False' if is_checkbox else str(form_value).strip())
                success = set_key(env_file_path, env_key, env_value, quote_mode="never")
                if success:
                    logger.info(
                        f"Schlüssel '{env_key}' in '{os.path.basename(env_file_path)}' auf '{env_value}' gesetzt.")
                    saved_keys.append(env_key)
                else:
                    error_msg = f"Fehler beim Setzen von Schlüssel '{env_key}'."
                    logger.error(error_msg)
                    error_messages.append(error_msg)
            else:
                logger.warning(f"Ignoriere nicht erlaubten Konfigurationsschlüssel: {form_key}")

        if error_messages: return jsonify({"success": False, "message": "Fehler:\n" + "\n".join(error_messages)}), 500
        if not saved_keys: return jsonify({"success": False, "message": "Keine gültigen Parameter empfangen."}), 400

        message = (f"Konfiguration aktualisiert ({', '.join(saved_keys)}). Neustart erforderlich.")
        return jsonify({"success": True, "message": message})

    except Exception as e:
        logger.error(f"Fehler beim Speichern der Konfiguration: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {str(e)}"}), 500


# --- /stats (Angepasst für Durchschnittswerte) ---
@app.route('/stats')
def stats():
    """Statistikseite - Lädt und berechnet Statistiken aus CSV-Dateien."""
    problem_zones = get_problem_zones()
    recordings_dir = os.path.join(project_root, 'recordings')
    total_recordings = 0
    total_distance_km = 0.0
    total_duration_min = 0.0
    all_satellites = []
    avg_satellites = 0.0
    # NEU: Variablen für Durchschnittswerte
    avg_distance_km = 0.0
    avg_duration_min = 0.0

    if not stats_libs_available:
        logger.error("Statistik-Bibliotheken (pandas, geopy) nicht verfügbar.")
        stats_data = {
            'total_recordings': 'N/A', 'total_distance': 'N/A', 'total_time': 'N/A',
            'avg_satellites': 'N/A', 'problem_zones_count': len(problem_zones),
            'avg_distance': 'N/A', 'avg_duration': 'N/A'  # NEU
        }
    else:
        try:
            csv_files = glob.glob(os.path.join(recordings_dir, '*.csv'))
            total_recordings = len(csv_files)

            if total_recordings > 0:
                for csv_file in csv_files:
                    try:
                        df = pd.read_csv(csv_file, parse_dates=['timestamp'], on_bad_lines='skip')
                        df.dropna(subset=['timestamp', 'latitude', 'longitude', 'satellites'], inplace=True)

                        # Benötigen mind. 2 Punkte für Distanz/Dauer
                        if not df.empty and len(df) > 1:
                            # Distanzberechnung
                            points = list(zip(df['latitude'], df['longitude']))
                            distance_m = 0
                            for i in range(len(points) - 1):
                                try:
                                    distance_m += geodesic(points[i], points[i + 1]).meters
                                except ValueError:
                                    logger.warning(
                                        f"Ungültige Koordinaten in {csv_file} bei Index {i}, überspringe Distanzsegment.")
                            total_distance_km += distance_m / 1000.0

                            # Dauerberechnung
                            duration = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
                            duration_minutes = duration.total_seconds() / 60.0
                            total_duration_min += duration_minutes

                            # Satelliten sammeln
                            all_satellites.extend(df['satellites'].tolist())
                        elif not df.empty and len(df) <= 1:
                            logger.warning(
                                f"CSV-Datei {csv_file} hat zu wenige gültige Punkte ({len(df)}) für Distanz/Dauer-Berechnung.")


                    except pd.errors.EmptyDataError:
                        logger.warning(f"CSV-Datei {csv_file} ist leer oder konnte nicht gelesen werden.")
                    except Exception as e:
                        logger.error(f"Fehler beim Verarbeiten von {csv_file}: {e}", exc_info=False)

                # Durchschnittliche Satellitenanzahl berechnen
                if all_satellites:
                    valid_sats = [float(s) for s in all_satellites if
                                  isinstance(s, (int, float, str)) and str(s).replace('.', '', 1).isdigit()]
                    if valid_sats:
                        avg_satellites = sum(valid_sats) / len(valid_sats)

                # NEU: Durchschnittswerte berechnen (nur wenn Aufnahmen vorhanden sind)
                if total_recordings > 0:
                    avg_distance_km = total_distance_km / total_recordings
                    avg_duration_min = total_duration_min / total_recordings

        except Exception as e:
            logger.error(f"Fehler beim Laden der Statistiken: {e}", exc_info=True)
            # Setze Daten auf 'Fehler' im Fehlerfall
            total_recordings, total_distance_km, total_duration_min, avg_satellites = 'Fehler', 'Fehler', 'Fehler', 'Fehler'
            avg_distance_km, avg_duration_min = 'Fehler', 'Fehler'  # NEU

        stats_data = {
            'total_recordings': total_recordings,
            'total_distance': total_distance_km,
            'total_time': round(total_duration_min) if isinstance(total_duration_min,
                                                                  (int, float)) else total_duration_min,
            'avg_satellites': avg_satellites,
            'problem_zones_count': len(problem_zones),
            # NEU: Durchschnittswerte hinzufügen
            'avg_distance': avg_distance_km,
            'avg_duration': avg_duration_min
        }

    template_path = os.path.join(app.template_folder, 'stats.html')
    if not os.path.exists(template_path):
        logger.error(f"Template 'stats.html' nicht gefunden in {app.template_folder}")
        return "Fehler: Template 'stats.html' nicht gefunden.", 500

    return render_template('stats.html',
                           stats=stats_data,
                           problem_zones=problem_zones)


# --- /control (Angepasst) ---
@app.route('/control', methods=['POST'])
def control():
    """Empfängt und verarbeitet Steuerbefehle."""
    try:
        data = request.get_json()
        if not data or 'command' not in data: return jsonify({"success": False, "message": "'command' fehlt."}), 400
        command = data['command']
        mqtt_config_dict = getattr(config, "MQTT_CONFIG", {})

        if not mqtt_client or not mqtt_client.is_connected(): return jsonify( # noqa: E501
            {"success": False, "message": "MQTT nicht verbunden"}), 503
        control_topic = mqtt_config_dict.get("topic_control")
        if not control_topic: return jsonify({"success": False, "message": "Kontroll-Topic nicht konfiguriert"}), 500
        command_map = {'start_recording': 'START_REC', 'stop_recording': 'STOP_REC',
                       'generate_heatmaps': 'GENERATE_HEATMAPS', 'shutdown': 'SHUTDOWN'}
        message = command_map.get(command)
        if message:
            try:
                # --- ÄNDERUNG: Status nicht mehr *hier* sofort ändern ---
                # Entferne die folgenden Zeilen:
                # if command == 'start_recording':
                #     with status_lock: current_status['is_recording'] = True
                # elif command == 'stop_recording':
                #     with status_lock: current_status['is_recording'] = False
                # --- ENDE ÄNDERUNG ---

                mqtt_client.publish(control_topic, message)
                logger.info(f"Steuerbefehl '{message}' an Topic '{control_topic}' gesendet.")

                # --- ÄNDERUNG: Kein sofortiges Socket.IO Update mehr von hier ---
                # Entferne die folgende Zeile:
                # socketio.emit('status_update', current_status)
                # --- ENDE ÄNDERUNG ---

                return jsonify({"success": True, "message": f"Befehl '{command}' gesendet."})
            except Exception as e:
                logger.error(f"Fehler beim Senden des MQTT-Befehls '{message}': {e}", exc_info=True)
                return jsonify({"success": False, "message": f"MQTT Sende-Fehler: {str(e)}"}), 500
        else:
            logger.warning(f"Unbekannter Steuerbefehl empfangen: {command}")
            return jsonify({"success": False, "message": f"Unbekannter Befehl: {command}"}), 400
    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten des Steuerbefehls: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {str(e)}"}), 500


# --- /live (Angepasst für Zoom) ---
@app.route('/live')
def live_view():
    """Live-Kartenansicht"""
    with status_lock: status_data = current_status.copy()
    geo_config_dict = getattr(config, "GEO_CONFIG", {})
    map_config = {
        'center_lat': status_data['lat'],
        'center_lon': status_data['lon'],
        # Hier den Standardwert (die 15) ändern, falls 'zoom_start' in config.py nicht existiert
        'zoom': geo_config_dict.get('zoom_start', 19),
        'max_zoom': geo_config_dict.get('max_zoom', 22),
        'osm_tiles': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'osm_attr': '&copy; <a href="https://osm.org/copyright">OSM</a> contributors',
        'satellite_tiles': 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        'satellite_attr': 'Google Satellite'
    }
    template_path = os.path.join(app.template_folder, 'live.html')
    if not os.path.exists(template_path):
        logger.error(f"Template 'live.html' nicht gefunden in {app.template_folder}")
        return "Fehler: Template 'live.html' nicht gefunden.", 500
    return render_template('live.html', status=status_data, map_config=map_config)


# --- SocketIO Events ---
@socketio.on('connect')
def handle_connect():
    """Wird aufgerufen, wenn sich ein Browser per WebSocket verbindet."""
    logger.info(f'Web-Client verbunden (SID: {request.sid})')
    # Sende den aktuellen Status sofort
    with status_lock: socketio.emit('status_update', current_status, room=request.sid)
    # Sende aktuellen Systemstatus (Webserver)
    with system_stats_lock: socketio.emit('system_update', current_system_stats, room=request.sid)
    # NEU: Sende aktuellen Pi-Status
    with pi_status_lock: socketio.emit('pi_status_update', current_pi_status, room=request.sid)


@socketio.on('disconnect')
def handle_disconnect():
    """Wird aufgerufen, wenn die WebSocket-Verbindung getrennt wird."""
    logger.info(f'Web-Client getrennt (SID: {request.sid})')


# --- Start ---
if __name__ == '__main__':
    logger.info("Worx GPS WebUI wird gestartet...")
    if setup_mqtt():
        logger.info("MQTT-Verbindung erfolgreich hergestellt.")
    else:
        logger.warning("MQTT-Verbindung konnte nicht hergestellt werden. WebUI läuft ohne MQTT-Updates.")

    # Starte den Systemstatistiken-Thread (Webserver)
    if psutil_available:
        system_stats_thread = threading.Thread(target=system_stats_updater, daemon=True)
        system_stats_thread.start()

    port = int(os.getenv('FLASK_PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']

    logger.info(f"Starte Flask-SocketIO WebUI auf http://0.0.0.0:{port} (Debug: {debug_mode})")
    try:
        socketio.run(app, host='0.0.0.0', port=port, use_reloader=False, debug=debug_mode)
    except KeyboardInterrupt:
        logger.info("Server wird durch Benutzer beendet.")
    except Exception as e:
        logger.error(f"Fehler beim Starten des Servers: {e}", exc_info=True)
    finally:
        logger.info("Server wird heruntergefahren...")
        stop_system_stats_thread.set()
        if system_stats_thread:
            logger.info("Warte auf Beendigung des Systemstatistiken-Threads...")
            system_stats_thread.join(timeout=2.0)
        if mqtt_client:
            try:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
                logger.info("MQTT Client gestoppt und getrennt.")
            except Exception as e:
                logger.error(f"Fehler beim Trennen des MQTT Clients: {e}")
        logger.info("WebUI beendet.")
