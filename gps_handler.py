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

# Hole den Logger, anstatt basicConfig hier aufzurufen
logger = logging.getLogger(__name__)


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
        # Letzte GGA Statusinformationen
        self.last_gga_info = {'qual': -1 if self.mode == "real" else 0, 'sats': 0, 'timestamp': time.time()}
        logger.info("GpsHandler initialisiert.") # Log Hinzugefügt

    def _connect_serial(self):
        """Versucht, die serielle Verbindung herzustellen oder wiederherzustellen."""
        if self.ser_gps and self.ser_gps.is_open:
            try:
                self.ser_gps.close()
                logger.info("Bestehende serielle Verbindung geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen der bestehenden seriellen Verbindung: {e}")
            self.ser_gps = None

        if self.mode == "real":
            try:
                logger.info(f"Versuche, serielle Verbindung zu {self.serial_port} herzustellen...")
                self.ser_gps = serial.Serial(self.serial_port, self.baudrate, timeout=1)
                logger.info("Serielle Verbindung erfolgreich hergestellt.")
                self.last_gga_info = {'qual': 0, 'sats': 0, 'timestamp': time.time()}
            except serial.SerialException as e:
                logger.error(f"Fehler beim Herstellen der seriellen Verbindung: {e}")
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung: {e}")
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
        else:
            logger.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
            self.ser_gps = None
            self.last_gga_info = {'qual': 1, 'sats': 8, 'timestamp': time.time()}

    def _reconnect_serial(self):
        """Wrapper für _connect_serial für den Einsatz bei Fehlern."""
        logger.info("Versuche, serielle Verbindung wiederherzustellen...")
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
        return (self.lat_bounds[0] <= lat <= self.lat_bounds[1] and
                self.lon_bounds[0] <= lon <= self.lon_bounds[1])

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
                logger.warning("Keine AssistNow Offline-Daten erhalten.")
                return None
            logger.info("AssistNow Offline-Daten erfolgreich heruntergeladen.")
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
            return None

    def send_assist_now_data(self, data):
        if not self.ser_gps or not self.ser_gps.is_open:
            logger.warning("Kann AssistNow nicht senden: Serielle Verbindung nicht offen.")
            return

        try:
            self.ser_gps.write(data)
            logger.info("AssistNow Offline-Daten erfolgreich gesendet.")
        except serial.SerialException as e:
            logger.error(f"Serieller Fehler beim Senden der AssistNow Offline-Daten: {e}")
            self._reconnect_serial()
        except Exception as e:
            logger.error(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")

    def get_gps_data(self):
        """
        Liest und parst NMEA-Nachrichten. Versucht, innerhalb eines Timeouts einen GGA-Satz zu finden.
        Gibt Positionsdaten nur bei gültigem Fix zurück.
        Aktualisiert IMMER self.last_gga_info und self.last_known_position (bei gültigem Fix).
        """
        # --- Fake-Modi ---
        if self.mode == "fake_random":
            fake_pos = self.generate_fake_data()
            # Aktualisiere Statusinformationen auch im Fake-Modus
            self.last_gga_info = {'qual': 1, 'sats': fake_pos.get('satellites', 8),
                                  'timestamp': fake_pos.get('timestamp', time.time())}
            self.last_known_position = fake_pos  # Wichtig: Auch im Fake-Modus setzen
            logger.debug(f"Fake Random Data: {fake_pos}")
            return fake_pos
        elif self.mode == "fake_route":
            fake_pos = self.generate_fake_route_data()
            # Aktualisiere Statusinformationen auch im Fake-Modus
            self.last_gga_info = {'qual': 1, 'sats': fake_pos.get('satellites', 8),
                                  'timestamp': fake_pos.get('timestamp', time.time())}
            self.last_known_position = fake_pos  # Wichtig: Auch im Fake-Modus setzen
            logger.debug(f"Fake Route Data: {fake_pos}")
            return fake_pos

        # --- Real-Modus ---
        elif self.mode == "real":
            if not self.ser_gps or not self.ser_gps.is_open:
                logger.warning("Serielle GPS-Verbindung nicht offen.")
                self._reconnect_serial()
                # Setze Status auf "Connecting" wenn Verbindung versucht wird
                if self.last_gga_info.get('qual') != -1:
                    self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
                return None

            # --- Versuch, mehrere Zeilen zu lesen ---
            start_time = time.monotonic()
            # Timeout etwas kürzer als der Serial-Timeout, um Blockaden zu vermeiden
            # und der Hauptschleife Zeit zu geben.
            read_timeout = 0.9  # Sekunden
            gga_msg = None  # Variable für die zuletzt gefundene GGA-Nachricht

            while time.monotonic() - start_time < read_timeout:
                try:
                    # Lese eine Zeile von der seriellen Schnittstelle
                    line_bytes = self.ser_gps.readline()

                    # Wenn nichts gelesen wurde (Timeout der readline-Funktion)
                    if not line_bytes:
                        logger.debug("Keine Daten von serieller Schnittstelle gelesen (readline Timeout).")
                        # Kurze Pause, um CPU zu schonen, wenn ständig nichts kommt
                        time.sleep(0.05)
                        continue  # Nächste Lese-Iteration

                    # Dekodiere die Zeile
                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    logger.debug(f"Serielle Zeile empfangen: '{line[:80]}...'")  # Logge empfangene Zeile (gekürzt)

                    # Verarbeite nur NMEA-Sätze (beginnen mit '$')
                    if line.startswith('$'):
                        try:
                            # Parse die NMEA-Nachricht
                            msg = pynmea2.parse(line)

                            # Prüfen, ob es ein GGA-Satz ist
                            if isinstance(msg, pynmea2.types.talker.GGA):
                                gga_msg = msg  # Merke den letzten gefundenen GGA-Satz
                                logger.debug(
                                    f"GGA gefunden: Qual={getattr(msg, 'gps_qual', 'N/A')}, Sats={getattr(msg, 'num_sats', 'N/A')}")
                                # Optional: break, wenn man den *ersten* GGA will
                                # break
                                # Aktuell: Lese weiter bis Timeout, um den *letzten* GGA zu bekommen
                            else:
                                logger.debug(f"Andere NMEA-Nachricht empfangen: {msg.sentence_type}")

                        except pynmea2.ParseError as e:
                            logger.warning(f"Fehler beim Parsen der NMEA-Zeile: {e} - Zeile: '{line}'")
                        except AttributeError as e:
                            # Fängt Fehler ab, wenn pynmea2 ein unerwartetes Format parst
                            logger.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Zeile: '{line}'")
                        # --- Ende inneres Try/Except für Pynmea2 ---
                    else:
                        # Ignoriere Zeilen, die keine NMEA-Sätze sind
                        if line:  # Nur loggen, wenn die Zeile nicht leer ist
                            logger.debug(f"Ignoriere Zeile ohne '$': '{line[:50]}...'")

                except serial.SerialException as e:
                    logger.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                    self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}  # Status: Verbindungsfehler
                    self._reconnect_serial()
                    return None  # Bei seriellem Fehler abbrechen
                except UnicodeDecodeError as e:
                    logger.warning(f"Fehler beim Dekodieren der seriellen Daten: {e}")
                    # Hier nicht unbedingt abbrechen, vielleicht ist die nächste Zeile ok
                except Exception as e:
                    logger.error(f"Unerwarteter Fehler in get_gps_data Leseschleife: {e}", exc_info=True)
                    # Bei unerwartetem Fehler ist es sicherer, None zurückzugeben
                    return None
            # --- Ende while-Schleife (Lese-Timeout erreicht) ---

            # --- Verarbeitung des zuletzt gefundenen GGA-Satzes (falls vorhanden) ---
            if gga_msg:
                current_time = time.time()
                qual = 0
                sats = 0
                # Extrahiere Qualität und Satellitenanzahl sicher
                try:
                    qual = int(getattr(gga_msg, 'gps_qual', 0))
                except (ValueError, TypeError):
                    logger.warning(f"Konnte gps_qual '{getattr(gga_msg, 'gps_qual', 'N/A')}' nicht in int konvertieren.")
                try:
                    sats = int(getattr(gga_msg, 'num_sats', 0))
                except (ValueError, TypeError):
                    logger.warning(f"Konnte num_sats '{getattr(gga_msg, 'num_sats', 'N/A')}' nicht in int konvertieren.")

                # Aktualisiere IMMER die letzten GGA-Statusinformationen
                self.last_gga_info['qual'] = qual
                self.last_gga_info['sats'] = sats
                self.last_gga_info['timestamp'] = current_time

                # Prüfe, ob der Fix gültig ist (Qualität > 0)
                if qual > 0:
                    self.last_valid_fix_time = current_time
                    # Aktualisiere die letzte bekannte Position
                    try:
                        # Stelle sicher, dass Lat/Lon gültige Floats sind
                        lat = float(gga_msg.latitude)
                        lon = float(gga_msg.longitude)
                        self.last_known_position = {
                            'lat': lat,
                            'lon': lon,
                            'timestamp': current_time,
                            'satellites': sats,
                            'mode': self.mode
                        }
                        logger.debug(f"Gültige GGA-Daten verarbeitet: Qual={qual}, Sats={sats}, Pos=({lat:.6f}, {lon:.6f})")
                        return self.last_known_position  # Gib die gültige Position zurück
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Fehler beim Extrahieren von Lat/Lon aus GGA: {e} - GGA: {gga_msg}")
                        # Obwohl Qual > 0, sind die Daten unbrauchbar
                        return None
                else:
                    # Gültiger GGA, aber kein Fix. Gib keine Position zurück.
                    logger.debug(f"Letzter gelesener GGA hatte keinen gültigen Fix (Qual={qual}).")
                    # last_known_position NICHT ändern, behalte die letzte gültige.
                    return None
            else:
                # Kein GGA-Satz im Lesezeitfenster gefunden
                logger.debug("Kein GGA-Satz im Lesezeitfenster gefunden.")
                # Prüfen, ob seit dem letzten *irgendeinem* GGA-Empfang (auch ohne Fix)
                # oder seit dem letzten Versuch, die Verbindung herzustellen, zu viel Zeit vergangen ist.
                # Wenn ja, markiere den Status als "No Signal".
                time_since_last_info = time.time() - self.last_gga_info.get('timestamp', 0)
                if time_since_last_info > 15:  # z.B. 15 Sekunden ohne jegliche GGA-Info
                    # Nur ändern, wenn der Status nicht schon "Connecting" oder "No Signal" ist
                    if self.last_gga_info.get('qual') not in [-1, -2]:
                        logger.warning(
                            f"Seit {time_since_last_info:.1f}s keine GGA-Info mehr. Setze Status auf 'No Signal'.")
                        self.last_gga_info['qual'] = -2  # Markiere als "No Signal"
                        self.last_gga_info['sats'] = 0
                        # Timestamp hier NICHT aktualisieren, damit der Timeout weiterhin greift
                return None
            # --- Ende Verarbeitung ---

        # Fallback (sollte eigentlich nicht erreicht werden)
        logger.error("Unerwarteter Fall am Ende von get_gps_data erreicht.")
        return None

    def get_last_gga_status(self):
        """Gibt den letzten bekannten GPS-Status inkl. Position als String zurück."""
        qual = self.last_gga_info.get('qual', 0)
        sats = self.last_gga_info.get('sats', 0)
        ts = self.last_gga_info.get('timestamp', 0)

        qual_map = {
            -2: "No Signal", -1: "Connecting", 0: "No Fix", 1: "GPS Fix (SPS)",
            2: "DGPS Fix", 3: "PPS Fix", 4: "RTK Fixed", 5: "RTK Float",
            6: "Estimated (DR)", 7: "Manual Input", 8: "Simulation"
        }
        fix_description = qual_map.get(qual, f"Unknown ({qual})")

        # --- Position hinzufügen ---
        lat_str = ""
        lon_str = ""
        # Greife auf die zuletzt gespeicherte Position zu
        if self.last_known_position and 'lat' in self.last_known_position and 'lon' in self.last_known_position:
             # Prüfe, ob die letzte Position aktuell genug ist (z.B. nicht älter als 15s)
             # oder ob der aktuelle Fix-Status > 0 ist.
             # Dies verhindert, dass eine alte Position bei "No Fix" angezeigt wird.
             if qual > 0 or (time.time() - self.last_known_position.get('timestamp', 0) < 15):
                try:
                    # Formatieren mit fester Anzahl Nachkommastellen für Konsistenz
                    lat_str = f"{self.last_known_position['lat']:.8f}"
                    lon_str = f"{self.last_known_position['lon']:.8f}"
                except (TypeError, ValueError):
                    logger.warning("Konnte letzte Position nicht formatieren.")
                    lat_str = ""
                    lon_str = ""

        # Format: "status,<Beschreibung>,<Satelliten>,<Latitude>,<Longitude>"
        # Latitude und Longitude sind leer, wenn keine (aktuelle) Position bekannt ist.
        status_message = f"status,{fix_description},{sats},{lat_str},{lon_str}"
        # --- Ende Positions-Hinzufügung ---

        logger.debug(f"Generierter GPS Status String: {status_message} (Qual={qual}, Sats={sats}, TS={ts})")
        return status_message

    def generate_fake_data(self):
        lat_range, lon_range = GEO_CONFIG["fake_gps_range"]
        fake_pos = {
            'lat': random.uniform(*lat_range),
            'lon': random.uniform(*lon_range),
            'timestamp': time.time(),
            'satellites': random.randint(4, 12),
            'mode': self.mode
        }
        logger.debug(f"Generiere Fake-Daten (random): {fake_pos}")
        # self.last_known_position wird in get_gps_data gesetzt
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
            logger.debug(f"Generiere Fake-Daten (route): {fake_pos}")
            # self.last_known_position wird in get_gps_data gesetzt
            return fake_pos
        else:
            logger.warning("Routenmodus aktiv, aber kein Routensimulator initialisiert.")
            return self.generate_fake_data() # Fallback

    def check_assist_now(self):
        if self.assist_now_enabled and datetime.now() - self.last_assist_now_update >= timedelta(days=1):
            logger.info("Prüfe auf AssistNow Offline Update...")
            data = self.download_assist_now_data()
            if data is not None:
                self.send_assist_now_data(data)
                self.last_assist_now_update = datetime.now()
                logger.info("AssistNow Offline Update erfolgreich durchgeführt.")
            else:
                logger.error("AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in 2 Sekunden.")
                time.sleep(2)
                return False
        return True

    def change_gps_mode(self, new_mode):
        if new_mode == self.mode:
            logger.info(f"GPS-Modus ist bereits '{new_mode}'. Keine Änderung.")
            return True

        logger.info(f"Ändere GPS-Modus von '{self.mode}' zu: {new_mode}")
        if new_mode == "fake_route":
            self.mode = "fake_route"
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            if not self.route_simulator:
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logger.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "fake_random":
            self.mode = "fake_random"
            self.is_fake_gps = True
            self.route_simulator = None
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logger.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "real":
            self.mode = "real"
            self.is_fake_gps = False
            self.route_simulator = None
            self._connect_serial()
        else:
            logger.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            return False

        # Reset last_known_position beim Moduswechsel? Optional.
        # self.last_known_position = None
        return True
