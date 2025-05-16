# web_ui/data_service.py
import logging
import os
import json
from pathlib import Path
from dotenv import dotenv_values, find_dotenv
import sys

# Füge das übergeordnete Verzeichnis zum Suchpfad hinzu
from datetime import datetime # Importiere datetime
project_root_ui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root_base = os.path.dirname(project_root_ui)
if project_root_base not in sys.path:
    sys.path.insert(0, project_root_base)

try:
    from data_manager import DataManager
    from heatmap_generator import HeatmapGenerator
    import config # Haupt-Konfigurationsdatei
    # Importiere pandas und geopy für Statistiken, falls verfügbar
    from utils import calculate_distance, format_duration # Importiere Hilfsfunktionen
    STATS_LIBS_AVAILABLE = True
    try:
        import pandas as pd
        from geopy.distance import geodesic # Wird hier nicht direkt verwendet, aber als Indikator
    except ImportError:
        STATS_LIBS_AVAILABLE = False
        logging.warning("pandas oder geopy nicht gefunden. Statistiken sind nur eingeschränkt verfügbar.")

except ImportError as e:
    logging.error(f"Fehler beim Importieren von Modulen in data_service.py: {e}")
    raise

logger = logging.getLogger(__name__)

class DataService:
    def __init__(self, project_root_path, heatmap_config, problem_config, geo_config_main, rec_config_main):
        self.project_root = Path(project_root_path)
        self.heatmaps_dir = self.project_root / "heatmaps"
        self.data_dir = self.project_root / "data" # Für DataManager

        self.heatmap_config = heatmap_config
        self.problem_config = problem_config
        self.geo_config_main = geo_config_main # GEO_CONFIG aus config.py
        self.rec_config_main = rec_config_main # REC_CONFIG aus config.py

        self.data_manager = DataManager(data_folder=str(self.data_dir))
        self.heatmap_generator = HeatmapGenerator(heatmaps_base_dir=str(self.heatmaps_dir))
        logger.info("DataService initialisiert.")

    def get_available_heatmaps(self):
        """Gibt eine Liste der verfügbaren Heatmap-Dateien zurück."""
        heatmaps = []
        if not self.heatmaps_dir.exists():
            logger.warning(f"Heatmap-Verzeichnis {self.heatmaps_dir} nicht gefunden.")
            return heatmaps

        for html_file in self.heatmaps_dir.glob("*.html"):
            map_id = html_file.stem
            map_name = map_id.replace("_", " ").title()
            png_path = html_file.with_suffix(".png")
            heatmaps.append({
                "id": map_id,
                "name": map_name,
                "html_path": url_for('serve_heatmap', filename=html_file.name),
                "png_path": url_for('serve_heatmap', filename=png_path.name) if png_path.exists() else None
            })
        return sorted(heatmaps, key=lambda x: x['name'])

    def get_current_heatmap_path(self):
        """Gibt den Pfad zur 'heatmap_aktuell.html' zurück, falls vorhanden."""
        current_heatmap_file = self.heatmaps_dir / "heatmap_aktuell.html"
        if current_heatmap_file.exists():
            return url_for('serve_heatmap', filename="heatmap_aktuell.html")
        return None

    def get_editable_config(self):
        """Liest editierbare Konfigurationswerte aus .env und config.py Defaults."""
        env_values = dotenv_values(find_dotenv())

        def get_config_value(env_key, default_from_config, value_type=str):
            value_str = env_values.get(env_key)
            if value_str is None: # Nicht in .env, nimm Default aus config.py
                value_to_convert = default_from_config
            else: # Wert aus .env
                value_to_convert = value_str
            
            try:
                if value_type == bool: return str(value_to_convert).lower() in ['true', '1', 'yes', 'on']
                if value_type == int and value_to_convert is not None: return int(value_to_convert)
                return str(value_to_convert) if value_to_convert is not None else ""
            except (ValueError, TypeError):
                logger.warning(f"Fehler beim Konvertieren von '{env_key}' (Wert: '{value_to_convert}') zu {value_type}. Verwende Default: {default_from_config}")
                return default_from_config

        # Lade Defaults aus der Haupt-config.py
        cfg_heatmap_aktuell = self.heatmap_config.get('heatmap_aktuell', {})
        cfg_geo = self.geo_config_main
        cfg_rec = self.rec_config_main

        return {
            'HEATMAP': {
                'HEATMAP_RADIUS': get_config_value('HEATMAP_RADIUS', cfg_heatmap_aktuell.get('radius', 5), int),
                'HEATMAP_BLUR': get_config_value('HEATMAP_BLUR', cfg_heatmap_aktuell.get('blur', 10), int),
                'HEATMAP_GENERATE_PNG': get_config_value('HEATMAP_GENERATE_PNG', cfg_heatmap_aktuell.get('generate_png', False), bool),
            },
            'GEO': {
                'GEO_ZOOM_START': get_config_value('GEO_ZOOM_START', cfg_geo.get('zoom_start', 19), int),
                'GEO_MAX_ZOOM': get_config_value('GEO_MAX_ZOOM', cfg_geo.get('max_zoom', 22), int),
            },
            'REC': {
                'REC_STORAGE_INTERVAL': get_config_value('REC_STORAGE_INTERVAL', cfg_rec.get('storage_interval', 1), int),
                'TEST_MODE': get_config_value('TEST_MODE', cfg_rec.get('test_mode', False), bool),
            },
        }

    def get_config_info(self):
        """Gibt nicht-editierbare, aber informative Konfigurationswerte zurück."""
        # Diese Werte kommen direkt aus der geladenen config.py (oder .env via config.py)
        return {
            "mqtt_host": config.MQTT_CONFIG.get("host"),
            "mqtt_port": config.MQTT_CONFIG.get("port"),
            "mqtt_topic_status": config.MQTT_CONFIG.get("topic_status"),
            "mqtt_topic_gps": config.MQTT_CONFIG.get("topic_gps"),
            "mqtt_topic_control": config.MQTT_CONFIG.get("topic_control"),
            "test_mode": config.REC_CONFIG.get("test_mode"),
            "assist_now": config.ASSIST_NOW_CONFIG.get("assist_now_enabled"),
            "gps_serial_port": config.REC_CONFIG.get("serial_port"),
        }

    def get_problem_zones(self):
        """Lädt Problemzonen aus der Datei."""
        return self.data_manager.read_problemzonen_data()

    def get_formatted_problem_zones(self):
        """
        Lädt Problemzonen aus der Datei und formatiert sie für die Anzeige in der WebUI.
        Konvertiert Unix-Zeitstempel und formatiert Koordinaten.
        """
        raw_problem_zones = self.data_manager.read_problemzonen_data()
        formatted_zones = []

        for problem in raw_problem_zones:
            formatted_problem = {}
            # Format Timestamp
            timestamp_unix = problem.get('timestamp')
            if timestamp_unix is not None:
                try:
                    # Convert Unix timestamp (float) to datetime object
                    dt_object = datetime.fromtimestamp(timestamp_unix)
                    # Format datetime object to a readable string
                    formatted_problem['zeitpunkt'] = dt_object.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    formatted_problem['zeitpunkt'] = "Ungültiger Zeitstempel"
                    logger.warning(f"Ungültiger Unix-Zeitstempel in Problemzone gefunden: {timestamp_unix}")
            else:
                formatted_problem['zeitpunkt'] = "N/A"

            # Format Position
            lat = problem.get('lat')
            lon = problem.get('lon')
            if lat is not None and lon is not None:
                try:
                    # Format coordinates to a string
                    formatted_problem['position'] = f"Lat: {lat:.6f}, Lon: {lon:.6f}"
                    # Also provide separate formatted lat/lon in case the template wants them
                    formatted_problem['lat_formatted'] = f"{lat:.6f}"
                    formatted_problem['lon_formatted'] = f"{lon:.6f}"
                except (ValueError, TypeError):
                     formatted_problem['position'] = "Ungültige Koordinaten"
                     formatted_problem['lat_formatted'] = "N/A"
                     formatted_problem['lon_formatted'] = "N/A"
                     logger.warning(f"Ungültige Lat/Lon Werte in Problemzone gefunden: Lat={lat}, Lon={lon}")
            else:
                formatted_problem['position'] = "Position N/A"
                formatted_problem['lat_formatted'] = "N/A"
                formatted_problem['lon_formatted'] = "N/A"

            formatted_zones.append(formatted_problem)

        return formatted_zones

    def get_statistics(self):
        """Berechnet Statistiken aus den Mähdaten."""
        if not STATS_LIBS_AVAILABLE:
            return {"error": "Statistikbibliotheken (pandas/geopy) nicht verfügbar."}

        all_mow_data = self.data_manager.load_all_mow_data()
        if not all_mow_data:
            return {"total_recordings": 0, "total_distance": 0.0, "total_time": 0, "avg_satellites": 0.0, "problem_zones_count": 0, "avg_distance": 0.0, "avg_duration": 0.0}

        total_distance_km = 0
        total_duration_minutes = 0
        total_satellites_sum = 0
        total_satellite_points = 0
        valid_sessions_for_avg = 0

        for session in all_mow_data:
            if not session or len(session) < 2: continue
            valid_sessions_for_avg +=1
            session_distance_m = 0
            session_start_time = float(session[0].get('timestamp', 0))
            session_end_time = float(session[-1].get('timestamp', 0))

            for i in range(len(session) - 1):
                session_distance_m += calculate_distance(session[i], session[i+1])
                sats = session[i].get('satellites')
                if sats is not None:
                    total_satellites_sum += sats
                    total_satellite_points += 1
            
            total_distance_km += session_distance_m / 1000.0
            if session_end_time > session_start_time:
                total_duration_minutes += (session_end_time - session_start_time) / 60

        problem_zones = self.get_problem_zones()

        return {
            "total_recordings": len(all_mow_data),
            "total_distance": round(total_distance_km, 2),
            "total_time": round(total_duration_minutes),
            "avg_satellites": round(total_satellites_sum / total_satellite_points, 1) if total_satellite_points > 0 else 0.0,
            "problem_zones_count": len(problem_zones),
            "avg_distance": round(total_distance_km / valid_sessions_for_avg, 2) if valid_sessions_for_avg > 0 else 0.0,
            "avg_duration": round(total_duration_minutes / valid_sessions_for_avg, 1) if valid_sessions_for_avg > 0 else 0.0,
        }

# Benötigt für url_for in get_available_heatmaps, wird von Flask bereitgestellt
from flask import url_for