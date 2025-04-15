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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
        self.ser_gps = None  # Initialisiere mit None, Verbindung wird später aufgebaut
        self.mode = "real"  # Standardmodus ist "real"
        self._connect_serial()  # Versuch, die Verbindung beim Start herzustellen

        self.last_assist_now_update = datetime.now() - timedelta(days=1)
        self.is_fake_gps = False  # Behalte dies vorerst bei, obwohl 'mode' informativer ist
        self.route_simulator = None
        self.last_valid_fix_time = 0  # Initialisieren
        self.last_known_position = None  # Initialisieren

    def _connect_serial(self):
        """Versucht, die serielle Verbindung herzustellen oder wiederherzustellen."""
        if self.ser_gps and self.ser_gps.is_open:
            try:
                self.ser_gps.close()
                logging.info("Bestehende serielle Verbindung geschlossen.")
            except Exception as e:
                logging.error(f"Fehler beim Schließen der bestehenden seriellen Verbindung: {e}")
            self.ser_gps = None  # Sicherstellen, dass es None ist nach dem Schließen

        # Nur versuchen, wenn kein Fake-Modus aktiv ist
        if self.mode == "real":
            try:
                logging.info(f"Versuche, serielle Verbindung zu {self.serial_port} herzustellen...")
                self.ser_gps = serial.Serial(self.serial_port, self.baudrate, timeout=1)
                logging.info("Serielle Verbindung erfolgreich hergestellt.")
            except serial.SerialException as e:
                logging.error(f"Fehler beim Herstellen der seriellen Verbindung: {e}")
                self.ser_gps = None  # Setze auf None, wenn die Verbindung fehlschlägt
            except Exception as e:
                logging.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung: {e}")
                self.ser_gps = None
        else:
            logging.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
            self.ser_gps = None

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
            # Einfaches Bewegungsmuster: Gerade Linie in der aktuellen Richtung
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
            response.raise_for_status()  # Fehler auslösen, wenn der Download fehlschlägt
            if not response.content:
                logging.warning("Keine AssistNow Offline-Daten erhalten.")  # Geändert zu warning
                return None
            logging.info("AssistNow Offline-Daten erfolgreich heruntergeladen.")  # Erfolgs-Log
            return response.content
        except requests.exceptions.RequestException as e:
            # Verwende logging.error statt print
            logging.error(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
            return None  # Rückgabewert None bei Fehler

    def send_assist_now_data(self, data):
        if not self.ser_gps or not self.ser_gps.is_open:
            logging.warning("Kann AssistNow nicht senden: Serielle Verbindung nicht offen.")
            return

        try:
            self.ser_gps.write(data)  # UBX-Daten direkt senden
            logging.info("AssistNow Offline-Daten erfolgreich gesendet.")
        except serial.SerialException as e:
            logging.error(f"Serieller Fehler beim Senden der AssistNow Offline-Daten: {e}")
            self._reconnect_serial()  # Versuch wiederzuverbinden
        except Exception as e:
            logging.error(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")

    def get_gps_data(self):
        """Liest und parst eine einzelne NMEA-Nachricht vom seriellen Port oder generiert Fake-Daten."""
        if self.mode == "fake_random":
            return self.generate_fake_data()
        elif self.mode == "fake_route":
            return self.generate_fake_route_data()
        elif self.mode == "real":
            if not self.ser_gps or not self.ser_gps.is_open:
                logging.warning("Serielle GPS-Verbindung nicht offen.")
                self._reconnect_serial()
                return None

            try:
                line_bytes = self.ser_gps.readline()
                if not line_bytes:  # Timeout oder leere Zeile
                    logging.debug("Keine Daten von serieller Schnittstelle gelesen (Timeout?).")
                    return None
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if line.startswith('$'):
                    try:
                        msg = pynmea2.parse(line)
                        if isinstance(msg, pynmea2.types.talker.GGA):
                            if hasattr(msg, 'gps_qual') and msg.gps_qual is not None and msg.gps_qual > 0:
                                current_time = time.time()
                                self.last_valid_fix_time = current_time
                                # --- KORREKTUR: Konvertiere num_sats zu int ---
                                try:
                                    num_sats_int = int(msg.num_sats) if hasattr(msg, 'num_sats') and msg.num_sats else 0
                                except (ValueError, TypeError):
                                    logging.warning(
                                        f"Konnte num_sats '{getattr(msg, 'num_sats', 'N/A')}' nicht in int konvertieren.")
                                    num_sats_int = 0  # Fallback
                                # --- ENDE KORREKTUR ---
                                self.last_known_position = {
                                    'lat': msg.latitude,
                                    'lon': msg.longitude,
                                    'timestamp': current_time,
                                    # --- KORREKTUR: Verwende konvertierten Wert ---
                                    'satellites': num_sats_int,
                                    # --- ENDE KORREKTUR ---
                                    'mode': self.mode
                                }
                                logging.debug(f"Gültige GGA-Daten empfangen: {self.last_known_position}")
                                return self.last_known_position
                            else:
                                logging.debug(
                                    f"GGA empfangen, aber kein gültiger Fix (Qual={getattr(msg, 'gps_qual', 'N/A')}).")
                                return None
                        else:
                            logging.debug(f"Andere NMEA-Nachricht empfangen: {msg.sentence_type}")
                            return None
                    except pynmea2.ParseError as e:
                        logging.warning(f"Fehler beim Parsen der NMEA-Zeile: {e} - Zeile: '{line}'")
                        return None
                    except AttributeError as e:
                        logging.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Nachricht: {msg}")
                        return None
                else:
                    logging.debug(f"Ignoriere Zeile ohne '$': '{line[:50]}...'")  # Nur Anfang loggen
                    return None  # Keine NMEA-Nachricht
            except serial.SerialException as e:
                logging.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                self._reconnect_serial()
                return None
            except UnicodeDecodeError as e:
                logging.warning(f"Fehler beim Dekodieren der seriellen Daten: {e}")
                return None
            except Exception as e:
                logging.error(f"Unerwarteter Fehler in get_gps_data: {e}", exc_info=True)  # exc_info für Traceback
                return None
        # Fallback
        return None

    def generate_fake_data(self):
        """Generiert zufällige Fake-GPS-Daten."""
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
        """Generiert Fake-GPS-Daten basierend auf dem Routensimulator."""
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
            logging.info("Prüfe auf AssistNow Offline Update...")  # Log
            data = self.download_assist_now_data()
            if data is not None:
                self.send_assist_now_data(data)
                self.last_assist_now_update = datetime.now()
                logging.info("AssistNow Offline Update erfolgreich durchgeführt.")  # Log
            else:
                # Verwende logging.error statt print
                logging.error(
                    "AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in 2 Sekunden.")
                time.sleep(2)
                return False
        return True

    def change_gps_mode(self, new_mode):
        """Ändert den GPS-Modus (real, fake_random, fake_route)."""
        if new_mode == self.mode:
            logging.info(f"GPS-Modus ist bereits '{new_mode}'. Keine Änderung.")
            return True  # Keine Änderung nötig

        logging.info(f"Ändere GPS-Modus von '{self.mode}' zu: {new_mode}")
        if new_mode == "fake_route":
            self.mode = "fake_route"
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            if not self.route_simulator:  # Nur initialisieren, wenn nicht vorhanden
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
            # Schließe serielle Verbindung, wenn sie offen ist
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logging.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "fake_random":
            self.mode = "fake_random"
            self.is_fake_gps = True
            self.route_simulator = None
            # Schließe serielle Verbindung, wenn sie offen ist
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logging.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "real":
            self.mode = "real"
            self.is_fake_gps = False
            self.route_simulator = None
            # Versuche, die serielle Verbindung herzustellen (oder wiederherzustellen)
            self._connect_serial()
        else:
            logging.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            return False
        return True
