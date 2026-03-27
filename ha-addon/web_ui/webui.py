# webui.py (Überarbeitete Struktur - Konzeptionell)



import logging



import logging

import os

import sys

import threading

import json

import time

from pathlib import Path

from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for

from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix

from dotenv import set_key, find_dotenv, dotenv_values

from flask_cors import CORS



import glob # glob ist Teil der Standardbibliothek

try:

    import pandas as pd

    from geopy.distance import geodesic

    stats_libs_available = True

except ImportError:

    stats_libs_available = False

    logging.warning("pandas oder geopy nicht gefunden. Statistiken sind nicht verfügbar.")

    # Definiere Dummy-Variablen, falls Import fehlschlägt, um spätere Fehler zu vermeiden

    pd = None 

    geodesic = None



# Füge das übergeordnete Verzeichnis zum Suchpfad hinzu

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, project_root)



# Importiere Konfiguration und die neuen Service-Klassen

import config

from web_ui.mqtt_service import MqttService

from web_ui.status_manager import StatusManager

from web_ui.data_service import DataService
from web_ui.system_monitor import SystemMonitor
from web_ui.worx_cloud_service import WorxCloudService
from web_ui.simulator import ChaosSimulator
from web_ui.ha_discovery import HADiscoveryService



# --- Logging ---

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s') # Geändert auf DEBUG und detaillierteres Format

logger = logging.getLogger(__name__)

# --- Centralized Log Collector ---
class LogCollector:
    """Sammelt und puffert Logs von verschiedenen Quellen."""
    def __init__(self, max_logs=1000):
        self.max_logs = max_logs
        self.logs = []
        self.lock = threading.Lock()
        
    def add_log(self, level, message, source="webui", timestamp=None):
        """Fügt einen Log-Eintrag hinzu."""
        if timestamp is None:
            # Einfacher Timestamp ohne datetime dependency
            import time
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "message": message
        }
        
        with self.lock:
            self.logs.append(log_entry)
            # Begrenze die Anzahl der Logs im Speicher
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
    
    def get_logs(self, level_filter=None, source_filter=None, limit=100):
        """Gibt die letzten Logs zurück, optional gefiltert."""
        with self.lock:
            logs = self.logs.copy()
        
        # Filter anwenden
        if level_filter:
            logs = [log for log in logs if log["level"] == level_filter]
        if source_filter:
            logs = [log for log in logs if log["source"] == source_filter]
        
        # Begrenzen und neueste zuerst
        return logs[-limit:] if logs else []

# Globaler Log Collector
log_collector = LogCollector(max_logs=200) # LIMITIERT: Nur die letzten 200 Logs im RAM behalten
log_collector.logs = [] # GARANTIERT: Leer beim Start

# Custom Handler der Logs zum Collector weiterleitet
class WebUILogHandler(logging.Handler):
    def __init__(self, collector):
        super().__init__()
        self.collector = collector
    
    def emit(self, record):
        try:
            level = record.levelname
            message = self.format(record)
            source = getattr(record, 'source', 'webui')
            # Einfacher Timestamp ohne datetime dependency
            import time
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(record.created))
            self.collector.add_log(level, message, source, timestamp)
        except Exception as e:
            # Bei Fehlern nicht crashen, einfach still ignorieren
            pass

# WebUILogHandler zum Root Logger hinzügen
webui_handler = WebUILogHandler(log_collector)
webui_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(webui_handler)



# --- Home Assistant Ingress Middleware ---
class IngressMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')
        ingress_path = environ.get('HTTP_X_INGRESS_PATH')
        
        # Nur eingreifen, wenn wir wirklich über HA Ingress kommen
        if ingress_path:
            logger.debug(f"[IngressMiddleware] HA Ingress erkannt: {ingress_path}")
            environ['SCRIPT_NAME'] = ingress_path.rstrip('/')
            if path_info.startswith(ingress_path):
                environ['PATH_INFO'] = path_info[len(ingress_path):]
                if not environ['PATH_INFO'].startswith('/'):
                    environ['PATH_INFO'] = '/' + environ['PATH_INFO']
        
        return self.app(environ, start_response)

# --- Flask & SocketIO Setup ---

app = Flask(__name__)
app.wsgi_app = IngressMiddleware(app.wsgi_app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback-sehr-geheim')

frontend_dist = os.path.join(project_root, 'frontend', 'dist')

app.template_folder = frontend_dist

app.static_folder = frontend_dist

# For serving static assets inside the Vite build (js/css)

app.static_url_path = ''

CORS(app) # Enable CORS for React Frontend API calls

# Eventlet entfernt wegen Kompatibilitätsproblemen auf Windows, falle zurück auf default (threading/werkzeug)

socketio = SocketIO(app, async_mode=None, ping_timeout=20, ping_interval=10, cors_allowed_origins="*")



# --- Instanzen der neuen Services (Globale Instanzen, auf die Routen zugreifen) ---

mqtt_service = None

status_manager = None

data_service = None

system_monitor = None

worx_cloud_service = None



# --- Flask Routen (Interagieren mit Service-Instanzen) ---



@app.route('/ping')
def ping():
    return "PONG", 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """
    Serve the React UI. Supports both direct IP access and HA Ingress.
    """
    if path and path.startswith('api/'):
        return jsonify({"error": "API route not found"}), 404

    # 1. Bereinige den Pfad (entferne Ingress-Präfix, falls im URL-Pfad vorhanden)
    ingress_path = request.headers.get('X-Ingress-Path', '').strip('/')
    clean_path = path
    if ingress_path and path.startswith(ingress_path):
        clean_path = path[len(ingress_path):].lstrip('/')

    # 2. Prüfe, ob es eine statische Datei (Asset) ist
    target_file = clean_path if clean_path else 'index.html'
    full_path = os.path.join(app.static_folder, target_file)

    # logger.debug(f"[ServeReact] Path: {path} | Clean: {clean_path} | Full: {full_path}")

    if os.path.exists(full_path) and os.path.isfile(full_path):
        # Wichtig: Mime-Types für JS/CSS sicherstellen
        return send_from_directory(app.static_folder, target_file)
    
    # 3. Fallback: Immer index.html (für React Router)
    return send_from_directory(app.static_folder, 'index.html')



# --- NEUE API ROUTEN FÜR REACT FRONTEND ---

@app.route('/api/status')

def api_status():

    if not status_manager or not data_service or not mqtt_service:

        return jsonify({"error": "Services not ready"}), 503

    return jsonify({

        "mower": status_manager.get_current_mower_status(),

        "system": status_manager.get_current_system_stats(),

        "pi": status_manager.get_current_pi_status(),

        "mqtt_connected": mqtt_service.is_connected()

    })



@app.route('/api/heatmaps')

def api_heatmaps():

    if not data_service: return jsonify({"error": "Service not ready"}), 503

    return jsonify({

        "heatmaps": data_service.get_available_heatmaps(),

        "current_heatmap": data_service.get_current_heatmap_path()

    })



@app.route('/api/stats')

def api_stats():

    if not data_service: return jsonify({"error": "Service not ready"}), 503

    return jsonify({

        "stats": data_service.get_statistics(),

        "problem_zones": data_service.get_formatted_problem_zones(),

        "mow_sessions": data_service.get_mow_sessions_for_display()

    })



@app.route('/api/config')

def api_config():

    if not data_service: return jsonify({"error": "Service not ready"}), 503

    return jsonify({

        "config": data_service.get_editable_config(),

        "info": data_service.get_config_info()

    })

# --- ENDE NEUE API ROUTEN ---
# --- LEGACY ROUTES (ENTFERNT) ---
# Die Routen /maps, /live, /stats, /config werden jetzt vom React-Frontend (App.jsx) gehandelt.
# Flask dient nur noch als API-Server (/api/...).



@app.route('/heatmaps/<path:filename>')

def serve_heatmap(filename):

    """Liefert Heatmap-Dateien"""

    # Der Pfad wird relativ zum Projekt-Root + 'heatmaps' sein

    heatmap_dir = os.path.join(project_root, 'heatmaps') # Oder data_service.get_heatmap_dir()

    if '..' in filename or filename.startswith('/'): return "Ungültiger Dateiname", 400

    return send_from_directory(heatmap_dir, filename)





@app.route('/config/save', methods=['POST'])

def save_config():

    """Speichert Konfigurationsänderungen"""

    try:

        if not data_service: # data_service wird hier nicht direkt verwendet, aber zur Konsistenz

            logger.error("DataService nicht initialisiert in save_config Route.")

            return jsonify({"success": False, "message": "Serverfehler: DataService nicht bereit."}), 503



        data = request.form.to_dict()

        logger.info(f"Empfangene Konfigurationsänderungen: {data}")

        # Persistenter Speicherort: Im HA Add-on nach /data/.env schreiben (überlebt Neustarts)
        data_dir = os.getenv('DATA_DIR', '')
        if data_dir and os.path.isdir(data_dir):
            env_file_path = os.path.join(data_dir, '.env')
            logger.info(f"Speichere Konfiguration persistent in: {env_file_path}")
        else:
            # Lokaler Entwicklungsmodus: .env im Projekt-Root
            env_file_path = find_dotenv()
            if not env_file_path:
                env_file_path = os.path.join(project_root, '.env')
                logger.warning(f".env Datei nicht gefunden, erstelle: {env_file_path}")

        if not os.path.exists(env_file_path):
            Path(env_file_path).touch()



        allowed_keys = {
            'heatmap_radius': 'HEATMAP_RADIUS', 'heatmap_blur': 'HEATMAP_BLUR',
            'heatmap_generate_png': 'HEATMAP_GENERATE_PNG', 'geo_zoom_start': 'GEO_ZOOM_START',
            'geo_max_zoom': 'GEO_MAX_ZOOM', 'rec_storage_interval': 'REC_STORAGE_INTERVAL',
            'rec_test_mode': 'TEST_MODE',
            'moving_average_window': 'MOVING_AVERAGE_WINDOW',
            'kalman_measurement_noise': 'KALMAN_MEASUREMENT_NOISE',
            'kalman_process_noise': 'KALMAN_PROCESS_NOISE',
            'hdop_threshold': 'HDOP_THRESHOLD',
            'max_speed_mps': 'MAX_SPEED_MPS',
            'outlier_detection': 'OUTLIER_DETECTION_ENABLE',
            'dead_reckoning': 'DEAD_RECKONING_ENABLED',
            'gnss_mode': 'GPS_GNSS_MODE',
            'gps_serial_port': 'GPS_SERIAL_PORT',
            'gps_baudrate': 'GPS_BAUDRATE',
            'debug_logging': 'DEBUG_LOGGING'
        }

        saved_keys, error_messages = [], []

        for form_key, form_value in data.items():

            if form_key in allowed_keys:

                env_key = allowed_keys[form_key]

                # Behandle Checkboxen (on -> True, nicht vorhanden -> False)
                # ACHTUNG: gnss_mode ist ein String/Toggle, keine Checkbox!
                checkbox_keys = ['heatmap_generate_png', 'rec_test_mode', 'outlier_detection', 'debug_logging', 'dead_reckoning']
                is_checkbox = form_key in checkbox_keys
                
                if is_checkbox:
                    env_value = 'True' if form_value == 'on' else 'False'
                else:
                    env_value = str(form_value).strip()

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



        # Hot-Reload: POST_PROCESSING_CONFIG in-memory aktualisieren
        hot_reloaded = []
        env_to_pp = {
            'MOVING_AVERAGE_WINDOW': ('POST_PROCESSING_CONFIG', 'moving_average_window', int),
            'KALMAN_MEASUREMENT_NOISE': ('POST_PROCESSING_CONFIG', 'kalman_measurement_noise', float),
            'KALMAN_PROCESS_NOISE': ('POST_PROCESSING_CONFIG', 'kalman_process_noise', float),
            'HDOP_THRESHOLD': ('POST_PROCESSING_CONFIG', 'hdop_threshold', float),
            'MAX_SPEED_MPS': ('POST_PROCESSING_CONFIG', 'max_speed_mps', float),
            'OUTLIER_DETECTION_ENABLE': ('POST_PROCESSING_CONFIG', 'outlier_detection.enable', bool),
            'DEAD_RECKONING_ENABLED': ('POST_PROCESSING_CONFIG', 'dead_reckoning_enabled', bool),
            'GPS_GNSS_MODE': ('GPS_CONFIG', 'gnss_mode', str),
        }
        for env_key in saved_keys:
            if env_key in env_to_pp:
                cfg_target, cfg_key, cfg_type = env_to_pp[env_key]
                env_val = dotenv_values(env_file_path).get(env_key)
                if env_val is not None:
                    try:
                        if cfg_type == bool:
                            typed_val = env_val.lower() in ['true', '1', 'yes', 'on']
                        else:
                            typed_val = cfg_type(env_val)
                        
                        # Ziel-Config bestimmen (config.POST_PROCESSING_CONFIG oder config.GPS_CONFIG)
                        target_dict = getattr(config, cfg_target)
                        
                        if '.' in cfg_key:
                            parts = cfg_key.split('.')
                            target_dict[parts[0]][parts[1]] = typed_val
                        else:
                            target_dict[cfg_key] = typed_val
                        
                        if env_key == 'MAX_SPEED_MPS':
                            config.POST_PROCESSING_CONFIG.setdefault('outlier_detection', {})['max_speed_mps'] = typed_val
                            
                        hot_reloaded.append(env_key)
                        logger.info(f"Hot-Reload: config.{cfg_target}['{cfg_key}'] = {typed_val}")
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.warning(f"Hot-Reload fehlgeschlagen für {env_key}: {e}")

        # Prüfe ob alle gespeicherten Keys hot-reloaded wurden
        all_reloaded = all(k in hot_reloaded for k in saved_keys)
        
        if all_reloaded:
            message = f"Konfiguration aktualisiert ({', '.join(saved_keys)}). Alle Änderungen wurden sofort übernommen."
        elif hot_reloaded:
            others = [k for k in saved_keys if k not in hot_reloaded]
            message = f"Teilweise aktualisiert: {', '.join(hot_reloaded)} (sofort übernommen), {', '.join(others)} (Neustart erforderlich)."
        else:
            message = f"Konfiguration gespeichert ({', '.join(saved_keys)}). Ein Neustart ist für alle Änderungen erforderlich."

        return jsonify({"success": True, "message": message})



    except Exception as e:

        logger.error(f"Fehler beim Speichern der Konfiguration: {e}", exc_info=True)

        return jsonify({"success": False, "message": f"Serverfehler: {str(e)}"}), 500





# --- LEGACY STATS (DEAKTIVIERT) ---
"""
@app.route('/stats')
def stats():
    ...
"""
# --- ENDE LEGACY STATS ---
# --- NEU: Mähvorgänge an Template übergeben



@app.route('/control', methods=['POST'])

def control():

    """Empfängt und verarbeitet Steuerbefehle."""

    try:

        data = request.get_json()

        if not data or 'command' not in data: return jsonify({"success": False, "message": "'command' fehlt."}), 400

        command = data['command']

        

        if not mqtt_service:

            logger.error("MqttService nicht initialisiert in control Route.")

            return jsonify({"success": False, "message": "Serverfehler: MQTT-Service nicht bereit."}), 503



        if not mqtt_service.is_connected():

             return jsonify({"success": False, "message": "MQTT nicht verbunden"}), 503



        command_map = {'start_recording': 'START_REC', 'stop_recording': 'STOP_REC',

                       'generate_heatmaps': 'GENERATE_HEATMAPS', 'shutdown': 'SHUTDOWN'}

        message = command_map.get(command)



        if message: # Korrigiert von message_to_send

            if mqtt_service.publish_command(message): # Korrigiert von message_to_send

                return jsonify({"success": True, "message": f"Befehl '{command}' gesendet."})

            else:

                return jsonify({"success": False, "message": "MQTT Sende-Fehler: Befehl konnte nicht veröffentlicht werden."}), 500

        else:

            logger.warning(f"Unbekannter Steuerbefehl empfangen: {command}")

            return jsonify({"success": False, "message": f"Unbekannter Befehl: {command}"}), 400



    except Exception as e:

        logger.error(f"Fehler beim Verarbeiten des Steuerbefehls: {e}", exc_info=True)

        return jsonify({"success": False, "message": f"Serverfehler: {str(e)}"}), 500



# NEU: Route zum Löschen von Mähvorgängen

@app.route('/mow_session/delete/<path:filename>', methods=['POST'])

def delete_mow_session_route(filename):

    if not data_service:

        logger.error("DataService nicht initialisiert für delete_mow_session_route.")

        return jsonify({"success": False, "message": "Serverfehler: DataService nicht bereit."}), 503

    

    logger.info(f"Löschanfrage für Mähvorgang empfangen: {filename}")
    success = data_service.delete_mow_session(filename)
    
    if success:
        return jsonify({"success": True, "message": f"Mähvorgang '{filename}' erfolgreich gelöscht."})
    else:
        # DataManager loggt bereits spezifischere Fehler
        return jsonify({"success": False, "message": f"Fehler beim Löschen von '{filename}'. Prüfe Server-Logs."}), 500





# --- Geofencing (Zoneneditor) ---

@app.route('/api/geofences', methods=['GET'])
def get_geofences():
    """Lädt alle Zonen."""
    if not data_service:
        return jsonify([])
    return jsonify(data_service.get_geofences())

@app.route('/api/geofences', methods=['POST'])
def save_geofence():
    """Speichert eine neue oder aktualisierte Zone."""
    if not data_service:
        return jsonify({"status": "error", "message": "Service nicht verfügbar"}), 500
    
    data = request.json
    fence_id = data.get('id')
    name = data.get('name')
    f_type = data.get('type', 'mow_area')
    coords = data.get('coordinates', [])
    
    if not name or not coords:
        return jsonify({"status": "error", "message": "Name und Koordinaten fehlen"}), 400
        
    new_id = data_service.save_geofence(name, f_type, coords, fence_id)
    if new_id:
        return jsonify({"status": "success", "id": new_id})
    return jsonify({"status": "error", "message": "Fehler beim Speichern"}), 500

@app.route('/api/geofences/<int:geofence_id>', methods=['DELETE'])
def delete_geofence(geofence_id):
    """Löscht eine Zone."""
    if not data_service:
        return jsonify({"status": "error"}), 500
    
    if data_service.delete_geofence(geofence_id):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route('/api/live_config')
def api_live_config():
    """JSON-API für die Live-Karte (React Frontend)."""
    if not status_manager:
        return jsonify({"error": "StatusManager nicht initialisiert"}), 503

    status_data = status_manager.get_current_mower_status()
    geo_config_dict = getattr(config, "GEO_CONFIG", {})

    initial_lat = status_data.get('lat') if status_data.get('lat') is not None else geo_config_dict.get("map_center", (0,0))[0]
    initial_lon = status_data.get('lon') if status_data.get('lon') is not None else geo_config_dict.get("map_center", (0,0))[1]

    map_config = {
        'initial_lat': initial_lat,
        'initial_lon': initial_lon,
        'initial_zoom': geo_config_dict.get('max_zoom', 22),
        'max_zoom': geo_config_dict.get('max_zoom', 22),
        'osm_tiles': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'osm_attr': '&copy; <a href="https://osm.org/copyright">OSM</a> contributors',
        'satellite_tiles': 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        'satellite_attr': 'Google Satellite'
    }

    return jsonify({"status": status_data, "map_config": map_config})

@app.route('/live')
def live_view():

    """Live-Kartenansicht"""

    if not status_manager:

        logger.error("StatusManager nicht initialisiert in live_view Route.")

        return "Fehler: StatusManager nicht initialisiert.", 503



    status_data = status_manager.get_current_mower_status()



    geo_config_dict = getattr(config, "GEO_CONFIG", {})

    

    # Definiere initiale Kartenparameter. Verwende Statusdaten, wenn verfügbar, sonst Fallback auf GEO_CONFIG.

    initial_lat = status_data.get('lat') if status_data.get('lat') is not None else geo_config_dict.get("map_center", (0,0))[0]

    initial_lon = status_data.get('lon') if status_data.get('lon') is not None else geo_config_dict.get("map_center", (0,0))[1]



    map_config_for_live = {

        'initial_lat': initial_lat,

        'initial_lon': initial_lon,

        'initial_zoom': geo_config_dict.get('max_zoom', 22), # Geändert auf max_zoom

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



    return render_template('live.html', status=status_data, map_config=map_config_for_live)





# --- SocketIO Events (Interagieren mit Status-Manager) ---

@socketio.on('connect')

def handle_connect():

    """Wird aufgerufen, wenn sich ein Browser per WebSocket verbindet."""

    if not status_manager:

        logger.error("StatusManager nicht initialisiert bei SocketIO connect.")

        return



    logger.info(f'Web-Client verbunden (SID: {request.sid})')

    # Sende den aktuellen Status sofort an den neuen Client

    socketio.emit('status_update', status_manager.get_current_mower_status(), room=request.sid)

    socketio.emit('system_update', status_manager.get_current_system_stats(), room=request.sid)

    socketio.emit('pi_status_update', status_manager.get_current_pi_status(), room=request.sid)





@socketio.on('disconnect')

def handle_disconnect():

    """Wird aufgerufen, wenn die WebSocket-Verbindung getrennt wird."""

    logger.info(f'Web-Client getrennt (SID: {request.sid})')

# --- Worx Cloud Mäher-API Routen ---

@app.route('/api/mower/status')
def api_mower_status():
    """Voller Mäher-Status aus der Worx Cloud."""
    if not worx_cloud_service or not worx_cloud_service.is_connected:
        return jsonify({"error": "Worx Cloud nicht verbunden"}), 503
    return jsonify(worx_cloud_service.get_status())

@app.route('/api/mower/command', methods=['POST'])
def api_mower_command():
    """Befehl an den Mäher senden."""
    if not worx_cloud_service or not worx_cloud_service.is_connected:
        return jsonify({"error": "Worx Cloud nicht verbunden"}), 503
    
    data = request.get_json(silent=True) or {}
    cmd = data.get('command', '')
    
    command_map = {
        'start': worx_cloud_service.command_start,
        'stop': worx_cloud_service.command_stop,
        'home': worx_cloud_service.command_stop,
        'pause': worx_cloud_service.command_pause,
        'safehome': worx_cloud_service.command_safehome,
        'edgecut': worx_cloud_service.command_edgecut,
        'restart': worx_cloud_service.command_restart,
    }
    
    if cmd in command_map:
        result = command_map[cmd]()
        return jsonify(result)
    elif cmd == 'ots':
        boundary = data.get('boundary', False)
        runtime = data.get('runtime', 60)
        return jsonify(worx_cloud_service.command_ots(boundary, runtime))
    elif cmd == 'lock':
        return jsonify(worx_cloud_service.command_set_lock(data.get('state', True)))
    elif cmd == 'torque':
        return jsonify(worx_cloud_service.command_set_torque(data.get('value', 0)))
    elif cmd == 'raindelay':
        return jsonify(worx_cloud_service.command_set_raindelay(data.get('value', 0)))
    elif cmd == 'toggle_schedule':
        return jsonify(worx_cloud_service.command_toggle_schedule(data.get('enabled', True)))
    elif cmd == 'setzone':
        return jsonify(worx_cloud_service.command_set_zone(data.get('zone', 0)))
    elif cmd == 'time_extension':
        return jsonify(worx_cloud_service.command_set_time_extension(data.get('value', 0)))
    elif cmd == 'raw':
        return jsonify(worx_cloud_service.command_send_raw(data.get('data', '{}')))
    else:
        return jsonify({"error": f"Unbekannter Befehl: {cmd}"}), 400

@app.route('/api/mower/schedule')
def api_mower_schedule():
    """Zeitplan abrufen."""
    if not worx_cloud_service or not worx_cloud_service.is_connected:
        return jsonify({"error": "Worx Cloud nicht verbunden"}), 503
    return jsonify(worx_cloud_service.get_schedule())

@app.route('/api/mower/autopilot', methods=['POST'])
def api_mower_autopilot():
    """Autopilot ein/ausschalten."""
    if not worx_cloud_service:
        return jsonify({"error": "Worx Cloud nicht verfügbar"}), 503
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled', True)
    worx_cloud_service.set_autopilot(enabled)
    return jsonify({"success": True, "autopilot": enabled})

# --- Logs API ---
@app.route('/api/logs')
def api_logs():
    """Gibt die echten Logs aus dem LogCollector zurück."""
    try:
        level_filter = request.args.get('level')
        source_filter = request.args.get('source')
        limit = int(request.args.get('limit', 100))
        
        logs = log_collector.get_logs(level_filter, source_filter, limit)
        
        return jsonify({
            "status": "success",
            "logs": logs,
            "total": len(logs)
        })
    except Exception as e:
        logger.error(f"[API] Error in /api/logs: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "logs": [],
            "total": 0
        }), 500

@app.route('/api/logs/sources')
def api_log_sources():
    """Gibt alle aktuell bekannten Log-Quellen zurück."""
    try:
        with log_collector.lock:
            # Schnelle Extraktion: Nur die letzten 50 Logs für Quellen-Check nutzen
            recent_logs = log_collector.logs[-50:]
            sources = list(set(log.get("source", "system") for log in recent_logs))
            if not sources: sources = ["webui", "system"]
            
        return jsonify({
            "status": "success", 
            "sources": sorted(sources)
        })
    except Exception as e:
        logger.error(f"[API] Error in /api/logs/sources: {e}")
        return jsonify({"status": "error", "sources": ["webui", "system"]}), 500

@app.route('/api/logs/test')
def api_logs_test():
    """Test-Endpoint für Log-Funktionalität."""
    return jsonify({
        "status": "success",
        "message": "Logs API works",
        "total_logs": len(log_collector.logs),
        "sample_logs": log_collector.logs[:3] if log_collector.logs else []
    })

# --- Database Reset API ---
@app.route('/api/database/reset', methods=['POST'])
def api_database_reset():
    """Setzt die Datenbank zurück (löscht alle Mähsessions)."""
    if not data_service:
        return jsonify({"status": "error", "message": "DataService nicht verfügbar"}), 500
    
    # Prüfe ob Geofences auch gelöscht werden sollen
    include_geofences = request.json.get('include_geofences', False) if request.is_json else False
    
    try:
        # Backup-Info vor dem Löschen
        all_sessions = data_service.data_manager.load_all_mow_data()
        session_count = len(all_sessions)
        geofence_count = 0
        
        if include_geofences:
            geofences = data_service.data_manager.get_geofences()
            geofence_count = len(geofences)
        
        # Datenbank zurücksetzen
        data_service.data_manager.reset_database(include_geofences=include_geofences)
        
        # Interne Puffer aktualisieren
        data_service.reload_buffers()
        
        # Heatmaps neu generieren (oder leeren, wenn keine Daten mehr da sind)
        data_service._generate_all_heatmaps()
        
        # Erfolgsmeldung zusammenbauen
        parts = [f"{session_count} Sessions"]
        if include_geofences:
            parts.append(f"{geofence_count} Geofences")
        
        logger.warning(f"[API] Datenbank zurückgesetzt: {', '.join(parts)} gelöscht.")
        
        return jsonify({
            "status": "success", 
            "message": f"Datenbank erfolgreich zurückgesetzt. {', '.join(parts)} wurden gelöscht.",
            "deleted_sessions": session_count,
            "deleted_geofences": geofence_count if include_geofences else 0
        })
        
    except Exception as e:
        logger.error(f"[API] Fehler beim Datenbank-Reset: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500

# --- Datenbank-Manager API ---

@app.route('/api/database/info')
def api_database_info():
    """Gibt allgemeine Datenbank-Informationen zurück."""
    if not data_service:
        return jsonify({"error": "DataService nicht verfügbar"}), 500
    return jsonify(data_service.data_manager.get_database_info())

@app.route('/api/database/sessions')
def api_database_sessions():
    """Gibt eine kompakte Übersicht aller Sessions zurück (ohne Punkte)."""
    if not data_service:
        return jsonify({"sessions": []}), 500
    sessions = data_service.data_manager.get_all_sessions_summary()
    return jsonify({"sessions": sessions})

@app.route('/api/database/sessions/<int:session_id>')
def api_database_session_detail(session_id):
    """Gibt eine einzelne Session mit Metadaten und Punkten zurück."""
    if not data_service:
        return jsonify({"error": "DataService nicht verfügbar"}), 500
    session = data_service.data_manager.get_session_by_id(session_id)
    if not session:
        return jsonify({"error": "Session nicht gefunden"}), 404
    points = data_service.data_manager.get_session_points(session_id)
    session['points'] = points
    return jsonify(session)

@app.route('/api/database/sessions/<int:session_id>/export/csv')
def api_database_export_csv(session_id):
    """Exportiert eine Session als CSV."""
    if not data_service:
        return jsonify({"error": "DataService nicht verfügbar"}), 500
    session = data_service.data_manager.get_session_by_id(session_id)
    if not session:
        return jsonify({"error": "Session nicht gefunden"}), 404
    points = data_service.data_manager.get_session_points(session_id)
    
    import io, csv
    output = io.StringIO()
    if points:
        writer = csv.DictWriter(output, fieldnames=points[0].keys())
        writer.writeheader()
        writer.writerows(points)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=session_{session_id}.csv'}
    )

@app.route('/api/database/sessions/<int:session_id>/export/json')
def api_database_export_json(session_id):
    """Exportiert eine Session als JSON."""
    if not data_service:
        return jsonify({"error": "DataService nicht verfügbar"}), 500
    session = data_service.data_manager.get_session_by_id(session_id)
    if not session:
        return jsonify({"error": "Session nicht gefunden"}), 404
    points = data_service.data_manager.get_session_points(session_id)
    
    export_data = {
        'session': session,
        'points': points,
        'export_timestamp': datetime.now().isoformat()
    }
    
    from flask import Response
    return Response(
        json.dumps(export_data, indent=2, default=str),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=session_{session_id}.json'}
    )

@app.route('/api/database/sessions/<int:session_id>', methods=['DELETE'])
def api_database_delete_session(session_id):
    """Löscht eine einzelne Session."""
    if not data_service:
        return jsonify({"error": "DataService nicht verfügbar"}), 500
    success = data_service.data_manager.delete_session_by_id(session_id)
    if success:
        # Interne Puffer aktualisieren
        data_service.reload_buffers()
        # Karten nach dem Löschen sofort neu generieren
        data_service._generate_all_heatmaps()
        logger.info(f"[API] Session {session_id} gelöscht.")
        return jsonify({"success": True, "message": f"Session {session_id} gelöscht."})
    return jsonify({"error": "Session nicht gefunden"}), 404

@app.route('/api/database/sessions/quality')
def api_database_quality_stats():
    """Gibt Qualitätsstatistiken pro Session für Langzeitanalyse zurück."""
    if not data_service:
        return jsonify({"stats": []}), 500
    stats = data_service.data_manager.get_session_quality_stats()
    return jsonify({"stats": stats})

@app.route('/api/database/export/all')
def api_database_export_all():
    """Exportiert alle Sessions als JSON."""
    if not data_service:
        return jsonify({"error": "DataService nicht verfügbar"}), 500
    sessions = data_service.data_manager.get_all_sessions_summary()
    all_data = []
    for s in sessions:
        points = data_service.data_manager.get_session_points(s['id'])
        s['points'] = points
        all_data.append(s)
    
    from flask import Response
    return Response(
        json.dumps({'sessions': all_data, 'export_timestamp': datetime.now().isoformat()}, indent=2, default=str),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=worx_gps_export_all.json'}
    )

# --- Simulator API ---
simulator_instance = None

@app.route('/api/simulator/status')
def api_simulator_status():
    """Gibt den aktuellen Simulator-Status zurück."""
    if simulator_instance:
        return jsonify({
            "running": simulator_instance.is_running(),
            "exists": True,
            "lat": simulator_instance.current_lat if simulator_instance.is_running() else None,
            "lon": simulator_instance.current_lon if simulator_instance.is_running() else None
        })
    return jsonify({"running": False, "exists": False})

@app.route('/api/simulator/toggle', methods=['POST'])
def api_simulator_toggle():
    """Startet oder stoppt den Simulator."""
    global simulator_instance
    if not simulator_instance:
        if mqtt_service and data_service:
            simulator_instance = ChaosSimulator(
                config.GEO_CONFIG,
                mqtt_service,
                data_manager=data_service
            )
        else:
            return jsonify({"error": "Services nicht verfügbar"}), 503

    if simulator_instance.is_running():
        simulator_instance.stop()
        return jsonify({"running": False})
    else:
        simulator_instance.start()
        return jsonify({"running": True})

# --- Start ---

if __name__ == '__main__':

    logger.info("Worx GPS WebUI wird gestartet...")

    # Globale Service-Instanzen erstellen

    try:

        status_manager = StatusManager(socketio, config.GEO_CONFIG.get("map_center", (0.0, 0.0)))



        # MqttService benötigt das Pi-Status-Topic aus der config.py

        pi_status_topic_for_mqtt_service = config.PI_STATUS_CONFIG.get("topic_pi_status")

        mqtt_service = MqttService(config.MQTT_CONFIG, pi_status_topic_for_mqtt_service)

        mqtt_service.set_status_update_callback(lambda payload: status_manager.update_mower_status(payload, config.GEO_CONFIG))

        mqtt_service.set_pi_status_update_callback(status_manager.update_pi_status)

        mqtt_service.set_gps_update_callback(lambda payload: data_service.handle_gps_data(payload))
        
        # Log-Callback für Pi-Logs
        def handle_pi_logs(payload):
            try:
                # Erwarte JSON: {"level": "INFO", "message": "...", "timestamp": "..."}
                import json
                log_data = json.loads(payload)
                log_collector.add_log(
                    level=log_data.get("level", "INFO"),
                    message=log_data.get("message", ""),
                    source="pi_gps_rec",
                    timestamp=log_data.get("timestamp")
                )
            except json.JSONDecodeError:
                # Fallback: plain text als INFO-Log
                log_collector.add_log("INFO", payload, "pi_gps_rec")
        
        mqtt_service.set_logs_update_callback(handle_pi_logs)

        mqtt_service.connect()



        data_service = DataService(

            project_root_path=project_root,

            heatmap_config=config.HEATMAP_CONFIG,

            problem_config=config.PROBLEM_CONFIG,

            geo_config_main=config.GEO_CONFIG,

            rec_config_main=config.REC_CONFIG

        )

        # Test-Log um zu prüfen ob der LogCollector funktioniert
        log_collector.add_log("INFO", "WebUI gestartet und LogCollector aktiv", "webui")



        system_monitor = SystemMonitor(status_manager.update_system_stats)
        system_monitor.start()

        # Worx Cloud Service starten (ersetzt HA-Polling Autopilot)
        worx_cloud_service = WorxCloudService()
        
        # Cloud-Status → StatusManager (für Frontend-Anzeige via SocketIO)
        def on_cloud_status(status_dict):
            if status_manager:
                display_text = status_dict.get('status_text', 'Unbekannt')
                imu = status_dict.get('orientation')
                status_manager.update_ha_mower_status(display_text, imu_data=imu)
            
            # IMU-Daten über MQTT an Worx_GPS.py senden (für Sensor-Fusion)
            imu = status_dict.get('orientation')
            if imu and mqtt_service:
                import json
                mqtt_service.publish("worx/imu", json.dumps({
                    "yaw": imu.get("yaw", 0),
                    "pitch": imu.get("pitch", 0),
                    "roll": imu.get("roll", 0),
                    "timestamp": time.time()
                }))
        
        worx_cloud_service.set_status_update_callback(on_cloud_status)
        worx_cloud_service.set_mqtt_publish_callback(mqtt_service.publish_command)

        # HA MQTT Auto-Discovery Service
        def ha_mqtt_publish(topic, payload, qos=0, retain=False):
            """Direkte MQTT Publish Funktion für HA Discovery (ohne test-prefix)."""
            if mqtt_service and mqtt_service.is_connected():
                mqtt_service.handler.publish_message(topic, payload, qos=qos, retain=retain)

        ha_discovery = HADiscoveryService(
            mqtt_publish_fn=ha_mqtt_publish,
            mower_name="Mower",  # Wird nach Verbindung automatisch aktualisiert
            serial="unknown",
        )
        worx_cloud_service.set_ha_discovery(ha_discovery)

        # HA Command Handler: lauscht auf Befehle vom HA Dashboard / landroid-card
        def on_ha_command(topic, payload):
            """Verarbeitet Befehle von Home Assistant (start_mowing, pause, dock)."""
            try:
                import json
                cmd = json.loads(payload)
                command = cmd.get('command', '')
                logger.info(f"[HADiscovery] HA-Befehl empfangen: {command}")

                if command == 'start_mowing' and worx_cloud_service.is_connected:
                    result = worx_cloud_service.command_start()
                    logger.info(f"[HADiscovery] Start: {result}")
                elif command == 'pause' and worx_cloud_service.is_connected:
                    result = worx_cloud_service.command_pause()
                    logger.info(f"[HADiscovery] Pause: {result}")
                elif command == 'dock' and worx_cloud_service.is_connected:
                    result = worx_cloud_service.command_stop()
                    logger.info(f"[HADiscovery] Dock/Home: {result}")
                else:
                    logger.warning(f"[HADiscovery] Unbekannter Befehl: {command}")
            except Exception as e:
                logger.error(f"[HADiscovery] Fehler beim Verarbeiten des HA-Befehls: {e}")

        # Subscriben auf das HA Command Topic
        cmd_topic = ha_discovery.get_command_topic()
        mqtt_service.handler.client.subscribe(cmd_topic, qos=1)
        mqtt_service.handler.client.message_callback_add(cmd_topic, lambda client, userdata, msg: on_ha_command(msg.topic, msg.payload.decode()))
        logger.info(f"[HADiscovery] Lausche auf HA-Befehle: {cmd_topic}")
        
        if worx_cloud_service.start():
            logger.info("[System] Worx Cloud Service verbunden (Autopilot + HA Discovery aktiv).")
        else:
            logger.warning("[System] Worx Cloud Service konnte nicht starten. Autopilot inaktiv.")



    except Exception as e:

        logger.critical(f"Fehler bei der Initialisierung der Services: {e}", exc_info=True)

        # Beende die Anwendung, wenn kritische Services nicht starten können

        if mqtt_service: mqtt_service.disconnect()

        if system_monitor: system_monitor.stop()

        sys.exit(1)



    port = int(os.getenv('FLASK_PORT', 5000))

    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']



    logger.info(f"Starte Flask-SocketIO WebUI auf http://0.0.0.0:{port} (Debug: {debug_mode})")

    try:

        socketio.run(app, host='0.0.0.0', port=port, use_reloader=False, debug=debug_mode, allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:

        logger.info("Server wird durch Benutzer beendet.")

    except Exception as e:

        logger.error(f"Fehler beim Starten des Servers: {e}", exc_info=True)

    finally:

        logger.info("Server wird heruntergefahren...")

        # --- Cleanup der Services (Pseudocode) ---

        if worx_cloud_service:

            worx_cloud_service.stop()

        if system_monitor:

            system_monitor.stop()

        if mqtt_service:

            mqtt_service.disconnect()

        logger.info("WebUI beendet.")

