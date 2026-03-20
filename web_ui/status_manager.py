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
            'hdop': 0.0,
            'agps_status': "N/A",
            'mower_status': "Unbekannt",
            'is_recording': False, 
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

    def _emit_socketio_event(self, event_name, data_to_emit, description):
        """Hilfsfunktion zum sicheren Senden von SocketIO-Events."""
        if self.socketio:
            try:
                self.socketio.emit(event_name, data_to_emit)
                logger.debug(f"{description} Socket.IO Update gesendet: Event '{event_name}'.")
            except Exception as e:
                logger.error(f"Fehler beim Senden von Socket.IO Event '{event_name}' für {description}: {e}", exc_info=True)
        else:
            logger.warning(f"SocketIO Instanz nicht verfügbar für {description} Event '{event_name}'.")

    def update_mower_status(self, payload_str, geo_config):
        """Aktualisiert den Mäherstatus basierend auf dem MQTT-Payload und sendet Update."""
        status_to_emit = None # Variable, um den Status nach dem Lock zu speichern

        with self.lock:
            try:
                if payload_str.startswith("status,"):
                    parts = payload_str.split(',')
                    if len(parts) >= 5: # status,fix_desc,sats,lat,lon[,agps_info]
                        status_text = parts[1]
                        satellites = int(parts[2]) if parts[2] and parts[2].lower() != 'n/a' else 0
                        lat_str = parts[3]
                        lon_str = parts[4]
                        
                        # Extrahiere HDOP (könnte an 6. Stelle stehen: status,fix,sats,lat,lon,agps,hdop)
                        # Wir schauen, ob agps oder hdop vorhanden sind
                        agps_status = "N/A"
                        hdop_val = 0.0
                        if len(parts) > 5:
                            agps_status = parts[5]
                        if len(parts) > 6:
                            try:
                                hdop_val = float(parts[6])
                            except (ValueError, TypeError):
                                pass

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
                            'hdop': hdop_val,
                            'lat': lat_val,
                            'lon': lon_val,
                            'agps_status': agps_status,
                            'last_update': datetime.now().strftime("%H:%M:%S")
                        })
                        logger.debug(f"Mäher-Statusdaten aktualisiert (ohne is_recording/mower_status): {self.current_mower_status}")
                    else:
                        logger.warning(f"Status-Payload hat nicht genügend Teile: {payload_str}")
                elif "recording started" in payload_str:
                    self.current_mower_status['is_recording'] = True
                    self.current_mower_status['mower_status'] = "Aufnahme läuft"
                elif "recording stopped" in payload_str:
                    self.current_mower_status['is_recording'] = False
                    self.current_mower_status['mower_status'] = "Aufnahme gestoppt"
                # Weitere Status-Nachrichten hier verarbeiten

                # Hole den Status *innerhalb* des Locks, aber sende *außerhalb*
                status_to_emit = self.current_mower_status.copy() # Sicherstellen, dass wir eine Kopie haben

            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten des Mäher-Status im Lock: {e}", exc_info=True)
                # Auch im Fehlerfall versuchen, den zuletzt bekannten Status zu senden
                status_to_emit = self.current_mower_status.copy()

        # Emit the update *after* releasing the lock
        if status_to_emit:
            self._emit_socketio_event('status_update', status_to_emit, "Mäher-Status")


    def update_pi_status(self, payload_str):
        """Aktualisiert den Pi-Status (z.B. Temperatur) und sendet Update."""
        pi_status_to_emit = None # Variable, um den Status nach dem Lock zu speichern

        with self.lock:
            try:
                temp_value = float(payload_str)
                self.current_pi_status['temperature'] = round(temp_value, 1)
                self.current_pi_status['last_update'] = datetime.now().strftime("%H:%M:%S")
                logger.debug(f"Pi-Status aktualisiert: {self.current_pi_status}")
                # Hole den Status *innerhalb* des Locks, aber sende *außerhalb*
                pi_status_to_emit = self.current_pi_status.copy()

            except ValueError:
                logger.warning(f"Ungültiger Pi-Status Payload (Temperatur) im Lock: {payload_str}")
                # Auch im Fehlerfall versuchen, den zuletzt bekannten Status zu senden
                pi_status_to_emit = self.current_pi_status.copy()
            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten des Pi-Status im Lock: {e}", exc_info=True)
                # Auch im Fehlerfall versuchen, den zuletzt bekannten Status zu senden
                pi_status_to_emit = self.current_pi_status.copy()

        # Emit the update *after* releasing the lock
        if pi_status_to_emit:
            self._emit_socketio_event('pi_status_update', pi_status_to_emit, "Pi-Status")


    def update_system_stats(self, stats_dict):
        """Aktualisiert die Systemstatistiken und sendet Update."""
        system_stats_to_emit = None # Variable, um den Status nach dem Lock zu speichern

        with self.lock:
            try:
                self.current_system_stats.update(stats_dict)
                logger.debug(f"System-Statistiken aktualisiert: {self.current_system_stats}")
                # Hole den Status *innerhalb* des Locks, aber sende *außerhalb*
                system_stats_to_emit = self.current_system_stats.copy()
            except Exception as e: # Catch potential errors during update
                logger.error(f"Fehler beim Aktualisieren der System-Statistiken im Lock: {e}", exc_info=True)
                system_stats_to_emit = self.current_system_stats.copy() # Send last known good or initial

        # Emit the update *after* releasing the lock
        if system_stats_to_emit is not None: # Sicherstellen, dass es nicht None ist
            self._emit_socketio_event('system_update', system_stats_to_emit, "System-Statistiken")


    def get_current_mower_status(self):
        with self.lock:
            return self.current_mower_status.copy()

    def get_current_pi_status(self):
        with self.lock:
            return self.current_pi_status.copy()

    def get_current_system_stats(self):
        with self.lock:
            return self.current_system_stats.copy()
