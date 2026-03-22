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
    from utils import calculate_distance, format_duration, read_gps_data_from_csv_string, flatten_data, calculate_area_coverage
    from processing import apply_moving_average, apply_kalman_filter, remove_outliers_by_speed, process_gps_data
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
        
        # Prüfen ob wir im HA Add-on laufen
        ha_data_dir = Path("/data")
        if ha_data_dir.exists() and ha_data_dir.is_dir():
            # Im HA Add-on: nutze persistentes /data Verzeichnis
            self.data_dir = ha_data_dir / "worx_gps"
            self.heatmaps_dir = ha_data_dir / "worx_gps" / "heatmaps"
            logger.info("DataService: HA Add-on erkannt, nutze /data/worx_gps")
        else:
            # Lokale Entwicklung
            self.data_dir = self.project_root / "data"
            self.heatmaps_dir = self.project_root / "heatmaps"
            logger.info("DataService: Lokale Entwicklung, nutze Projekt-Verzeichnisse")

        self.heatmap_config = heatmap_config
        self.problem_config = problem_config
        self.geo_config_main = geo_config_main # GEO_CONFIG aus config.py
        self.rec_config_main = rec_config_main # REC_CONFIG aus config.py

        self.data_manager = DataManager(data_folder=str(self.data_dir))
        self.heatmap_generator = HeatmapGenerator(heatmaps_base_dir=str(self.heatmaps_dir))
        
        # GPS-Datenpuffer für Session-Daten (wie Worx_GPS.py)
        self._gps_data_buffer = ""
        # Letzte Sessions für Karten-Generierung
        self._alle_maehvorgang_data = self.data_manager.load_all_mow_data()
        from collections import deque
        self._maehvorgang_data = deque(maxlen=10)
        if self._alle_maehvorgang_data:
            num_to_load = min(len(self._alle_maehvorgang_data), 10)
            for session in self._alle_maehvorgang_data[-num_to_load:]:
                if isinstance(session, list):
                    self._maehvorgang_data.append(session)
        
        logger.info("DataService initialisiert.")

    def handle_gps_data(self, csv_data):
        """Verarbeitet empfangene GPS-Daten vom MQTT (wie Worx_GPS.handle_gps_data)."""
        if csv_data != "-1":
            self._gps_data_buffer += csv_data
            logger.debug(f"GPS-Puffer aktualisiert, Größe: {len(self._gps_data_buffer)}")
            return
        
        logger.info("End-Marker für GPS-Daten empfangen, verarbeite Puffer...")
        
        raw_gps_data = read_gps_data_from_csv_string(self._gps_data_buffer)
        self._gps_data_buffer = ""
        
        if not raw_gps_data:
            logger.warning("Keine GPS-Daten aus dem Puffer gelesen.")
            return
        
        logger.info(f"{len(raw_gps_data)} GPS-Punkte aus Puffer gelesen.")
        original_count = len(raw_gps_data)
        
        # Geofences laden für Filterung
        geofences = self.data_manager.get_geofences() if self.data_manager else None
        
        # Zentrale Processing-Pipeline (HDOP, Geofence, Drift, Speed, Kalman)
        processed_data = process_gps_data(
            raw_gps_data,
            config.POST_PROCESSING_CONFIG,
            geofences=geofences
        )
        
        if not processed_data:
            logger.warning("Nach Filterung keine GPS-Daten übrig.")
            return
        
        logger.info(f"Verarbeitung: {len(processed_data)} Punkte (von {original_count}).")
        
        # Session speichern
        self._maehvorgang_data.append(processed_data)
        self._alle_maehvorgang_data.append(processed_data)
        
        l_bounds = self.geo_config_main.get("lat_bounds")
        ln_bounds = self.geo_config_main.get("lon_bounds")
        session_coverage = calculate_area_coverage(processed_data, l_bounds, ln_bounds)
        
        filename = self.data_manager.get_next_mow_filename()
        self.data_manager.save_gps_data(processed_data, filename, coverage=session_coverage)
        
        logger.info(f"Session {filename} in DB gespeichert. Starte Karten-Generierung...")
        try:
            self._generate_all_heatmaps(processed_data)
        except Exception as e:
            logger.error(f"Fehler bei automatischer Karten-Generierung: {e}", exc_info=True)

    def _generate_all_heatmaps(self, current_session_data):
        """Generiert alle Heatmaps nach einer abgeschlossenen Session."""
        # Sicherstellen dass das Verzeichnis existiert
        self.heatmaps_dir.mkdir(parents=True, exist_ok=True)
        
        draw_path = self.geo_config_main.get("draw_path", True)
        
        # 1. Aktuelle Session (heatmap_aktuell)
        if 'heatmap_aktuell' in self.heatmap_config:
            self._update_map('heatmap_aktuell', current_session_data, draw_path)
        
        # 2. Letzte 10 Sessions (heatmap_10)
        if 'heatmap_10' in self.heatmap_config:
            combined_10 = flatten_data(list(self._maehvorgang_data))
            if combined_10:
                self._update_map('heatmap_10', combined_10, draw_path, is_multi=True)
        
        # 3. Alle Sessions kumuliert (heatmap_kumuliert)
        if 'heatmap_kumuliert' in self.heatmap_config:
            combined_all = flatten_data(self._alle_maehvorgang_data)
            if combined_all:
                self._update_map('heatmap_kumuliert', combined_all, draw_path, is_multi=True)
        
        # 4. GPS-Qualität (letzte 10 Sessions)
        if 'quality_path_10' in self.heatmap_config:
            combined_10 = flatten_data(list(self._maehvorgang_data))
            if combined_10:
                self._update_map('quality_path_10', combined_10, draw_path, is_multi=True)
        
        # 5. WiFi Signalstärke (letzte 10 Sessions)
        if 'wifi_heatmap' in self.heatmap_config:
            combined_10 = flatten_data(list(self._maehvorgang_data))
            if combined_10:
                self._update_map('wifi_heatmap', combined_10, draw_path, is_multi=True)
        
        # 6. GPS-Qualität kumuliert (alle Sessions)
        if 'quality_kumuliert' in self.heatmap_config:
            combined_all = flatten_data(self._alle_maehvorgang_data)
            if combined_all:
                self._update_map('quality_kumuliert', combined_all, draw_path, is_multi=True)
        
        # 7. WiFi Signalstärke kumuliert (alle Sessions)
        if 'wifi_kumuliert' in self.heatmap_config:
            combined_all = flatten_data(self._alle_maehvorgang_data)
            if combined_all:
                self._update_map('wifi_kumuliert', combined_all, draw_path, is_multi=True)
        
        logger.info("[DataService] Alle Heatmaps erfolgreich generiert.")

    def _update_map(self, config_key, data, draw_path, is_multi=False):
        """Aktualisiert eine einzelne Karte (wie Worx_GPS.update_single_map)."""
        if config_key not in self.heatmap_config:
            logger.warning(f"Karten-Key '{config_key}' nicht in HEATMAP_CONFIG.")
            return
        
        map_config = self.heatmap_config[config_key]
        html_output = map_config["output"]
        
        if not data:
            logger.warning(f"Keine Daten für Karte '{config_key}'.")
            return
        
        try:
            self.heatmap_generator.create_heatmap(data, html_output, draw_path, is_multi_session=is_multi)
            logger.info(f"Karte '{config_key}' aktualisiert -> {html_output}")
        except Exception as e:
            logger.error(f"Fehler bei Karte '{config_key}': {e}", exc_info=True)

    def get_available_heatmaps(self):
        """Gibt eine Liste der verfügbaren Heatmap-Dateien zurück."""
        heatmaps = []
        if not self.heatmaps_dir.exists():
            logger.warning(f"Heatmap-Verzeichnis {self.heatmaps_dir} nicht gefunden.")
            return heatmaps

        # Sprechende Namen für die Karten (Keys = Dateiname ohne .html)
        display_names = {
            "heatmap_aktuell": "Aktueller Mähvorgang",
            "heatmap_10": "Letzte 10 Mähvorgänge",
            "heatmap_kumuliert": "Alle Mähvorgänge (Kumuliert)",
            "quality": "GPS Qualität (Letzte 10)",
            "quality_kumuliert": "GPS Qualität (Kumuliert)",
            "wifi": "WiFi Signalstärke (Letzte 10)",
            "wifi_kumuliert": "WiFi Signalstärke (Kumuliert)",
            "problemzonen": "Problemzonen",
        }

        for html_file in self.heatmaps_dir.glob("*.html"):
            map_id = html_file.stem
            map_name = display_names.get(map_id, map_id.replace("_", " ").title())
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
        logger.debug(f"DataService:get_formatted_problem_zones - {len(raw_problem_zones)} Roh-Problemzonen empfangen.")
        logger.debug(f"DataService:get_formatted_problem_zones - Erste 3 Roh-Problemzonen (falls vorhanden): {raw_problem_zones[:3]}")

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
                    logger.debug(f"  Problem-Loop: Timestamp for {problem.get('timestamp')} formatted to {formatted_problem['zeitpunkt']}")
                except (ValueError, TypeError):
                    formatted_problem['zeitpunkt'] = "Ungültiger Zeitstempel"
                    logger.warning(f"Ungültiger Unix-Zeitstempel in Problemzone gefunden: {timestamp_unix}")
            else:
                formatted_problem['zeitpunkt'] = "N/A"

            # Format Position
            lat = problem.get('lat')
            lon = problem.get('lon')
            logger.debug(f"  Problem-Loop: Processing item: {problem}, Got lat: {lat}, lon: {lon}")
            if lat is not None and lon is not None:
                try:
                    # Format coordinates to a string
                    logger.debug(f"    Problem-Loop: Formatting valid lat/lon: {lat}, {lon}")
                    formatted_problem['position'] = f"Lat: {lat:.6f}, Lon: {lon:.6f}"
                    # Also provide separate formatted lat/lon in case the template wants them
                    formatted_problem['lat_formatted'] = f"{lat:.6f}"
                    formatted_problem['lon_formatted'] = f"{lon:.6f}"
                except (ValueError, TypeError):
                     formatted_problem['position'] = "Ungültige Koordinaten"
                     formatted_problem['lat_formatted'] = "N/A"
                     formatted_problem['lon_formatted'] = "N/A"
                     logger.warning(f"    Problem-Loop: ValueError/TypeError formatting lat/lon. Original lat: {problem.get('lat')}, lon: {problem.get('lon')}")
                     logger.warning(f"Ungültige Lat/Lon Werte in Problemzone gefunden: Lat={lat}, Lon={lon}")
            else:
                formatted_problem['position'] = "Position N/A"
                formatted_problem['lat_formatted'] = "N/A"
                formatted_problem['lon_formatted'] = "N/A"
                logger.debug(f"    Problem-Loop: Lat or Lon is None. Original lat: {problem.get('lat')}, lon: {problem.get('lon')}. Setting to N/A.")

            formatted_zones.append(formatted_problem)

        return formatted_zones

    def _calculate_coverage(self, sessions, grid_size_m=0.5):
        """Berechnet den prozentualen Anteil der abgedeckten Fläche im Geofence."""
        if not STATS_LIBS_AVAILABLE or not sessions:
            return 0.0

        lat_bounds = self.geo_config_main.get("lat_bounds")
        lon_bounds = self.geo_config_main.get("lon_bounds")

        if not lat_bounds or not lon_bounds:
            return 0.0

        bottom_left = (lat_bounds[0], lon_bounds[0])
        top_left = (lat_bounds[1], lon_bounds[0])
        bottom_right = (lat_bounds[0], lon_bounds[1])

        try:
            height_m = geodesic(bottom_left, top_left).meters
            width_m = geodesic(bottom_left, bottom_right).meters

            if height_m == 0 or width_m == 0:
                return 0.0

            cols = int(width_m / grid_size_m) + 1
            rows = int(height_m / grid_size_m) + 1
            total_cells = cols * rows

            visited_cells = set()
            for session_data in sessions:
                if isinstance(session_data, dict):
                    session_points = session_data.get('data', [])
                else:
                    session_points = session_data

                for point in session_points:
                    try:
                        lat = float(point.get('lat', 0))
                        lon = float(point.get('lon', 0))
                        if lat_bounds[0] <= lat <= lat_bounds[1] and lon_bounds[0] <= lon <= lon_bounds[1]:
                            col = int((lon - lon_bounds[0]) / (lon_bounds[1] - lon_bounds[0]) * cols)
                            row = int((lat - lat_bounds[0]) / (lat_bounds[1] - lat_bounds[0]) * rows)
                            visited_cells.add((row, col))
                    except (ValueError, TypeError):
                        pass

            coverage = (len(visited_cells) / total_cells) * 100
            # Mähroboter überlappen oft, also könnten wir eine höhere Rate extrapolieren. 
            # Multiplikator um auf realistische 100% zu kommen
            coverage = coverage * 1.5 
            return round(min(100.0, coverage), 1)

        except Exception as e:
            logger.error(f"Fehler bei _calculate_coverage: {e}")
            return 0.0

    def get_statistics(self):
        """Berechnet Statistiken aus den Mähdaten."""
        if not STATS_LIBS_AVAILABLE:
            return {"error": "Statistikbibliotheken (pandas/geopy) nicht verfügbar."}

        all_mow_data = self.data_manager.load_all_mow_data()
        if not all_mow_data:
            return {"total_recordings": 0, "total_distance": 0.0, "total_time": 0, "avg_satellites": 0.0, "problem_zones_count": 0, "avg_distance": 0.0, "avg_duration": 0.0, "total_coverage": 0.0, "last_coverage": 0.0}

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
        
        # Kumulative Coverage über alle Sessions
        total_coverage = self._calculate_coverage(all_mow_data)

        # Letzte Session Coverage
        last_coverage = 0.0
        if valid_sessions_for_avg > 0:
             last_coverage = self._calculate_coverage([all_mow_data[-1]])

        return {
            "total_recordings": len(all_mow_data),
            "total_distance": round(total_distance_km, 2),
            "total_time": round(total_duration_minutes),
            "avg_satellites": round(total_satellites_sum / total_satellite_points, 1) if total_satellite_points > 0 else 0.0,
            "problem_zones_count": len(problem_zones),
            "avg_distance": round(total_distance_km / valid_sessions_for_avg, 2) if valid_sessions_for_avg > 0 else 0.0,
            "avg_duration": round(total_duration_minutes / valid_sessions_for_avg, 1) if valid_sessions_for_avg > 0 else 0.0,
            "total_coverage": total_coverage,
            "last_coverage": last_coverage,
        }

    def get_mow_sessions_for_display(self):
        """Ruft Details zu allen Mähvorgängen ab und formatiert sie für die Anzeige."""
        sessions = self.data_manager.get_all_mow_session_details()
        formatted_sessions = []
        for session in sessions:
            session_data = session.get("data", [])
            duration_seconds = 0
            distance_m = 0
            start_time_str = "N/A"

            if session_data:
                timestamps = [p.get('timestamp') for p in session_data if p.get('timestamp') is not None]
                if timestamps:
                    min_ts = min(timestamps)
                    max_ts = max(timestamps)
                    duration_seconds = max_ts - min_ts
                    start_time_str = datetime.fromtimestamp(min_ts).strftime('%Y-%m-%d %H:%M:%S')
                
                for i in range(len(session_data) - 1):
                    distance_m += calculate_distance(session_data[i], session_data[i+1])
                    
            coverage = session.get("coverage", 0.0)

            formatted_sessions.append({
                "filename": session.get("filename"),
                "start_time_str": start_time_str,
                "point_count": session.get("point_count"),
                "duration_str": format_duration(duration_seconds),
                "distance_km_str": f"{distance_m / 1000:.2f} km" if distance_m > 0 else "0.00 km",
                "coverage_str": f"{coverage}%"
            })
        return formatted_sessions

    def delete_mow_session(self, filename: str) -> bool:
        """Löscht eine Mähsession und gibt True bei Erfolg zurück."""
        return self.data_manager.delete_mow_session_file(filename)

    # --- Geofencing (Zoneneditor) ---
    def get_geofences(self):
        """Lädt alle Geofences (Zonen) aus dem DataManager."""
        return self.data_manager.get_geofences()

    def save_geofence(self, name, type, coordinates, fence_id=None):
        """Speichert oder aktualisiert eine Zone im DataManager."""
        return self.data_manager.save_geofence(name, type, coordinates, fence_id)

    def delete_geofence(self, geofence_id):
        """Löscht eine Zone aus dem DataManager."""
        return self.data_manager.delete_geofence(geofence_id)

# Benötigt für url_for in get_available_heatmaps, wird von Flask bereitgestellt
from flask import url_for