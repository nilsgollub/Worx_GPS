# web_ui/status_manager.py
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class StatusManager:
    def __init__(self, socketio_instance, initial_map_center=(0.0, 0.0)):
        self.socketio = socketio_instance
        self.lock = threading.Lock()

        self.current_mower_status = {
            'lat': initial_map_center[0],
            'lon': initial_map_center[1],
            'status_text': "Initialisiere...",
            'satellites': 0,
            'agps_status': "N/A",
            'mower_status': "Unbekannt",
            'is_recording': False, # Wird von der WebUI oder einem anderen Service gesetzt
            'last_update': datetime.now().strftime("%H:%M:%S")
        }
        self.current_pi_status = {
            'temperature': None,
            'last_update': "N/A"
        }
        self.current_system_stats = {
            'cpu_load': 0.0,
            'ram_usage': 0.0,
            'cpu_temp': None
        }
        logger.info("StatusManager initialisiert.")

    def update_mower_status(self, payload_str, geo_config):
        """Aktualisiert den Mäherstatus basierend auf dem MQTT-Payload."""
        with self.lock:
            try:
                if payload_str.startswith("status,"):
                    parts = payload_str.split(',')
                    if len(parts) >= 5: # status,fix_desc,sats,lat,lon[,agps_info]
                        status_text = parts[1]
                        satellites = int(parts[2]) if parts[2] else 0
                        lat_str = parts[3]
                        lon_str = parts[4]
                        agps_status = parts[5] if len(parts) > 5 else "N/A"
                        # mower_status wird hier nicht direkt aus dem GPS-String gelesen,
                        # könnte aber aus einem anderen Teil des Payloads kommen oder
                        # durch Befehle (START_REC/STOP_REC) beeinflusst werden.

                        lat_val, lon_val = None, None
                        if lat_str and lat_str.lower() != 'n/a' and \
                           lon_str and lon_str.lower() != 'n/a':
                            try:
                                temp_lat = float(lat_str)
                                temp_lon = float(lon_str)
                                lat_bounds = geo_config.get("lat_bounds")
                                lon_bounds = geo_config.get("lon_bounds")
                                if (not lat_bounds or (lat_bounds[0] <= temp_lat <= lat_bounds[1])) and \
                                   (not lon_bounds or (lon_bounds[0] <= temp_lon <= lon_bounds[1])):
                                    lat_val = temp_lat
                                    lon_val = temp_lon
                                else:
                                    logger.warning(f"Koordinaten außerhalb der Grenzen: Lat '{temp_lat}', Lon '{temp_lon}'")
                            except ValueError:
                                logger.warning(f"Konnte Lat/Lon nicht in Float konvertieren: '{lat_str}', '{lon_str}'")

                        self.current_mower_status.update({
                            'status_text': status_text,
                            'satellites': satellites,
                            'lat': lat_val,
                            'lon': lon_val,
                            'agps_status': agps_status,
                            'last_update': datetime.now().strftime("%H:%M:%S")
                        })
                        logger.debug(f"Mäher-Status aktualisiert: {self.current_mower_status}")
                        self.socketio.emit('status_update', self.get_current_mower_status())
                    else:
                        logger.warning(f"Status-Payload hat nicht genügend Teile: {payload_str}")
                elif "recording started" in payload_str:
                    self.current_mower_status['is_recording'] = True
                    self.current_mower_status['mower_status'] = "Aufnahme läuft"
                    self.socketio.emit('status_update', self.get_current_mower_status())
                elif "recording stopped" in payload_str:
                    self.current_mower_status['is_recording'] = False
                    self.current_mower_status['mower_status'] = "Aufnahme gestoppt"
                    self.socketio.emit('status_update', self.get_current_mower_status())
                # Weitere Status-Nachrichten hier verarbeiten

            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten des Mäher-Status: {e}", exc_info=True)

    def update_pi_status(self, payload_str):
        """Aktualisiert den Pi-Status (z.B. Temperatur)."""
        with self.lock:
            try:
                temp_value = float(payload_str)
                self.current_pi_status['temperature'] = round(temp_value, 1)
                self.current_pi_status['last_update'] = datetime.now().strftime("%H:%M:%S")
                logger.debug(f"Pi-Status aktualisiert: {self.current_pi_status}")
                self.socketio.emit('pi_status_update', self.get_current_pi_status())
            except ValueError:
                logger.warning(f"Ungültiger Pi-Status Payload (Temperatur): {payload_str}")
            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten des Pi-Status: {e}", exc_info=True)

    def update_system_stats(self, stats_dict):
        """Aktualisiert die Systemstatistiken und sendet sie."""
        with self.lock:
            self.current_system_stats.update(stats_dict)
            logger.debug(f"System-Statistiken aktualisiert: {self.current_system_stats}")
            self.socketio.emit('system_update', self.get_current_system_stats())

    def get_current_mower_status(self):
        with self.lock:
            return self.current_mower_status.copy()

    def get_current_pi_status(self):
        with self.lock:
            return self.current_pi_status.copy()

    def get_current_system_stats(self):
        with self.lock:
            return self.current_system_stats.copy()