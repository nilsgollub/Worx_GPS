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
        self._connect_serial()  # Versuch, die Verbindung beim Start herzustellen

        self.last_assist_now_update = datetime.now() - timedelta(days=1)
        # --- Korrektur: Initialisiere self.mode ---
        self.mode = "real"  # Standardmodus ist "real"
        # --- Ende Korrektur ---
        self.is_fake_gps = False  # Behalte dies vorerst bei, obwohl 'mode' informativer ist
        self.route_simulator = None
        self.last_valid_fix_time = 0  # Initialisieren
        self.last_known_position = None  # Initialisieren

    # --- Hinzugefügte Methode zum Verbinden/Wiederverbinden ---
    def _connect_serial(self):
        """Versucht, die serielle Verbindung herzustellen oder wiederherzustellen."""
        if self.ser_gps and self.ser_gps.is_open:
            self.ser_gps.close()
            logging.info("Bestehende serielle Verbindung geschlossen.")
        try:
            # Nur versuchen, wenn kein Fake-Modus aktiv ist
            if self.mode == "real":
                logging.info(f"Versuche, serielle Verbindung zu {self.serial_port} herzustellen...")
                self.ser_gps = serial.Serial(self.serial_port, self.baudrate, timeout=1)
                logging.info("Serielle Verbindung erfolgreich hergestellt.")
            else:
                logging.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
                self.ser_gps = None
        except serial.SerialException as e:
            logging.error(f"Fehler beim Herstellen der seriellen Verbindung: {e}")
            self.ser_gps = None  # Setze auf None, wenn die Verbindung fehlschlägt
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung: {e}")
            self.ser_gps = None

    # --- Ende Hinzufügung ---

    # --- Hinzugefügte Methode _reconnect_serial (wird in get_gps_data verwendet) ---
    def _reconnect_serial(self):
        """Wrapper für _connect_serial für den Einsatz bei Fehlern."""
        self._connect_serial()

    # --- Ende Hinzufügung ---

    class RouteSimulator:
        # ... (Inhalt der RouteSimulator-Klasse bleibt gleich) ...
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
        # ... (Inhalt bleibt gleich) ...
        return (lat >= self.lat_bounds[0] and lat <= self.lat_bounds[1] and lon >= self.lon_bounds[0] and lon <=
                self.lon_bounds[1])

    def download_assist_now_data(self):
        # ... (Inhalt bleibt gleich) ...
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
                print("Keine AssistNow Offline-Daten erhalten.")
                return None
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
            return None  # Rückgabewert None bei Fehler

    def send_assist_now_data(self, data):
        # ... (Inhalt bleibt gleich, aber prüft self.ser_gps) ...
        if not self.ser_gps or not self.ser_gps.is_open:
            logging.warning("Kann AssistNow nicht senden: Serielle Verbindung nicht offen.")
            return

        # Plattformspezifisches Senden ist wahrscheinlich nicht nötig, pyserial abstrahiert das
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
        # --- Korrektur: Verwende self.mode ---
        if self.mode == "fake_random":
            return self.generate_fake_data()
        elif self.mode == "fake_route":
            return self.generate_fake_route_data()
        elif self.mode == "real":
            # --- Ende Korrektur ---
            if not self.ser_gps or not self.ser_gps.is_open:
                logging.warning("Serielle GPS-Verbindung nicht offen.")
                self._reconnect_serial()  # Versuch, die Verbindung wiederherzustellen
                return None  # Im Fehlerfall None zurückgeben

            try:
                line = self.ser_gps.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('$'):
                    try:
                        msg = pynmea2.parse(line)
                        if isinstance(msg, pynmea2.types.talker.GGA):
                            if hasattr(msg, 'gps_qual') and msg.gps_qual is not None and msg.gps_qual > 0:
                                current_time = time.time()
                                self.last_valid_fix_time = current_time
                                self.last_known_position = {
                                    'lat': msg.latitude,
                                    'lon': msg.longitude,
                                    'timestamp': current_time,
                                    'satellites': msg.num_sats if hasattr(msg, 'num_sats') else 0,
                                    'mode': self.mode
                                }
                                logging.debug(f"Gültige GGA-Daten empfangen: {self.last_known_position}")
                                return self.last_known_position
                            else:
                                logging.debug(
                                    f"GGA empfangen, aber kein gültiger Fix (Qual={getattr(msg, 'gps_qual', 'N/A')}).")
                                return None  # Kein gültiger Fix, None zurückgeben
                        else:
                            logging.debug(f"Andere NMEA-Nachricht empfangen: {msg.sentence_type}")
                            return None  # Keine GGA-Nachricht, None zurückgeben
                    except pynmea2.ParseError as e:
                        logging.warning(f"Fehler beim Parsen der NMEA-Zeile: {e} - Zeile: '{line}'")
                        return None
                    except AttributeError as e:
                        logging.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Nachricht: {msg}")
                        return None
            except serial.SerialException as e:
                logging.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                self._reconnect_serial()
                return None  # Im Fehlerfall None zurückgeben
            except Exception as e:
                logging.error(f"Unerwarteter Fehler in get_gps_data: {e}")
                return None  # Im Fehlerfall None zurückgeben
        # Fallback, wenn kein Modus passt oder anderer Fehler
        return None

    # --- Hinzugefügte Methoden für Fake-Daten (Beispielimplementierung) ---
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
        self.last_known_position = fake_pos  # Auch hier letzte Position merken
        return fake_pos

    def generate_fake_route_data(self):
        """Generiert Fake-GPS-Daten basierend auf dem Routensimulator."""
        if self.route_simulator:
            # Beispiel: Alle paar Aufrufe die Richtung ändern
            if random.random() < 0.1:  # 10% Chance
                self.route_simulator.change_direction(random.randint(-30, 30))

            lat, lon = self.route_simulator.move()
            fake_pos = {
                'lat': lat,
                'lon': lon,
                'timestamp': time.time(),
                'satellites': random.randint(7, 12),  # Routensimulation hat meist guten Empfang
                'mode': self.mode
            }
            logging.debug(f"Generiere Fake-Daten (route): {fake_pos}")
            self.last_known_position = fake_pos  # Auch hier letzte Position merken
            return fake_pos
        else:
            logging.warning("Routenmodus aktiv, aber kein Routensimulator initialisiert.")
            # Fallback auf zufällige Daten oder None
            return self.generate_fake_data()

    # --- Ende Hinzufügung Fake-Daten ---

    def check_assist_now(self):
        # ... (Inhalt bleibt gleich) ...
        if self.assist_now_enabled and datetime.now() - self.last_assist_now_update >= timedelta(days=1):
            data = self.download_assist_now_data()
            if data is not None:
                self.send_assist_now_data(data)
                self.last_assist_now_update = datetime.now()
            else:
                print("AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nchster Versuch in 2 Sekunden.")
                time.sleep(2)  # Warte 2 Sekunden bis zum nächsten Versuch
                return False  # Geändert zu False, um anzuzeigen, dass es nicht geklappt hat
        return True  # True, wenn kein Update nötig war oder erfolgreich

    def change_gps_mode(self, new_mode):
        """Ändert den GPS-Modus (real, fake_random, fake_route)."""
        logging.info(f"Ändere GPS-Modus zu: {new_mode}")
        # --- Korrektur: Setze self.mode und self.is_fake_gps ---
        if new_mode == "fake_route":
            self.mode = "fake_route"
            self.is_fake_gps = True  # Behalte is_fake_gps vorerst für Kompatibilität
            start_lat, start_lon = self.map_center
            # Initialisiere Simulator nur, wenn er noch nicht existiert oder Modus wechselt
            if not self.route_simulator or self.mode != "fake_route":
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
            # Schließe serielle Verbindung, wenn sie offen ist
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logging.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "fake_random":
            self.mode = "fake_random"
            self.is_fake_gps = True
            self.route_simulator = None  # Kein Simulator für random
            # Schließe serielle Verbindung, wenn sie offen ist
            if self.ser_gps and self.ser_gps.is_open:
                self.ser_gps.close()
                self.ser_gps = None
                logging.info("Serielle Verbindung für Fake-Modus geschlossen.")
        elif new_mode == "real":
            self.mode = "real"
            self.is_fake_gps = False
            self.route_simulator = None
            # Versuche, die serielle Verbindung herzustellen
            self._connect_serial()
        else:
            logging.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            return False  # Ungültiger Modus
        # --- Ende Korrektur ---
        return True  # Modus erfolgreich geändert
