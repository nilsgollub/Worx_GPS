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
    """Wird aufgerufen, wenn die Verbindung zum MQTT Broker hergestellt wurde."""
    if rc == 0:
        logger.info(f"Erfolgreich mit MQTT Broker verbunden")
        # Bisherige Topics abonnieren
        status_topic = config.MQTT_CONFIG.get("topic_status")
        if status_topic:
            client.subscribe(status_topic)
            logger.info(f"Abonniert auf Topic: {status_topic}")
        else:
            logger.error("MQTT Status Topic ('topic_status') ist nicht in config.py definiert!")
        gps_topic = config.MQTT_CONFIG.get("topic_gps")
        if gps_topic:
            client.subscribe(gps_topic)
            logger.info(f"Abonniert auf Topic: {gps_topic}")

        # NEU: Pi-Status Topic abonnieren
        pi_status_topic = config.PI_STATUS_CONFIG.get("topic_pi_status")
        if pi_status_topic:
            client.subscribe(pi_status_topic)
            logger.info(f"Abonniert auf Topic: {pi_status_topic}")
        else:
            logger.warning("Pi Status Topic ('topic_pi_status') ist nicht in config.py definiert!")
            # --- ENDE NEU ---
    else:
        logger.error(f"Verbindung zum MQTT Broker fehlgeschlagen mit Code: {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    """Wird aufgerufen, wenn die Verbindung zum MQTT Broker getrennt wird."""
    logger.warning(f"Verbindung zum MQTT Broker getrennt mit Code: {rc}. Paho-MQTT versucht automatischen Reconnect.")


def on_message(client, userdata, msg):
    """Wird aufgerufen, wenn eine Nachricht auf einem abonnierten Topic empfangen wird."""
    global current_status, current_pi_status  # NEU: current_pi_status hinzugefügt
    try:
        payload = msg.payload.decode('utf-8')
        logger.debug(f"Nachricht empfangen auf Topic '{msg.topic}': {payload}")

        # --- Verarbeite Status-Nachrichten vom Status-Topic ---
        if msg.topic == config.MQTT_CONFIG.get("topic_status"):
            if payload.startswith("status,"):
                parts = payload.split(',')
                if len(parts) >= 5:
                    try:
                        status_text = parts[1]
                        satellites = int(parts[2]) if parts[2].isdigit() else 0
                        lat = float(parts[3])
                        lon = float(parts[4])
                        agps_status = parts[5] if len(parts) > 5 else "Unbekannt"
                        mower_status_text = parts[6] if len(parts) > 6 else "Unbekannt"

                        lat_bounds = config.GEO_CONFIG.get("lat_bounds")
                        lon_bounds = config.GEO_CONFIG.get("lon_bounds")
                        valid = True
                        if lat_bounds and not (lat_bounds[0] <= lat <= lat_bounds[1]): valid = False
                        if lon_bounds and not (lon_bounds[0] <= lon <= lon_bounds[1]): valid = False

                        if valid:
                            from datetime import datetime
                            with status_lock:
                                current_status.update({
                                    'lat': lat, 'lon': lon, 'status_text': status_text,
                                    'satellites': satellites, 'agps_status': agps_status,
                                    'mower_status': mower_status_text,
                                    'last_update': datetime.now().strftime("%H:%M:%S")
                                })
                            socketio.emit('status_update', current_status)
                        else:
                            logger.warning(f"Ignoriere ungültige Koordinaten: Lat={lat}, Lon={lon}")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Konnte Daten nicht aus Status-Nachricht extrahieren: {payload}, Fehler: {e}")
                    except Exception as e:
                        logger.error(f"Fehler beim Verarbeiten der Status-Nachricht: {payload} - {e}", exc_info=True)
                else:
                    logger.debug(f"Ignoriere Statusnachricht (falsches Format?): {payload}")
            elif payload.startswith("problem,"):
                logger.debug(f"Empfangene Problem-Nachricht (wird hier nicht weiter verarbeitet): {payload}")
            else:
                logger.debug(f"Unbekannte Nachricht auf Status-Topic: {payload}")

        # --- Verarbeite GPS-Nachrichten (falls nötig) ---
        elif msg.topic == config.MQTT_CONFIG.get("topic_gps"):
            logger.debug(f"Nachricht auf GPS-Topic (wird hier nicht weiter verarbeitet): {payload}")

        # --- NEU: Verarbeite Pi-Status Nachrichten ---
        elif msg.topic == config.PI_STATUS_CONFIG.get("topic_pi_status"):
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


# --- setup_mqtt (unverändert) ---
def setup_mqtt():
    # ... (Code wie vorher) ...
    global mqtt_client
    host = config.MQTT_CONFIG.get("host_lokal") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get(
        "host")
    port = config.MQTT_CONFIG.get("port_lokal") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get(
        "port")
    user = config.MQTT_CONFIG.get("user_local") if config.REC_CONFIG.get("test_mode") else config.MQTT_CONFIG.get(
        "user")
    password = config.MQTT_CONFIG.get("password_local") if config.REC_CONFIG.get(
        "test_mode") else config.MQTT_CONFIG.get("password")

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
    problem_file = os.path.join(project_root, config.PROBLEM_CONFIG.get("problem_json", "problemzonen.json"))
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

    def get_config_value(env_key, default, value_type=str):
        value_str = env_values.get(env_key)
        if value_str is None:
            if env_key == 'HEATMAP_RADIUS':
                default = config.HEATMAP_CONFIG.get('heatmap_aktuell', {}).get('radius', 5)
            elif env_key == 'HEATMAP_BLUR':
                default = config.HEATMAP_CONFIG.get('heatmap_aktuell', {}).get('blur', 10)
            elif env_key == 'HEATMAP_GENERATE_PNG':
                default = config.HEATMAP_CONFIG.get('heatmap_aktuell', {}).get('generate_png', False)
            elif env_key == 'GEO_ZOOM_START':
                default = config.GEO_CONFIG.get('zoom_start', 15)
            elif env_key == 'GEO_MAX_ZOOM':
                default = config.GEO_CONFIG.get('max_zoom', 22)
            elif env_key == 'REC_STORAGE_INTERVAL':
                default = config.REC_CONFIG.get('storage_interval', 1)
            elif env_key == 'TEST_MODE':
                default = config.REC_CONFIG.get('test_mode', False)
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
            'GEO_ZOOM_START': get_config_value('GEO_ZOOM_START', 15, int),
            'GEO_MAX_ZOOM': get_config_value('GEO_MAX_ZOOM', 22, int),
        },
        'REC': {
            'REC_STORAGE_INTERVAL': get_config_value('REC_STORAGE_INTERVAL', 1, int),
            'TEST_MODE': get_config_value('TEST_MODE', False, bool),
        },
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
        except Exception as e:
            logger.error(f"Fehler im Systemstatistiken-Thread: {e}", exc_info=False)
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


# --- /stats (unverändert, nutzt jetzt stats_libs_available) ---
@app.route('/stats')
def stats():
    # ... (Code wie vorher, mit Prüfung auf stats_libs_available) ...
    problem_zones = get_problem_zones()
    recordings_dir = os.path.join(project_root, 'recordings')
    total_recordings = 0
    total_distance_km = 0.0
    total_duration_min = 0.0
    all_satellites = []
    avg_satellites = 0.0

    if not stats_libs_available:
        logger.error("Statistik-Bibliotheken (pandas, geopy) nicht verfügbar.")
        stats_data = {
            'total_recordings': 'N/A', 'total_distance': 'N/A', 'total_time': 'N/A',
            'avg_satellites': 'N/A', 'problem_zones_count': len(problem_zones)
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
                        if not df.empty:
                            points = list(zip(df['latitude'], df['longitude']))
                            distance_m = 0
                            for i in range(len(points) - 1):
                                try:
                                    distance_m += geodesic(points[i], points[i + 1]).meters
                                except ValueError:
                                    logger.warning(
                                        f"Ungültige Koordinaten in {csv_file} bei Index {i}, überspringe Distanzsegment.")
                            total_distance_km += distance_m / 1000.0
                            duration = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
                            total_duration_min += duration.total_seconds() / 60.0
                            all_satellites.extend(df['satellites'].tolist())
                    except pd.errors.EmptyDataError:
                        logger.warning(f"CSV-Datei {csv_file} ist leer oder konnte nicht gelesen werden.")
                    except Exception as e:
                        logger.error(f"Fehler beim Verarbeiten von {csv_file}: {e}", exc_info=False)
                if all_satellites:
                    valid_sats = [float(s) for s in all_satellites if
                                  isinstance(s, (int, float, str)) and str(s).replace('.', '', 1).isdigit()]
                    if valid_sats: avg_satellites = sum(valid_sats) / len(valid_sats)
        except Exception as e:
            logger.error(f"Fehler beim Laden der Statistiken: {e}", exc_info=True)
            total_recordings, total_distance_km, total_duration_min, avg_satellites = 'Fehler', 'Fehler', 'Fehler', 'Fehler'

        stats_data = {
            'total_recordings': total_recordings,
            'total_distance': total_distance_km,
            'total_time': round(total_duration_min) if isinstance(total_duration_min,
                                                                  (int, float)) else total_duration_min,
            'avg_satellites': avg_satellites,
            'problem_zones_count': len(problem_zones)
        }

    template_path = os.path.join(app.template_folder, 'stats.html')
    if not os.path.exists(template_path):
        logger.error(f"Template 'stats.html' nicht gefunden in {app.template_folder}")
        return "Fehler: Template 'stats.html' nicht gefunden.", 500
    return render_template('stats.html', stats=stats_data, problem_zones=problem_zones)


# --- /control, /live (unverändert) ---
@app.route('/control', methods=['POST'])
def control():
    # ... (Code wie vorher) ...
    try:
        data = request.get_json()
        if not data or 'command' not in data: return jsonify({"success": False, "message": "'command' fehlt."}), 400
        command = data['command']
        if not mqtt_client or not mqtt_client.is_connected(): return jsonify(
            {"success": False, "message": "MQTT nicht verbunden"}), 503
        control_topic = config.MQTT_CONFIG.get("topic_control")
        if not control_topic: return jsonify({"success": False, "message": "Kontroll-Topic nicht konfiguriert"}), 500
        command_map = {'start_recording': 'START_REC', 'stop_recording': 'STOP_REC',
                       'generate_heatmaps': 'GENERATE_HEATMAPS', 'shutdown': 'SHUTDOWN'}
        message = command_map.get(command)
        if message:
            try:
                if command == 'start_recording':
                    with status_lock:
                        current_status['is_recording'] = True
                elif command == 'stop_recording':
                    with status_lock:
                        current_status['is_recording'] = False
                mqtt_client.publish(control_topic, message)
                logger.info(f"Steuerbefehl '{message}' an Topic '{control_topic}' gesendet.")
                socketio.emit('status_update', current_status)
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


@app.route('/live')
def live_view():
    # ... (Code wie vorher) ...
    with status_lock: status_data = current_status.copy()
    map_config = {
        'center_lat': status_data['lat'], 'center_lon': status_data['lon'],
        'zoom': config.GEO_CONFIG.get('zoom_start', 15), 'max_zoom': config.GEO_CONFIG.get('max_zoom', 22),
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
