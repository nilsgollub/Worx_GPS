# web_ui/status_manager.py
import logging
import threading
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class StatusManager:
    def __init__(self, socketio_instance, initial_map_center=(0.0, 0.0)):
        self.socketio = socketio_instance
        self.lock = threading.Lock()
        self.ha_service = None
        self.mqtt_service = None

        self.current_mower_status = {
            'lat': initial_map_center[0],
            'lon': initial_map_center[1],
            'status_text': "Initialisiere...",
            'satellites': 0,
            'hdop': 0.0,
            'agps_status': "N/A",
            'mower_status': "Unbekannt",
            'is_recording': False, 
            'is_simulated': False,
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

    def update_mower_status(self, payload_str, geo_config, data_manager=None):
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
                        is_simulated = "Sim" in agps_status
                        
                        self.current_mower_status.update({
                            'agps_status': agps_status,
                            'hdop': hdop_val,
                            'is_simulated': is_simulated
                        })
                        if lat_str and lat_str.lower() != 'n/a' and \
                           lon_str and lon_str.lower() != 'n/a':
                            try:
                                temp_lat = float(lat_str)
                                temp_lon = float(lon_str)
                                
                                # 1. Grober rechteckiger Bounds-Check (Schnellfilter)
                                lat_bounds = geo_config.get("lat_bounds")
                                lon_bounds = geo_config.get("lon_bounds")
                                
                                is_inside = True
                                if lat_bounds and (not (lat_bounds[0] <= temp_lat <= lat_bounds[1])):
                                    is_inside = False
                                if lon_bounds and (not (lon_bounds[0] <= temp_lon <= lon_bounds[1])):
                                    is_inside = False
                                
                                # 2. Feiner Polygon-Geofence-Check (Präzisionsfilter)
                                if is_inside and data_manager:
                                    from utils import is_point_in_polygon
                                    geofences = data_manager.get_geofences()
                                    mow_areas = [f['coordinates'] for f in geofences if f.get('type') == 'mow_area']
                                    forbidden_areas = [f['coordinates'] for f in geofences if f.get('type') == 'forbidden_area']
                                    
                                    if mow_areas or forbidden_areas:
                                        # Wenn Erlaubt-Zonen da sind, MUSS er in einer sein
                                        if mow_areas:
                                            allowed = False
                                            for area in mow_areas:
                                                if is_point_in_polygon(temp_lat, temp_lon, area):
                                                    allowed = True
                                                    break
                                            if not allowed:
                                                is_inside = False
                                        
                                        # Wenn Verboten-Zonen da sind, darf er in KEINER sein
                                        if is_inside and forbidden_areas:
                                            for area in forbidden_areas:
                                                if is_point_in_polygon(temp_lat, temp_lon, area):
                                                    is_inside = False
                                                    break

                                if is_inside:
                                    lat_val = temp_lat
                                    lon_val = temp_lon
                                else:
                                    logger.warning(f"Koordinaten durch Geofence gefiltert: Lat '{temp_lat}', Lon '{temp_lon}'")
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
                        
                        # --- NEU: Verarbeitete Daten an HA via MQTT senden ---
                        if self.mqtt_service:
                            ha_payload = {
                                "geofence_ok": lat_val is not None,
                                "satellites": satellites,
                                "hdop": hdop_val,
                                "status": status_text,
                                "is_simulated": is_simulated,
                                "latitude": lat_val if lat_val is not None else self.current_mower_status.get('lat'),
                                "longitude": lon_val if lon_val is not None else self.current_mower_status.get('lon')
                            }
                            self.mqtt_service.publish("worx/processed", json.dumps(ha_payload))
                        # --- Ende NEU ---
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

    def set_ha_service(self, service):
        """Setzt den Home Assistant Service für ausgehende Updates."""
        with self.lock:
            self.ha_service = service

    def set_mqtt_service(self, service):
        """Setzt den MQTT Service für ausgehende Updates."""
        with self.lock:
            self.mqtt_service = service

    def trigger_ha_mqtt_update(self):
        """Erzwingt ein Update der HA-Daten via MQTT (basierend auf aktuellen Werten)."""
        with self.lock:
            if self.mqtt_service:
                ha_payload = {
                    "geofence_ok": self.current_mower_status.get('lat') is not None,
                    "satellites": self.current_mower_status.get('satellites', 0),
                    "hdop": self.current_mower_status.get('hdop', 0.0),
                    "status": self.current_mower_status.get('mower_status', 'unknown'),
                    "is_simulated": self.current_mower_status.get('is_simulated', False),
                    "latitude": self.current_mower_status.get('lat'),
                    "longitude": self.current_mower_status.get('lon')
                }
                self.mqtt_service.publish("worx/processed", json.dumps(ha_payload))

    def update_ha_mower_status(self, state):
        """Aktualisiert den Mäher-Status basierend auf HA-Daten mit Mapping auf lesbare Texte."""
        status_to_emit = None
        
        # Mapping von HA lawn_mower Klassen und Landroid-spezifischen Stati
        status_map = {
            'mowing': 'Mäher mäht',
            'starting': 'Mäher startet...',
            'edge cutting': 'Mäher mäht (Kantenschnitt)',
            'searching zone': 'Mäher sucht Zone',
            'returning': 'Mäher kehrt zurück',
            'at home': 'Mäher in der Box',
            'docked': 'Mäher angedockt (Geladen)',
            'charging': 'Mäher lädt',
            'idle': 'Mäher bereit',
            'rain delay': 'Mäher wartet (Regenpause)',
            'paused': 'Mäher pausiert',
            'off': 'Mäher ausgeschaltet',
            'error': 'FEHLER AM MÄHER',
            'trapped': 'Mäher festgefahren!',
            'manual stop': 'MANUELLER STOPP',
            'out of bounds': 'Außerhalb des Kabels!',
            'wires missing': 'Fehlendes Kabel-Signal'
        }
        
        # Normalisiere den Status für das Mapping
        state_clean = str(state).lower()
        display_status = status_map.get(state_clean, state) # Fallback auf Original-Text
        
        with self.lock:
            if self.current_mower_status['mower_status'] != display_status:
                self.current_mower_status['mower_status'] = display_status
                self.current_mower_status['last_update'] = datetime.now().strftime("%H:%M:%S")
                status_to_emit = self.current_mower_status.copy()
        
        if status_to_emit:
            logger.info(f"[StatusManager] HA-Status gemappt: {state} -> {display_status}")
            self._emit_socketio_event('status_update', status_to_emit, "Mäher-Status (HA)")
