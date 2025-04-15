# gps_handler.py
import logging
import datetime
import random
import time
import serial
import pynmea2
import requests
import platform
from datetime import datetime, timedelta
from config import GEO_CONFIG, ASSIST_NOW_CONFIG, REC_CONFIG
import math

# Stelle sicher, dass das Level auf DEBUG steht, um die neuen Logs zu sehen
#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class GpsHandler:
    def __init__(self):
        self.lat_bounds = GEO_CONFIG["lat_bounds"]
        self.lon_bounds = GEO_CONFIG["lon_bounds"]
        self.map_center = GEO_CONFIG["map_center"]
        self.assist_now_token = ASSIST_NOW_CONFIG["assist_now_token"]
        self.assist_now_offline_url = ASSIST_NOW_CONFIG["assist_now_offline_url"]
        self.assist_now_enabled = ASSIST_NOW_CONFIG["assist_now_enabled"]
        self.serial_port = REC_CONFIG["serial_port"]
        self.baudrate = REC_CONFIG["baudrate"]
        self.ser_gps = None
        self.mode = "real"
        self._connect_serial()

        self.last_assist_now_update = datetime.now() - timedelta(days=1)
        self.is_fake_gps = False
        self.route_simulator = None
        self.last_valid_fix_time = 0
        self.last_known_position = None
        # --- NEU: Letzte GGA Statusinformationen ---
        # Speichert den letzten bekannten Status, auch wenn kein Fix vorliegt
        # Initialisiere mit einem Status, der "Connecting" oder "No Fix" entspricht
        self.last_gga_info = {'qual': -1 if self.mode == "real" else 0, 'sats': 0, 'timestamp': time.time()}
        # --- ENDE NEU ---

    def _connect_serial(self):
        """Versucht, die serielle Verbindung herzustellen oder wiederherzustellen."""
        if self.ser_gps and self.ser_gps.is_open:
            try:
                self.ser_gps.close()
                logging.info("Bestehende serielle Verbindung geschlossen.")
            except Exception as e:
                logging.error(f"Fehler beim Schließen der bestehenden seriellen Verbindung: {e}")
            self.ser_gps = None

        if self.mode == "real":
            try:
                logging.info(f"Versuche, serielle Verbindung zu {self.serial_port} herzustellen...")
                self.ser_gps = serial.Serial(self.serial_port, self.baudrate, timeout=1)
                logging.info("Serielle Verbindung erfolgreich hergestellt.")
                # Setze Status auf "No Fix" nach erfolgreicher Verbindung, bis GGA kommt
                self.last_gga_info = {'qual': 0, 'sats': 0, 'timestamp': time.time()}
            except serial.SerialException as e:
                logging.error(f"Fehler beim Herstellen der seriellen Verbindung: {e}")
                self.ser_gps = None
                # --- Status bei Verbindungsfehler aktualisieren ---
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}  # -1 für Verbindungsfehler
            except Exception as e:
                logging.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung: {e}")
                self.ser_gps = None
                # --- Status bei Verbindungsfehler aktualisieren ---
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}  # -1 für Verbindungsfehler
        else:
            logging.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
            self.ser_gps = None
            # Setze Status für Fake-Modus (wird in get_gps_data überschrieben)
            self.last_gga_info = {'qual': 1, 'sats': 8, 'timestamp': time.time()}  # Simulierter Fix

    def _reconnect_serial(self):
        """Wrapper für _connect_serial für den Einsatz bei Fehlern."""
        logging.info("Versuche, serielle Verbindung wiederherzustellen...")
        self._connect_serial()

    class RouteSimulator:
        def __init__(self, start_lat, start_lon, speed=0.00001, direction=0):
            self.current_lat = start_lat
            self.current_lon = start_lon
            self.speed = speed
            self.direction = direction

        def move(self):
            self.current_lat += self.speed * math.cos(math.radians(self.direction))
            self.current_lon += self.speed * math.sin(math.radians(self.direction))
            return self.current_lat, self.current_lon

        def change_direction(self, angle_change):
            self.direction = (self.direction + angle_change) % 360

    def is_inside_boundaries(self, lat, lon):
        return (lat >= self.lat_bounds[0] and lat <= self.lat_bounds[1] and lon >= self.lon_bounds[0] and lon <=
                self.lon_bounds[1])

    def download_assist_now_data(self):
        try:
            headers = {"useragent": "Thingstream Client"}
            params = {
                "token": self.assist_now_token,
                "gnss": "gps",
                "alm": "gps",
                "days": 7,
                "resolution": 1
            }
            response = requests.get(self.assist_now_offline_url, headers=headers, params=params)
            response.raise_for_status()
            if not response.content:
                logging.warning("Keine AssistNow Offline-Daten erhalten.")
                return None
            logging.info("AssistNow Offline-Daten erfolgreich heruntergeladen.")
            return response.content
        except requests.exceptions.RequestException as e:
            logging.error(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
            return None

    def send_assist_now_data(self, data):
        if not self.ser_gps or not self.ser_gps.is_open:
            logging.warning("Kann AssistNow nicht senden: Serielle Verbindung nicht offen.")
            return

        try:
            self.ser_gps.write(data)
            logging.info("AssistNow Offline-Daten erfolgreich gesendet.")
        except serial.SerialException as e:
            logging.error(f"Serieller Fehler beim Senden der AssistNow Offline-Daten: {e}")
            self._reconnect_serial()
        except Exception as e:
            logging.error(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")

    def get_gps_data(self):
        """
        Liest und parst eine NMEA-Nachricht. Gibt Positionsdaten nur bei gültigem Fix zurück.
        Aktualisiert IMMER self.last_gga_info, wenn eine GGA-Nachricht empfangen wird.
        """
        # --- Fake-Modi ---
        if self.mode == "fake_random":
            fake_pos = self.generate_fake_data()
            # Simuliere Status für Fake-Modus
            self.last_gga_info = {
                'qual': 1,  # Simulierter Fix
                'sats': fake_pos.get('satellites', 0),
                'timestamp': fake_pos.get('timestamp', time.time())
            }
            return fake_pos  # Gib Position zurück
        elif self.mode == "fake_route":
            fake_pos = self.generate_fake_route_data()
            # Simuliere Status für Fake-Modus
            self.last_gga_info = {
                'qual': 1,  # Simulierter Fix
                'sats': fake_pos.get('satellites', 0),
                'timestamp': fake_pos.get('timestamp', time.time())
            }
            return fake_pos  # Gib Position zurück

        # --- Real-Modus ---
        elif self.mode == "real":
            if not self.ser_gps or not self.ser_gps.is_open:
                logging.warning("Serielle GPS-Verbindung nicht offen.")
                # Status wurde bereits in _connect_serial aktualisiert
                self._reconnect_serial()
                return None  # Keine gültige Position

            try:
                line_bytes = self.ser_gps.readline()
                if not line_bytes:
                    logging.debug("Keine Daten von serieller Schnittstelle gelesen (Timeout?).")
                    # Prüfen, ob letzter Status zu alt ist -> "No Signal"
                    if time.time() - self.last_gga_info.get('timestamp', 0) > 15:  # Timeout 15s
                        if self.last_gga_info.get('qual') != -1:  # Nur wenn nicht schon Verbindungsfehler
                            self.last_gga_info['qual'] = -2  # Eigener Code für "No Signal"
                            self.last_gga_info['sats'] = 0
                    return None  # Keine gültige Position
                line = line_bytes.decode('utf-8', errors='ignore').strip()

                if line.startswith('$'):
                    try:
                        msg = pynmea2.parse(line)
                        if isinstance(msg, pynmea2.types.talker.GGA):
                            current_time = time.time()
                            # --- GGA verarbeiten und self.last_gga_info IMMER aktualisieren ---
                            qual = 0
                            sats = 0
                            try:
                                qual = int(getattr(msg, 'gps_qual', 0))
                            except (ValueError, TypeError):
                                logging.warning(
                                    f"Konnte gps_qual '{getattr(msg, 'gps_qual', 'N/A')}' nicht in int konvertieren.")
                            try:
                                sats = int(getattr(msg, 'num_sats', 0))
                            except (ValueError, TypeError):
                                logging.warning(
                                    f"Konnte num_sats '{getattr(msg, 'num_sats', 'N/A')}' nicht in int konvertieren.")

                            self.last_gga_info['qual'] = qual
                            self.last_gga_info['sats'] = sats
                            self.last_gga_info['timestamp'] = current_time
                            # --- Ende GGA Verarbeitung ---

                            # Nur bei gültigem Fix Positionsdaten zurückgeben
                            if qual > 0:
                                self.last_valid_fix_time = current_time
                                self.last_known_position = {
                                    'lat': msg.latitude,
                                    'lon': msg.longitude,
                                    'timestamp': current_time,
                                    'satellites': sats,  # Verwende geparsten Wert
                                    'mode': self.mode
                                }
                                logging.debug(f"Gültige GGA-Daten empfangen: {self.last_known_position}")
                                return self.last_known_position
                            else:
                                logging.debug(f"GGA empfangen, aber kein gültiger Fix (Qual={qual}).")
                                return None  # Keine gültige Position
                        else:
                            logging.debug(f"Andere NMEA-Nachricht empfangen: {msg.sentence_type}")
                            return None  # Keine Positionsdaten
                    except pynmea2.ParseError as e:
                        logging.warning(f"Fehler beim Parsen der NMEA-Zeile: {e} - Zeile: '{line}'")
                        return None
                    except AttributeError as e:
                        logging.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Nachricht: {msg}")
                        return None
                else:
                    logging.debug(f"Ignoriere Zeile ohne '$': '{line[:50]}...'")
                    return None
            except serial.SerialException as e:
                logging.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                # --- Status bei Verbindungsfehler aktualisieren ---
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}  # -1 für Verbindungsfehler
                self._reconnect_serial()
                return None  # Keine gültige Position
            except UnicodeDecodeError as e:
                logging.warning(f"Fehler beim Dekodieren der seriellen Daten: {e}")
                return None
            except Exception as e:
                logging.error(f"Unerwarteter Fehler in get_gps_data: {e}", exc_info=True)
                return None
        # Fallback
        return None

    # --- NEUE METHODE: get_last_gga_status ---
    def get_last_gga_status(self):
        """Gibt den letzten bekannten GPS-Status als String zurück."""
        qual = self.last_gga_info.get('qual', 0)
        sats = self.last_gga_info.get('sats', 0)
        ts = self.last_gga_info.get('timestamp', 0)

        # Mapping für gps_qual
        qual_map = {
            -2: "No Signal",  # Eigener Code für Timeout
            -1: "Connecting",  # Eigener Code für Verbindungsfehler
            0: "No Fix",
            1: "GPS Fix (SPS)",
            2: "DGPS Fix",
            3: "PPS Fix",  # Selten
            4: "RTK Fixed",
            5: "RTK Float",
            6: "Estimated (DR)",
            7: "Manual Input",
            8: "Simulation"
        }
        fix_description = qual_map.get(qual, f"Unknown ({qual})")

        # Format: "status,<Beschreibung>,<Satelliten>"
        status_message = f"status,{fix_description},{sats}"
        logging.debug(f"Generierter GPS Status String: {status_message} (Qual={qual}, Sats={sats}, TS={ts})")
        return status_message

    # --- ENDE NEUE METHODE ---

    def generate_fake_data(self):
        lat_range, lon_range = GEO_CONFIG["fake_gps_range"]
        fake_pos = {
            'lat': random.uniform(*lat_range),
            'lon': random.uniform(*lon_range),
            'timestamp': time.time(),
            'satellites': random.randint(4, 12),
            'mode': self.mode
        }
        logging.debug(f"Generiere Fake-Daten (random): {fake_pos}")
        self.last_known_position = fake_pos
        return fake_pos

    def generate_fake_route_data(self):
        if self.route_simulator:
            if random.random() < 0.1:
                self.route_simulator.change_direction(random.randint(-30, 30))

            lat, lon = self.route_simulator.move()
            fake_pos = {
                'lat': lat,
                'lon': lon,
                'timestamp': time.time(),
                'satellites': random.randint(7, 12),
                'mode': self.mode
            }
            logging.debug(f"Generiere Fake-Daten (route): {fake_pos}")
            self.last_known_position = fake_pos
            return fake_pos
        else:
            logging.warning("Routenmodus aktiv, aber kein Routensimulator initialisiert.")
            return self.generate_fake_data()

    def check_assist_now(self):
        if self.assist_now_enabled and datetime.now() - self.last_assist_now_update >= timedelta(days=1):
            logging.info("Prüfe auf AssistNow Offline Update...")
            data = self.download_assist_now_data()
            if data is not None:
                self.send_assist_now_data(data)
                self.last_assist_now_update = datetime.now()
                logging.info("AssistNow Offline Update erfolgreich durchgeführt.")
            else:
                logging.error(
                    "AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in 2 Sekunden.")
                time.sleep(2)
                return False
        return True

    def change_gps_mode(self, new_mode):
        if new_mode == self.mode:
            logging.info(f"GPS-Modus ist bereits '{new_mode}'. Keine Änderung.")
            return True

        logging.info(f" GPS-Modus von '{self.mode}' zu: {new_mode}")  # Korrigiertes Log
        if new_mode == "fake_route":
            self.mode = "fake_route"
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            if not self.route_simulator:
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logging.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "fake_random":
            self.mode = "fake_random"
            self.is_fake_gps = True
            self.route_simulator = None
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logging.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "real":
            self.mode = "real"
            self.is_fake_gps = False
            self.route_simulator = None
            self._connect_serial()  # Stelle Verbindung wieder her
        else:
            logging.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            return False
        return True
