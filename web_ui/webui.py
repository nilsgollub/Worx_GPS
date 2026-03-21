# webui.py (Überarbeitete Struktur - Konzeptionell)



import logging



import logging

import os

import sys

import threading

import json

import time

from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for

from flask_socketio import SocketIO

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



# --- Logging ---

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s') # Geändert auf DEBUG und detaillierteres Format

logger = logging.getLogger(__name__)



# --- Flask & SocketIO Setup ---

app = Flask(__name__)

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



# --- Flask Routen (Interagieren mit Service-Instanzen) ---



@app.route('/', defaults={'path': ''})

@app.route('/<path:path>')

def serve_react(path):

    """

    Serve the React UI. If a file exists in the static folder, send it.

    Otherwise, send index.html and let React Router handle the route.

    """

    if path and path.startswith('api/'):

        return jsonify({"error": "API route not found"}), 404

        

    full_path = os.path.join(app.static_folder, path)

    if path != "" and os.path.exists(full_path):

        return send_from_directory(app.static_folder, path)

    else:

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



@app.route('/maps')

def maps():

    """Kartenübersicht"""

    if not data_service:

        logger.error("DataService nicht initialisiert in maps Route.")

        return "Fehler: DataService nicht initialisiert.", 503



    heatmaps = data_service.get_available_heatmaps()

    if heatmaps is None: heatmaps = [] # Sicherstellen, dass es eine Liste ist

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

    """Liefert Heatmap-Dateien"""

    # Der Pfad wird relativ zum Projekt-Root + 'heatmaps' sein

    heatmap_dir = os.path.join(project_root, 'heatmaps') # Oder data_service.get_heatmap_dir()

    if '..' in filename or filename.startswith('/'): return "Ungültiger Dateiname", 400

    return send_from_directory(heatmap_dir, filename)





@app.route('/config')

def config_page():

    """Konfigurationsseite"""

    if not data_service:

        logger.error("DataService nicht initialisiert in config_page Route.")

        return "Fehler: DataService nicht initialisiert.", 503



    editable_config = data_service.get_editable_config()

    info = data_service.get_config_info()



    template_path = os.path.join(app.template_folder, 'config.html')

    if not os.path.exists(template_path):

        logger.error(f"Template 'config.html' nicht gefunden in {app.template_folder}")

        return "Fehler: Template 'config.html' nicht gefunden.", 500



    return render_template('config.html', config=editable_config, info=info)





@app.route('/config/save', methods=['POST'])

def save_config():

    """Speichert Konfigurationsänderungen"""

    try:

        if not data_service: # data_service wird hier nicht direkt verwendet, aber zur Konsistenz

            logger.error("DataService nicht initialisiert in save_config Route.")

            return jsonify({"success": False, "message": "Serverfehler: DataService nicht bereit."}), 503



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





@app.route('/stats')

def stats():

    """Statistikseite"""

    if not data_service:

        logger.error("DataService nicht initialisiert in stats Route.") # Keep this check

        return "Fehler: DataService nicht initialisiert.", 503



    stats_data = data_service.get_statistics()

    formatted_problem_zones = data_service.get_formatted_problem_zones()

    mow_sessions = data_service.get_mow_sessions_for_display() # NEU

    logger.debug(f"Formatted problem zones being passed to template: {formatted_problem_zones[:5]}")

    logger.debug(f"Mow sessions for display: {mow_sessions[:3]}") # NEU: Log für Mähvorgänge



    template_path = os.path.join(app.template_folder, 'stats.html')

    if not os.path.exists(template_path):

        logger.error(f"Template 'stats.html' nicht gefunden in {app.template_folder}")

        return "Fehler: Template 'stats.html' nicht gefunden.", 500

    return render_template('stats.html',

                           stats=stats_data,

                           problem_zones=formatted_problem_zones,

                           mow_sessions=mow_sessions) # NEU: Mähvorgänge an Template übergeben



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

        # Optional: mqtt_service.set_gps_update_callback(...)

        mqtt_service.connect()



        data_service = DataService(

            project_root_path=project_root,

            heatmap_config=config.HEATMAP_CONFIG,

            problem_config=config.PROBLEM_CONFIG,

            geo_config_main=config.GEO_CONFIG,

            rec_config_main=config.REC_CONFIG

        )



        system_monitor = SystemMonitor(status_manager.update_system_stats)

        system_monitor.start()



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

        socketio.run(app, host='0.0.0.0', port=port, use_reloader=False, debug=debug_mode)

    except KeyboardInterrupt:

        logger.info("Server wird durch Benutzer beendet.")

    except Exception as e:

        logger.error(f"Fehler beim Starten des Servers: {e}", exc_info=True)

    finally:

        logger.info("Server wird heruntergefahren...")

        # --- Cleanup der Services (Pseudocode) ---

        if system_monitor:

            system_monitor.stop()

        if mqtt_service:

            mqtt_service.disconnect()

        logger.info("WebUI beendet.")

