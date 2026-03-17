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

# --- pyubx2 Import entfernt ---

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
        # --- Aufruf von _configure_ublox entfernt ---
        self._connect_serial()

        # Zeitstempel des letzten erfolgreichen AssistNow-Updates
        self.last_assist_now_update = datetime.now() - timedelta(days=ASSIST_NOW_CONFIG.get("days", 7) + 1)
        # NEU: Backoff für fehlgeschlagene AssistNow-Downloads
        self._assist_now_fail_count = 0
        self._assist_now_last_attempt = None
        self._assist_now_backoff_base = 300  # 5 Minuten Basis-Backoff
        self._assist_now_max_backoff = 21600  # Max 6 Stunden

        self.is_fake_gps = False
        self.route_simulator = None
        self.last_valid_fix_time = 0
        self.last_known_position = None
        # --- Initialer Status auf -1 (Connecting) gesetzt, wird durch erste GGA-Nachricht aktualisiert ---
        self.last_gga_info = {'qual': -1 if self.mode == "real" else 0, 'sats': 0, 'timestamp': time.time()}
        logger.info("GpsHandler initialisiert.")

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
                logger.info(
                    f"Versuche, serielle Verbindung zu {self.serial_port} mit Baudrate {self.baudrate} herzustellen...")
                # --- write_timeout bleibt sinnvoll für AssistNow ---
                self.ser_gps = serial.Serial(
                    self.serial_port,
                    self.baudrate,
                    timeout=1,  # Read timeout
                    write_timeout=60  # Write timeout
                )
                logger.info(f"Serielle Verbindung zu {self.ser_gps.name} erfolgreich hergestellt.")

                # --- Status auf -1 (Connecting) setzen, bis der erste GGA kommt ---
                # Wird jetzt in __init__ gesetzt und hier ggf. zurückgesetzt
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}

                # --- Block für U-BLOX Konfiguration entfernt ---

            except serial.SerialException as ser_e:
                logger.error(f"Serieller Fehler beim Herstellen der Verbindung zu {self.serial_port}: {ser_e}",
                             exc_info=True)
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung zu {self.serial_port}: {e}",
                             exc_info=True)
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
        else:
            logger.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
            self.ser_gps = None
            self.last_gga_info = {'qual': 1, 'sats': 8, 'timestamp': time.time()}  # Fake GPS hat sofort Fix

    def _reconnect_serial(self):
        """Wrapper für _connect_serial für den Einsatz bei Fehlern."""
        logger.info("Versuche, serielle Verbindung wiederherzustellen...")
        # _connect_serial ruft KEINE Konfiguration mehr auf
        self._connect_serial()

    def close_serial(self):
        """Schließt die serielle Verbindung sicher."""
        if self.ser_gps and self.ser_gps.is_open:
            try:
                self.ser_gps.close()
                logger.info("Serielle GPS-Verbindung geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen der seriellen Verbindung: {e}")
        self.ser_gps = None

    # --- Methode _send_ubx_config entfernt ---

    # --- Methode _configure_ublox entfernt ---

    # --- RouteSimulator Klasse bleibt ---
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

    # --- is_inside_boundaries bleibt ---
    def is_inside_boundaries(self, lat, lon):
        return (self.lat_bounds[0] <= lat <= self.lat_bounds[1] and
                self.lon_bounds[0] <= lon <= self.lon_bounds[1])

    # --- download_assist_now_data bleibt ---
    def download_assist_now_data(self):
        """Lädt AssistNow Offline Daten herunter (für u-blox 7 optimiert)."""
        if not self.assist_now_token:
            logger.error("AssistNow Token fehlt in der Konfiguration.")
            return None
        try:
            headers = {"useragent": "Thingstream Client"}
            requested_days = ASSIST_NOW_CONFIG.get("days", 7)
            valid_u7_days = [1, 2, 3, 5, 7, 10, 14]
            if requested_days not in valid_u7_days:
                logger.warning(
                    f"Ungültiger Wert für 'days' ({requested_days}) in ASSIST_NOW_CONFIG für u-blox 7. Verwende Standardwert 7.")
                effective_days = 7
            else:
                effective_days = requested_days

            params = {
                "token": self.assist_now_token,
                "gnss": "gps",
                "format": "aid",
                "days": effective_days
            }
            logger.info(
                f"Lade AssistNow Offline Daten von {self.assist_now_offline_url} mit Token {self.assist_now_token[:5]}... (Params: {params})")
            response = requests.get(self.assist_now_offline_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()

            if not response.content:
                logger.warning("Keine AssistNow Offline-Daten erhalten (leere Antwort).")
                return None
            try:
                response_text = response.content.decode('utf-8', errors='ignore')
                if "error" in response_text.lower() or "invalid token" in response_text.lower() or "bad request" in response_text.lower():
                    logger.error(f"Fehler von AssistNow Service erhalten: {response_text}")
                    return None
            except UnicodeDecodeError:
                pass
            logger.info(f"AssistNow Offline-Daten erfolgreich heruntergeladen ({len(response.content)} Bytes).")
            return response.content
        except requests.exceptions.Timeout:
            logger.error("Timeout beim Herunterladen der AssistNow Offline-Daten.")
            return None
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if e.response is not None else "N/A"
            req_url = e.request.url if e.request is not None else "N/A"
            logger.error(
                f"Fehler beim Herunterladen der AssistNow Offline-Daten (Status: {status_code}) für URL {req_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim AssistNow Download: {e}", exc_info=True)
            return None

    # --- send_assist_now_data bleibt ---
    def send_assist_now_data(self, data):
        """Sendet die heruntergeladenen AssistNow Daten an das GPS-Modul."""
        logger.debug("send_assist_now_data aufgerufen.")
        if self.ser_gps is None:
            logger.warning("send_assist_now_data: self.ser_gps ist None. Breche ab.")
            return False
        if not self.ser_gps.is_open:
            logger.warning(f"send_assist_now_data: Serielle Verbindung {self.ser_gps.name} ist nicht offen. Breche ab.")
            return False

        logger.debug(f"Versuche, {len(data)} Bytes auf {self.ser_gps.name} zu schreiben...")
        try:
            start_write = time.monotonic()
            bytes_written = self.ser_gps.write(data)
            duration_write = time.monotonic() - start_write
            logger.debug(
                f"self.ser_gps.write abgeschlossen nach {duration_write:.2f}s. Bytes geschrieben: {bytes_written}")

            logger.debug("Führe self.ser_gps.flush() aus...")
            start_flush = time.monotonic()
            self.ser_gps.flush()
            duration_flush = time.monotonic() - start_flush
            logger.debug(f"self.ser_gps.flush() abgeschlossen nach {duration_flush:.2f}s.")

            logger.info(f"AssistNow Offline-Daten ({bytes_written} Bytes) erfolgreich gesendet.")
            return True
        except serial.SerialTimeoutException:
            duration_timeout = time.monotonic() - start_write
            write_timeout_val = getattr(self.ser_gps, 'write_timeout', 'N/A')
            logger.error(
                f"Timeout ({write_timeout_val}s) beim Senden der AssistNow Offline-Daten nach {duration_timeout:.2f}s.")
            self._reconnect_serial()  # Reconnect bleibt sinnvoll
            return False
        except serial.SerialException as e:
            logger.error(f"Serieller Fehler beim Senden der AssistNow Offline-Daten: {e}", exc_info=True)
            self._reconnect_serial()  # Reconnect bleibt sinnvoll
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Senden der AssistNow Offline-Daten: {e}", exc_info=True)
            return False

    # --- get_gps_data bleibt im Wesentlichen gleich ---
    def get_gps_data(self):
        """
        Liest und parst NMEA-Nachrichten. Versucht, innerhalb eines Timeouts einen GGA-Satz zu finden.
        Gibt Positionsdaten nur bei gültigem Fix zurück.
        Aktualisiert IMMER self.last_gga_info und self.last_known_position (bei gültigem Fix).
        """
        # --- Fake-Modi ---
        if self.mode == "fake_random":
            fake_pos = self.generate_fake_data()
            self.last_gga_info = {'qual': 1, 'sats': fake_pos.get('satellites', 8),
                                  'timestamp': fake_pos.get('timestamp', time.time())}
            self.last_known_position = fake_pos
            logger.debug(f"Fake Random Data: {fake_pos}")
            return fake_pos
        elif self.mode == "fake_route":
            fake_pos = self.generate_fake_route_data()
            self.last_gga_info = {'qual': 1, 'sats': fake_pos.get('satellites', 8),
                                  'timestamp': fake_pos.get('timestamp', time.time())}
            self.last_known_position = fake_pos
            logger.debug(f"Fake Route Data: {fake_pos}")
            return fake_pos

        # --- Real-Modus ---
        elif self.mode == "real":
            connection_ok = True
            if self.ser_gps is None:
                logger.warning("GPS-Verbindung ist None in get_gps_data.")
                connection_ok = False
            elif not self.ser_gps.is_open:
                logger.warning(f"GPS-Verbindung {self.ser_gps.name} ist nicht offen in get_gps_data.")
                connection_ok = False

            if not connection_ok:
                logger.info("-> get_gps_data löst _reconnect_serial aus.")
                self._reconnect_serial()
                # Setze Status auf Connecting, falls nicht schon
                if self.last_gga_info.get('qual') != -1:
                    self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
                return None

            try:
                # logger.debug("Leere seriellen Eingangspuffer...") # Kann evtl. Probleme machen, erstmal raus
                # self.ser_gps.reset_input_buffer()
                pass  # Platzhalter
            except Exception as e:
                logger.error(f"Fehler beim Leeren des Eingangspuffers: {e}")

            start_time = time.monotonic()
            read_timeout = 0.9
            gga_msg = None

            while time.monotonic() - start_time < read_timeout:
                try:
                    line_bytes = self.ser_gps.readline()
                    if not line_bytes:
                        # logger.debug("Keine Daten von serieller Schnittstelle gelesen (readline Timeout).") # Zu viel Logspam
                        time.sleep(0.05)
                        continue

                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    # logger.debug(f"Serielle Zeile empfangen: '{line[:80]}...'") # Zu viel Logspam

                    if line.startswith('$'):
                        try:
                            # Basis-Prüfung: Hat die Zeile überhaupt nützliche Felder?
                            # Zeilen wie '$GPGL,,,,,*4' oder '$GPRMC,,V,,,,,,,,*3' überspringen
                            parts = line.split(',')
                            if len(parts) > 2:
                                talker = parts[0].upper()
                                status_field = ""
                                if "RMC" in talker or "GLL" in talker:
                                    status_field = parts[2] # RMC/GLL haben Status an Pos 2
                                elif "GGA" in talker:
                                    status_field = parts[6] if len(parts) > 6 else "" # GGA hat Qual an Pos 6
                                
                                # Wenn 'V' (Void) oder '0' (No Fix) und keine Koordinaten da sind
                                if status_field in ['V', '0']:
                                    # Zähle gefüllte Felder abseits von Talker und Status
                                    filled_data = [p for i, p in enumerate(parts) if i not in [0, 2, 6] and p.split('*')[0].strip()]
                                    if not filled_data:
                                        # logger.debug(f"Überspringe Status-nur NMEA-Zeile: '{line}'")
                                        continue
                            
                            msg = pynmea2.parse(line)
                            if isinstance(msg, pynmea2.types.talker.GGA):
                                gga_msg = msg
                                logger.debug(
                                    f"GGA gefunden: Qual={getattr(msg, 'gps_qual', 'N/A')}, Sats={getattr(msg, 'num_sats', 'N/A')}")
                                # break # Optional: Nur ersten GGA nehmen
                        except pynmea2.ParseError:
                            # Silently ignore parse errors for sentences that look like standard "no data" patterns
                            if ",V," in line or ",0," in line or line.count(',,') > 3:
                                # logger.debug(f"Ignoriere erwarteten Parse-Fehler für Such-Phase: '{line}'")
                                pass
                            else:
                                logger.warning(f"Fehler beim Parsen der NMEA-Zeile: '{line}'")
                        except AttributeError as e:
                            logger.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Zeile: '{line}'")
                    # else: # Zu viel Logspam
                    # if line:
                    # logger.debug(f"Ignoriere Zeile ohne '$': '{line[:50]}...'")

                except serial.SerialException as e:
                    logger.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                    self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
                    self._reconnect_serial()
                    return None
                except UnicodeDecodeError as e:
                    logger.warning(f"Fehler beim Dekodieren der seriellen Daten: {e}")
                except Exception as e:
                    logger.error(f"Unerwarteter Fehler in get_gps_data Leseschleife: {e}", exc_info=True)
                    return None

            if gga_msg:
                current_time = time.time()
                qual = 0
                sats = 0
                try:
                    qual_str = getattr(gga_msg, 'gps_qual', '0')
                    qual = int(qual_str) if qual_str else 0
                except (ValueError, TypeError):
                    qual = 0
                try:
                    sats_str = getattr(gga_msg, 'num_sats', '0')
                    sats = int(sats_str) if sats_str else 0
                except (ValueError, TypeError):
                    sats = 0

                self.last_gga_info['qual'] = qual
                self.last_gga_info['sats'] = sats
                self.last_gga_info['timestamp'] = current_time

                if qual > 0:
                    self.last_valid_fix_time = current_time
                    try:
                        if hasattr(gga_msg, 'latitude') and hasattr(gga_msg, 'longitude') and \
                                gga_msg.latitude is not None and gga_msg.longitude is not None:
                            lat = float(gga_msg.latitude)
                            lon = float(gga_msg.longitude)
                            self.last_known_position = {
                                'lat': lat, 'lon': lon, 'timestamp': current_time,
                                'satellites': sats, 'mode': self.mode
                            }
                            logger.debug(
                                f"Gültige GGA-Daten verarbeitet: Qual={qual}, Sats={sats}, Pos=({lat:.6f}, {lon:.6f})")
                            return self.last_known_position
                        else:
                            logger.warning(f"GGA mit Qual={qual} hat keine gültigen Lat/Lon-Attribute: {gga_msg}")
                            return None
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Fehler beim Extrahieren von Lat/Lon aus GGA: {e} - GGA: {gga_msg}")
                        return None
                else:
                    logger.debug(f"Letzter gelesener GGA hatte keinen gültigen Fix (Qual={qual}).")
                    return None
            else:
                # logger.debug("Kein GGA-Satz im Lesezeitfenster gefunden.") # Zu viel Logspam
                time_since_last_info = time.time() - self.last_gga_info.get('timestamp', 0)
                # --- Logik für "No Signal" bleibt ---
                if time_since_last_info > 15:
                    if self.last_gga_info.get('qual') not in [-1, -2]:
                        logger.warning(
                            f"Seit {time_since_last_info:.1f}s keine GGA-Info mehr. Setze Status auf 'No Signal'.")
                        self.last_gga_info['qual'] = -2
                        self.last_gga_info['sats'] = 0
                return None

        logger.error("Unerwarteter Fall am Ende von get_gps_data erreicht.")
        return None

    # --- get_last_gga_status bleibt ---
    def get_last_gga_status(self):
        qual = self.last_gga_info.get('qual', -1)  # Standard -1 (Connecting)
        sats = self.last_gga_info.get('sats', 0)
        ts = self.last_gga_info.get('timestamp', 0)

        qual_map = {
            -2: "No Signal", -1: "Connecting", 0: "No Fix", 1: "GPS Fix (SPS)",
            2: "DGPS Fix", 3: "PPS Fix", 4: "RTK Fixed", 5: "RTK Float",
            6: "Estimated (DR)", 7: "Manual Input", 8: "Simulation"
        }
        fix_description = qual_map.get(qual, f"Unknown ({qual})")

        lat_str, lon_str = "", ""
        if self.last_known_position and 'lat' in self.last_known_position and 'lon' in self.last_known_position:
            if qual > 0 or (time.time() - self.last_known_position.get('timestamp', 0) < 15):
                try:
                    lat_str = f"{self.last_known_position['lat']:.8f}"
                    lon_str = f"{self.last_known_position['lon']:.8f}"
                except (TypeError, ValueError):
                    pass  # Fehler schon geloggt

        agps_status_str = ""
        if self.assist_now_enabled:
            time_since_agps_update = datetime.now() - self.last_assist_now_update
            if time_since_agps_update < timedelta(days=ASSIST_NOW_CONFIG.get("days", 7) + 1):
                hours_ago = time_since_agps_update.total_seconds() / 3600
                agps_status_str = f",AGPS: OK ({hours_ago:.1f}h ago)"
            else:
                agps_status_str = ",AGPS: Stale"
        else:
            agps_status_str = ",AGPS: Off"

        status_message = f"status,{fix_description},{sats},{lat_str},{lon_str}{agps_status_str}"
        # logger.debug(f"Generierter GPS Status String: {status_message} (Qual={qual}, Sats={sats}, TS={ts})") # Zu viel Logspam
        return status_message

    # --- generate_fake_data bleibt ---
    def generate_fake_data(self):
        lat_range, lon_range = GEO_CONFIG["fake_gps_range"]
        fake_pos = {
            'lat': random.uniform(*lat_range), 'lon': random.uniform(*lon_range),
            'timestamp': time.time(), 'satellites': random.randint(4, 12), 'mode': self.mode
        }
        logger.debug(f"Generiere Fake-Daten (random): {fake_pos}")
        return fake_pos

    # --- generate_fake_route_data bleibt ---
    def generate_fake_route_data(self):
        if self.route_simulator:
            if random.random() < 0.1:
                self.route_simulator.change_direction(random.randint(-30, 30))
            lat, lon = self.route_simulator.move()
            fake_pos = {
                'lat': lat, 'lon': lon, 'timestamp': time.time(),
                'satellites': random.randint(7, 12), 'mode': self.mode
            }
            logger.debug(f"Generiere Fake-Daten (route): {fake_pos}")
            return fake_pos
        else:
            logger.warning("Routenmodus aktiv, aber kein Routensimulator initialisiert.")
            return self.generate_fake_data()

    # --- check_assist_now bleibt ---
    def check_assist_now(self, force_update=False):
        if self.mode != "real" or not self.assist_now_enabled:
            return True

        # NEU: Backoff-Logik bei vorherigen Fehlern
        if self._assist_now_fail_count > 0 and not force_update:
            backoff_seconds = min(
                self._assist_now_backoff_base * (2 ** (self._assist_now_fail_count - 1)),
                self._assist_now_max_backoff
            )
            if self._assist_now_last_attempt:
                elapsed = (datetime.now() - self._assist_now_last_attempt).total_seconds()
                if elapsed < backoff_seconds:
                    # Noch in Backoff-Phase, überspringe
                    return True
                logger.info(f"AssistNow Backoff abgelaufen ({elapsed:.0f}s >= {backoff_seconds:.0f}s). Neuer Versuch...")

        update_interval_days = ASSIST_NOW_CONFIG.get("days", 7) - 1
        time_since_last = datetime.now() - self.last_assist_now_update
        interval_elapsed = time_since_last >= timedelta(days=update_interval_days)

        if force_update or interval_elapsed:
            log_prefix = "Manuelles" if force_update else "Periodisches"
            logger.info(f"{log_prefix} AssistNow Offline Update wird versucht...")
            self._assist_now_last_attempt = datetime.now()

            data = self.download_assist_now_data()
            if data is not None:
                if self.send_assist_now_data(data):
                    self.last_assist_now_update = datetime.now()
                    self._assist_now_fail_count = 0  # Reset bei Erfolg
                    logger.info("AssistNow Offline Update erfolgreich durchgeführt.")
                    return True
                else:
                    self._assist_now_fail_count += 1
                    next_retry = min(self._assist_now_backoff_base * (2 ** (self._assist_now_fail_count - 1)), self._assist_now_max_backoff)
                    logger.error(f"AssistNow Offline-Daten konnten nicht an das Modul gesendet werden. Nächster Versuch in {next_retry:.0f}s.")
                    return False
            else:
                self._assist_now_fail_count += 1
                next_retry = min(self._assist_now_backoff_base * (2 ** (self._assist_now_fail_count - 1)), self._assist_now_max_backoff)
                logger.error(f"AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in {next_retry:.0f}s (Versuch #{self._assist_now_fail_count}).")
                return False
        else:
            return True

    # --- change_gps_mode bleibt ---
    def change_gps_mode(self, new_mode):
        if new_mode == self.mode:
            logger.info(f"GPS-Modus ist bereits '{new_mode}'. Keine Änderung.")
            return True

        logger.info(f"Ändere GPS-Modus von '{self.mode}' zu: {new_mode}")
        previous_mode = self.mode
        self.mode = new_mode

        if new_mode == "fake_route":
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            if not self.route_simulator or previous_mode == "real":
                if self.last_known_position and 'lat' in self.last_known_position:
                    start_lat = self.last_known_position['lat']
                    start_lon = self.last_known_position['lon']
                    logger.info(
                        f"Starte Routensimulator von letzter bekannter Position ({start_lat:.6f}, {start_lon:.6f}).")
                else:
                    logger.info(f"Starte Routensimulator von Kartenmitte ({start_lat:.6f}, {start_lon:.6f}).")
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
            self.close_serial()
            logger.info("Serielle Verbindung für Fake-Modus geschlossen (falls offen).")
            self.last_gga_info = {'qual': 8, 'sats': 8, 'timestamp': time.time()}

        elif new_mode == "fake_random":
            self.is_fake_gps = True
            self.route_simulator = None
            self.close_serial()
            logger.info("Serielle Verbindung für Fake-Modus geschlossen (falls offen).")
            self.last_gga_info = {'qual': 8, 'sats': 8, 'timestamp': time.time()}

        elif new_mode == "real":
            self.is_fake_gps = False
            self.route_simulator = None
            self._connect_serial()  # Stellt Verbindung her, ohne Konfiguration

        else:
            logger.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            self.mode = previous_mode
            return False

        logger.info(f"GPS-Modus erfolgreich auf '{self.mode}' geändert.")
        return True
