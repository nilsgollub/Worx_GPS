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

# --- NEU: Importiere pyubx2 ---
try:
    from pyubx2 import UBXMessage, SET, POLL, UBX_CONFIG_DATABASE, protocol

    PYUBX2_AVAILABLE = True
    # Schlüssel-IDs für CFG-VALSET/GET (optional, aber nützlich)
    # Beispiel: from pyubx2.ubx_cfgval import UBX_CFGVAL_KEYS
except ImportError:
    PYUBX2_AVAILABLE = False
    logging.warning("pyubx2 nicht gefunden. UBX-Konfiguration ist nicht möglich.")
# --- ENDE NEU ---

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
        # --- Geändert: _connect_serial ruft jetzt _configure_ublox auf ---
        self._connect_serial()

        # Zeitstempel des letzten erfolgreichen AssistNow-Updates
        self.last_assist_now_update = datetime.now() - timedelta(days=ASSIST_NOW_CONFIG.get("days", 7) + 1)

        self.is_fake_gps = False
        self.route_simulator = None
        self.last_valid_fix_time = 0
        self.last_known_position = None
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
                logger.info(f"Versuche, serielle Verbindung zu {self.serial_port} herzustellen...")
                self.ser_gps = serial.Serial(self.serial_port, self.baudrate, timeout=1)
                logger.info("Serielle Verbindung erfolgreich hergestellt.")
                # Status auf "No Fix" setzen, bis der erste GGA kommt
                self.last_gga_info = {'qual': 0, 'sats': 0, 'timestamp': time.time()}

                # --- NEU: U-BLOX Konfiguration nach erfolgreicher Verbindung ---
                if PYUBX2_AVAILABLE:
                    self._configure_ublox()
                else:
                    logger.warning("pyubx2 nicht verfügbar, U-BLOX Konfiguration übersprungen.")
                # --- ENDE NEU ---

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
        # _connect_serial enthält bereits den Aufruf für _configure_ublox
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

    # --- NEUE HILFSMETHODE zum Senden von UBX-Nachrichten ---
    def _send_ubx_config(self, msg):
        """Hilfsfunktion zum Senden einer UBX Konfigurationsnachricht."""
        if not PYUBX2_AVAILABLE:
            logger.error("Kann UBX nicht senden: pyubx2 nicht verfügbar.")
            return False
        if self.ser_gps and self.ser_gps.is_open:
            try:
                logger.debug(f"Sende UBX Konfiguration: {msg}")
                self.ser_gps.write(msg.serialize())
                time.sleep(0.1)  # Kurze Pause nach dem Senden
                # Optional: Auf ACK/NAK warten (komplexer, erfordert Lesen)
                # response = self._read_ubx_response(msg.identity)
                # if response == 'ACK': return True
                # else: return False
                return True
            except serial.SerialTimeoutException:
                logger.error(f"Timeout beim Senden der UBX Nachricht {msg.identity}.")
                self._reconnect_serial()  # Versuch wiederherzustellen
                return False
            except serial.SerialException as e:
                logger.error(f"Serieller Fehler beim Senden der UBX Nachricht {msg.identity}: {e}")
                self._reconnect_serial()  # Versuch wiederherzustellen
                return False
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Senden der UBX Nachricht {msg.identity}: {e}", exc_info=True)
                return False
        else:
            logger.warning("Kann UBX Konfiguration nicht senden, Port nicht offen.")
            return False

    # --- ENDE NEUE HILFSMETHODE ---

    # --- NEUE METHODE zur U-BLOX Konfiguration ---
    def _configure_ublox(self):
        """Sendet Konfigurationsbefehle an das U-BLOX Modul via pyubx2."""
        if not PYUBX2_AVAILABLE:
            logger.warning("pyubx2 nicht verfügbar, Konfiguration übersprungen.")
            return

        logger.info("Starte U-BLOX Konfiguration...")
        config_success = True
        save_needed = False  # Flag, ob Konfiguration gespeichert werden muss

        # --- 1. Dynamic Platform Model (CFG-NAV5) ---
        # Pedestrian = 2, Portable = 0 (Default). Pedestrian (2) oder Automotive (4) könnten passen.
        # Maske 'dyn': Bit 0 muss gesetzt sein (0x0001)
        # Siehe u-blox Protokoll Spezifikation für Details zu CFG-NAV5 Payload.
        # pyubx2 < 1.2.15: UBXMessage('CFG', 'CFG-NAV5', SET, mask=1, dynModel=2)
        # pyubx2 >= 1.2.15: UBXMessage('CFG', 'CFG-NAV5', SET, payload=b'\x01\x00\x02\x00\x00\x00\x00\x00' + b'\x00'*28) # mask=1, dynModel=2

        # Sicherer: CFG-VALSET verwenden (wenn vom Modul unterstützt, NEO-7M sollte es)
        # Key ID für dynModel: 0x20110021 (siehe u-blox Doku oder pyubx2.ubx_cfgval)
        try:
            # Alternative mit CFG-VALSET (empfohlen für neuere Module/Firmware)
            # key_id = 0x20110021 # CFG-NAVSPG-DYNMODEL
            # value = b'\x02' # Pedestrian
            # msg_nav5 = UBXMessage.config_set(layers=UBX_CONFIG_DATABASE.RAM, transaction=0, cfgData=[(key_id, value)])

            # Klassisch mit CFG-NAV5 (prüfe pyubx2 Version!)
            # Annahme: pyubx2 >= 1.2.15
            payload_nav5 = b'\x01\x00' + b'\x02' + b'\x00' * 33  # mask=1 (dyn), dynModel=2 (Pedestrian)
            msg_nav5 = UBXMessage('CFG', 'CFG-NAV5', SET, payload=payload_nav5)

            if self._send_ubx_config(msg_nav5):
                logger.info("CFG-NAV5: Dynamic Model auf 'Pedestrian' (2) gesetzt.")
                save_needed = True
            else:
                config_success = False
                logger.error("Fehler beim Setzen von CFG-NAV5.")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen/Senden von CFG-NAV5: {e}")
            config_success = False

        # --- 2. SBAS (EGNOS) aktivieren (CFG-SBAS) ---
        # mode=1 (Enabled), usage=0x07 (Range, DiffCorr, Integrity)
        # Siehe u-blox Protokoll Spezifikation für Details zu CFG-SBAS Payload.
        # pyubx2 < 1.2.15: UBXMessage('CFG', 'CFG-SBAS', SET, mode=1, usage=7, maxSBAS=1, scanmode2=0, scanmode1=0) # Beispiel
        # pyubx2 >= 1.2.15: payload muss manuell erstellt werden
        try:
            payload_sbas = b'\x01' + b'\x07' + b'\x01' + b'\x00\x00\x00\x00\x00'  # mode=1, usage=7, maxSBAS=1, rest=0
            msg_sbas = UBXMessage('CFG', 'CFG-SBAS', SET, payload=payload_sbas)
            if self._send_ubx_config(msg_sbas):
                logger.info("CFG-SBAS: SBAS aktiviert (Mode=1, Usage=7).")
                save_needed = True
            else:
                config_success = False
                logger.error("Fehler beim Setzen von CFG-SBAS.")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen/Senden von CFG-SBAS: {e}")
            config_success = False

        # --- 3. NMEA Nachrichten konfigurieren (CFG-MSG) ---
        # Deaktiviere unnötige Nachrichten, setze Rate für GGA/GSA
        # Raten sind pro Navigationslösung (z.B. 1 = jede Lösung, 5 = jede 5. Lösung)
        # Annahme: UART1 wird verwendet (portID=1)
        # NMEA IDs: GGA=0x00, GLL=0x01, GSA=0x02, GSV=0x03, RMC=0x04, VTG=0x05
        nmea_msgs_to_configure = {
            0xF0: {  # NMEA Standard Talker ID
                0x00: 1,  # GGA: Jede Navigationslösung (z.B. 1Hz wenn Rate 1Hz ist)
                0x02: 5,  # GSA: Jede 5. Navigationslösung
                0x04: 0,  # RMC: Deaktivieren
                0x05: 0,  # VTG: Deaktivieren
                0x03: 0,  # GSV: Deaktivieren (kann viele Nachrichten erzeugen)
                0x01: 0  # GLL: Deaktivieren
                # Füge hier weitere hinzu, falls nötig (z.B. ZDA deaktivieren: 0x08)
            }
        }
        try:
            for msgClass, ids_rates in nmea_msgs_to_configure.items():
                for msgID, rate in ids_rates.items():
                    # Payload: msgClass (1), msgID (1), ratePort0..5 (6 bytes)
                    # Wir setzen nur UART1 (Index 1 in der Liste)
                    rates = [0] * 6  # Default: alle Ports 0
                    rates[1] = rate  # Setze Rate für UART1
                    payload_msg = bytes([msgClass, msgID]) + bytes(rates)
                    msg_cfg = UBXMessage('CFG', 'CFG-MSG', SET, payload=payload_msg)
                    if self._send_ubx_config(msg_cfg):
                        action = "gesetzt auf Rate" if rate > 0 else "deaktiviert"
                        logger.info(
                            f"CFG-MSG: NMEA Nachricht (Class {msgClass:02X}, ID {msgID:02X}) {action} {rate if rate > 0 else ''}.")
                        save_needed = True  # Änderung gemacht
                    else:
                        config_success = False
                        logger.error(
                            f"Fehler beim Konfigurieren von NMEA Nachricht (Class {msgClass:02X}, ID {msgID:02X}).")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen/Senden von CFG-MSG: {e}")
            config_success = False

        # --- 4. Navigationsrate setzen (CFG-RATE) --- (Optional, Standard ist 1Hz)
        # Beispiel: 1Hz (measRate=1000ms)
        # measRate: Millisekunden zwischen Messungen
        # navRate: Anzahl Messungen pro Navigationslösung (1 = jede Messung ergibt eine Lösung)
        # timeRef: 0=UTC, 1=GPS, 2=GLONASS etc. (1 für GPS Zeit ist oft gut)
        try:
            meas_rate_ms = 1000  # 1 Hz
            nav_rate_cycles = 1
            time_ref = 1  # GPS time
            payload_rate = meas_rate_ms.to_bytes(2, 'little') + \
                           nav_rate_cycles.to_bytes(2, 'little') + \
                           time_ref.to_bytes(2, 'little')
            msg_rate = UBXMessage('CFG', 'CFG-RATE', SET, payload=payload_rate)
            if self._send_ubx_config(msg_rate):
                logger.info(f"CFG-RATE: Messrate auf {1000 / meas_rate_ms:.1f}Hz ({meas_rate_ms}ms) gesetzt.")
                save_needed = True
            else:
                config_success = False
                logger.error("Fehler beim Setzen von CFG-RATE.")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen/Senden von CFG-RATE: {e}")
            config_success = False

        # --- 5. Konfiguration speichern (CFG-CFG) ---
        # WICHTIG, damit die Einstellungen bleiben! Nur speichern, wenn Änderungen gemacht wurden.
        if save_needed and config_success:  # Nur speichern, wenn bisher alles ok war und Änderungen gemacht wurden
            logger.info("Speichere Konfiguration im U-BLOX Modul...")
            # saveMask: Welche Konfigurationsbereiche speichern (0x001F = IO, MSG, INF, NAV, RXM)
            # deviceMask: Wohin speichern (0x04=BBR, 0x02=Flash, 0x01=I2C EEPROM)
            # Für NEO-7M ist BBR (Battery Backed RAM) relevant. Flash oft nicht vorhanden.
            # Maske 0x04 (BBR) oder 0x07 (BBR+Flash+EEPROM) probieren.
            try:
                save_mask = 0x001F  # IO, MSG, INF, NAV, RXM
                dev_mask = 0x04  # Nur BBR
                payload_save = save_mask.to_bytes(4, 'little') + b'\x00' * 4 + dev_mask.to_bytes(4,
                                                                                                 'little')  # clearMask=0, loadMask=0
                msg_save = UBXMessage('CFG', 'CFG-CFG', SET, payload=payload_save)
                if self._send_ubx_config(msg_save):
                    logger.info("CFG-CFG: Konfiguration erfolgreich zum Speichern in BBR angewiesen.")
                else:
                    config_success = False
                    logger.error("Fehler beim Senden des CFG-CFG Speicherbefehls.")
            except Exception as e:
                logger.error(f"Fehler beim Erstellen/Senden von CFG-CFG: {e}")
                config_success = False
        elif not save_needed:
            logger.info("Keine Änderungen an der U-BLOX Konfiguration vorgenommen, Speichern übersprungen.")
        elif not config_success:
            logger.warning("Fehler während der U-BLOX Konfiguration aufgetreten, Speichern übersprungen.")

        if config_success:
            logger.info("U-BLOX Konfiguration erfolgreich abgeschlossen (oder keine Änderungen nötig).")
        else:
            logger.warning("U-BLOX Konfiguration mit Fehlern abgeschlossen.")

        # Optional: Konfiguration zurücklesen (POLL) und prüfen (z.B. CFG-MSG für GGA)
        # try:
        #     msg_poll = UBXMessage('CFG', 'CFG-MSG', POLL, payload=b'\xF0\x00') # Poll GGA config
        #     if self._send_ubx_config(msg_poll):
        #         # Hier müsste man auf die Antwort warten und sie parsen
        #         logger.info("CFG-MSG POLL für GGA gesendet. Antwort muss manuell gelesen werden.")
        # except Exception as e:
        #     logger.error(f"Fehler beim Senden von CFG-MSG POLL: {e}")

    # --- ENDE NEUE METHODE ---

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
        """Lädt AssistNow Offline Daten herunter (für u-blox 7 optimiert)."""
        if not self.assist_now_token:
            logger.error("AssistNow Token fehlt in der Konfiguration.")
            return None
        try:
            headers = {"useragent": "Thingstream Client"}

            # --- Angepasste Parameter (basierend auf Doku für u-blox 7) ---
            # Hole die gewünschte Anzahl Tage aus der Config, prüfe ob gültig für u7
            requested_days = ASSIST_NOW_CONFIG.get("days", 7)  # Standard 7 Tage aus Config holen
            valid_u7_days = [1, 2, 3, 5, 7, 10, 14]
            if requested_days not in valid_u7_days:
                logger.warning(
                    f"Ungültiger Wert für 'days' ({requested_days}) in ASSIST_NOW_CONFIG für u-blox 7. Verwende Standardwert 7.")
                effective_days = 7  # Fallback auf einen gültigen Wert
            else:
                effective_days = requested_days

            params = {
                "token": self.assist_now_token,
                "gnss": "gps",
                "format": "aid",  # Korrekt für u-blox 7
                "days": effective_days  # Korrekt für u-blox 7, Wert validiert
                # "period": 1,         # Falsch für u-blox 7
                # "resolution": 1      # Falsch für u-blox 7
                # "alm": "gps",        # Falsch für format=aid
                # "datatype": "alm",   # Falsch für u-blox 7
            }
            # --- Ende Anpassung ---

            logger.info(
                f"Lade AssistNow Offline Daten von {self.assist_now_offline_url} mit Token {self.assist_now_token[:5]}... (Params: {params})")  # Logge die Parameter
            response = requests.get(self.assist_now_offline_url, headers=headers, params=params,
                                    timeout=15)
            response.raise_for_status()  # Löst HTTPError bei Fehlern aus (wie 400 Bad Request)

            # ... (Rest der Methode bleibt gleich: Prüfung auf leeren Inhalt, Textfehler, Rückgabe) ...

            if not response.content:
                logger.warning("Keine AssistNow Offline-Daten erhalten (leere Antwort).")
                return None

            # Prüfen, ob die Antwort Text enthält (Fehlermeldung von u-blox?)
            try:
                response_text = response.content.decode('utf-8', errors='ignore')
                # Suche nach typischen Fehlermeldungen
                if "error" in response_text.lower() or "invalid token" in response_text.lower() or "bad request" in response_text.lower():
                    logger.error(f"Fehler von AssistNow Service erhalten: {response_text}")
                    return None
            except UnicodeDecodeError:
                # Das ist der erwartete Fall bei binären Daten
                pass

            logger.info(f"AssistNow Offline-Daten erfolgreich heruntergeladen ({len(response.content)} Bytes).")
            return response.content

        except requests.exceptions.Timeout:
            logger.error("Timeout beim Herunterladen der AssistNow Offline-Daten.")
            return None
        except requests.exceptions.RequestException as e:
            # Logge den Statuscode und die URL, falls verfügbar
            status_code = e.response.status_code if e.response is not None else "N/A"
            req_url = e.request.url if e.request is not None else "N/A"
            logger.error(
                f"Fehler beim Herunterladen der AssistNow Offline-Daten (Status: {status_code}) für URL {req_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim AssistNow Download: {e}", exc_info=True)
            return None

    def send_assist_now_data(self, data):
        """Sendet die heruntergeladenen AssistNow Daten an das GPS-Modul."""
        if not self.ser_gps or not self.ser_gps.is_open:
            logger.warning("Kann AssistNow nicht senden: Serielle Verbindung nicht offen.")
            return False  # Signalisiert Misserfolg

        try:
            bytes_written = self.ser_gps.write(data)
            self.ser_gps.flush()  # Sicherstellen, dass Daten gesendet werden
            logger.info(f"AssistNow Offline-Daten ({bytes_written} Bytes) erfolgreich gesendet.")
            return True  # Signalisiert Erfolg
        except serial.SerialTimeoutException:
            logger.error("Timeout beim Senden der AssistNow Offline-Daten.")
            self._reconnect_serial()  # Versuch, die Verbindung wiederherzustellen
            return False
        except serial.SerialException as e:
            logger.error(f"Serieller Fehler beim Senden der AssistNow Offline-Daten: {e}")
            self._reconnect_serial()
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Senden der AssistNow Offline-Daten: {e}", exc_info=True)
            return False

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
                    # Versuche, gps_qual zu lesen, Standardwert 0
                    qual_str = getattr(gga_msg, 'gps_qual', '0')
                    if qual_str:  # Nur konvertieren, wenn nicht leer
                        qual = int(qual_str)
                    else:
                        qual = 0
                except (ValueError, TypeError):
                    logger.warning(f"Konnte gps_qual '{qual_str}' nicht in int konvertieren.")
                    qual = 0  # Fallback auf 0 bei Fehler
                try:
                    # Versuche, num_sats zu lesen, Standardwert 0
                    sats_str = getattr(gga_msg, 'num_sats', '0')
                    if sats_str:  # Nur konvertieren, wenn nicht leer
                        sats = int(sats_str)
                    else:
                        sats = 0
                except (ValueError, TypeError):
                    logger.warning(f"Konnte num_sats '{sats_str}' nicht in int konvertieren.")
                    sats = 0  # Fallback auf 0 bei Fehler

                # Aktualisiere IMMER die letzten GGA-Statusinformationen
                self.last_gga_info['qual'] = qual
                self.last_gga_info['sats'] = sats
                self.last_gga_info['timestamp'] = current_time

                # Prüfe, ob der Fix gültig ist (Qualität > 0)
                if qual > 0:
                    self.last_valid_fix_time = current_time
                    # Aktualisiere die letzte bekannte Position
                    try:
                        # Stelle sicher, dass Lat/Lon gültige Floats sind und vorhanden
                        if hasattr(gga_msg, 'latitude') and hasattr(gga_msg, 'longitude') and \
                                gga_msg.latitude is not None and gga_msg.longitude is not None:
                            lat = float(gga_msg.latitude)
                            lon = float(gga_msg.longitude)
                            self.last_known_position = {
                                'lat': lat,
                                'lon': lon,
                                'timestamp': current_time,
                                'satellites': sats,
                                'mode': self.mode
                            }
                            logger.debug(
                                f"Gültige GGA-Daten verarbeitet: Qual={qual}, Sats={sats}, Pos=({lat:.6f}, {lon:.6f})")
                            return self.last_known_position  # Gib die gültige Position zurück
                        else:
                            logger.warning(f"GGA mit Qual={qual} hat keine gültigen Lat/Lon-Attribute: {gga_msg}")
                            return None  # Obwohl Qual > 0, sind die Daten unbrauchbar
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Fehler beim Extrahieren von Lat/Lon aus GGA: {e} - GGA: {gga_msg}")
                        return None  # Obwohl Qual > 0, sind die Daten unbrauchbar
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
        """Gibt den letzten bekannten GPS-Status inkl. Position und A-GPS Info als String zurück."""
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
        # --- Ende Positions-Hinzufügung ---

        # --- A-GPS Status hinzufügen ---
        agps_status_str = ""
        if self.assist_now_enabled:
            time_since_agps_update = datetime.now() - self.last_assist_now_update
            # Prüfen, ob das letzte Update erfolgreich war (könnte man noch detaillierter machen)
            # Hier gehen wir davon aus, dass last_assist_now_update nur bei Erfolg gesetzt wird.
            if time_since_agps_update < timedelta(days=ASSIST_NOW_CONFIG.get("days", 7) + 1):  # +1 Tag Puffer
                hours_ago = time_since_agps_update.total_seconds() / 3600
                agps_status_str = f",AGPS: OK ({hours_ago:.1f}h ago)"
            else:
                agps_status_str = ",AGPS: Stale"
        else:
            agps_status_str = ",AGPS: Off"  # Explizit anzeigen, wenn deaktiviert
        # --- Ende A-GPS Status ---

        # Format: "status,<Beschreibung>,<Satelliten>,<Latitude>,<Longitude><AGPS-Status>"
        # Latitude und Longitude sind leer, wenn keine (aktuelle) Position bekannt ist.
        status_message = f"status,{fix_description},{sats},{lat_str},{lon_str}{agps_status_str}"

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
            if random.random() < 0.1:  # Zufällige Richtungsänderung
                self.route_simulator.change_direction(random.randint(-30, 30))

            lat, lon = self.route_simulator.move()

            # Stelle sicher, dass die Route innerhalb der Grenzen bleibt (optional)
            # if not self.is_inside_boundaries(lat, lon):
            #     # Kehre um oder ändere Richtung stark
            #     self.route_simulator.change_direction(180 + random.randint(-10, 10))
            #     lat, lon = self.route_simulator.move() # Mache einen Schritt zurück

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
            return self.generate_fake_data()  # Fallback

    # --- GEÄNDERTE check_assist_now ---
    def check_assist_now(self, force_update=False):
        """
        Prüft, ob AssistNow Daten aktualisiert werden müssen (zeitbasiert oder erzwungen)
        und führt dies ggf. durch.

        Args:
            force_update (bool): Wenn True, wird das Update unabhängig vom Zeitintervall versucht.

        Returns:
            bool: True, wenn kein Update nötig war oder das Update erfolgreich war.
                  False, wenn ein Update versucht wurde, aber fehlschlug.
        """
        # Prüfe nur im Real-Modus und wenn aktiviert
        if self.mode != "real" or not self.assist_now_enabled:
            logger.debug("AssistNow nicht aktiv oder nicht im Real-Modus.")
            return True  # Nichts zu tun

        # Prüfe, ob das Update-Intervall abgelaufen ist
        update_interval_days = ASSIST_NOW_CONFIG.get("days", 7) - 1  # Update 1 Tag vor Ablauf
        time_since_last = datetime.now() - self.last_assist_now_update
        interval_elapsed = time_since_last >= timedelta(days=update_interval_days)

        # --- NEUE Bedingung: Update wenn erzwungen ODER Intervall abgelaufen ---
        if force_update or interval_elapsed:
            if force_update:
                logger.info("AssistNow Offline Update manuell angestoßen.")
            else:
                logger.info(
                    f"AssistNow Offline Update erforderlich (letztes Update: {self.last_assist_now_update}, Intervall: {update_interval_days} Tage).")

            # --- Download und Senden ---
            data = self.download_assist_now_data()
            if data is not None:
                if self.send_assist_now_data(data):
                    self.last_assist_now_update = datetime.now()  # Nur bei Erfolg aktualisieren
                    logger.info("AssistNow Offline Update erfolgreich durchgeführt.")
                    return True  # Erfolg
                else:
                    logger.error("AssistNow Offline-Daten konnten nicht an das Modul gesendet werden.")
                    # Optional: Kurze Pause vor nächstem Versuch in der Hauptschleife? Eher nicht hier.
                    return False  # Signalisiert Fehler beim Senden
            else:
                logger.error("AssistNow Offline-Daten konnten nicht heruntergeladen werden.")
                # Optional: Kurze Pause? Eher nicht hier.
                return False  # Signalisiert Fehler beim Download
            # --- Ende Download und Senden ---
        else:
            logger.debug(f"Kein AssistNow Update erforderlich (letztes Update: {self.last_assist_now_update}).")
            return True  # Kein Update nötig, also "Erfolg" im Sinne von "kein Fehler"

    # --- ENDE GEÄNDERTE check_assist_now ---

    def change_gps_mode(self, new_mode):
        """Ändert den Betriebsmodus des GPS-Handlers (real, fake_random, fake_route)."""
        if new_mode == self.mode:
            logger.info(f"GPS-Modus ist bereits '{new_mode}'. Keine Änderung.")
            return True

        logger.info(f"Ändere GPS-Modus von '{self.mode}' zu: {new_mode}")
        previous_mode = self.mode
        self.mode = new_mode  # Setze den Modus sofort

        if new_mode == "fake_route":
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            # Initialisiere Simulator, falls nicht vorhanden oder wenn von 'real' gewechselt wird
            if not self.route_simulator or previous_mode == "real":
                # Verwende letzte bekannte Position als Start, falls vorhanden und gültig
                if self.last_known_position and 'lat' in self.last_known_position:
                    start_lat = self.last_known_position['lat']
                    start_lon = self.last_known_position['lon']
                    logger.info(
                        f"Starte Routensimulator von letzter bekannter Position ({start_lat:.6f}, {start_lon:.6f}).")
                else:
                    logger.info(f"Starte Routensimulator von Kartenmitte ({start_lat:.6f}, {start_lon:.6f}).")
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))

            # Schließe serielle Verbindung, wenn sie offen war
            self.close_serial()
            logger.info("Serielle Verbindung für Fake-Modus geschlossen (falls offen).")
            # Setze Status auf Simulation
            self.last_gga_info = {'qual': 8, 'sats': 8, 'timestamp': time.time()}

        elif new_mode == "fake_random":
            self.is_fake_gps = True
            self.route_simulator = None  # Deaktiviere Routensimulator
            # Schließe serielle Verbindung, wenn sie offen war
            self.close_serial()
            logger.info("Serielle Verbindung für Fake-Modus geschlossen (falls offen).")
            # Setze Status auf Simulation
            self.last_gga_info = {'qual': 8, 'sats': 8, 'timestamp': time.time()}

        elif new_mode == "real":
            self.is_fake_gps = False
            self.route_simulator = None  # Deaktiviere Routensimulator
            # Stelle serielle Verbindung her (oder versuche es)
            self._connect_serial()
            # Status wird durch _connect_serial gesetzt (Connecting oder No Fix)

        else:
            logger.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            self.mode = previous_mode  # Setze Modus zurück
            return False

        # Reset last_known_position beim Moduswechsel? Optional, aber vielleicht sinnvoll.
        # self.last_known_position = None
        logger.info(f"GPS-Modus erfolgreich auf '{self.mode}' geändert.")
        return True
