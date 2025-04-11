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
        self.ser_gps = serial.Serial(self.serial_port, self.baudrate, timeout=1)
        self.last_assist_now_update = datetime.now() - timedelta(days=1)
        self.is_fake_gps = False
        self.route_simulator = None

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
                print("Keine AssistNow Offline-Daten erhalten.")
                return None
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
            return None  # Rückgabewert None bei Fehler

    def send_assist_now_data(self, data):
        if platform.system() == "Linux":
            try:
                with open(self.serial_port, "wb") as f:  # Pfad zur seriellen Schnittstelle anpassen
                    f.write(data)  # UBX-Daten direkt senden
                    print("AssistNow Offline-Daten erfolgreich gesendet.")
            except Exception as e:
                print(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")
        else:
            try:
                self.ser_gps.write(data)  # UBX-Daten direkt senden
                print("AssistNow Offline-Daten erfolgreich gesendet.")
            except Exception as e:
                print(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")

    def get_gps_data(self):
        """Liest und parst eine einzelne NMEA-Nachricht vom seriellen Port oder generiert Fake-Daten."""
        if self.mode == "fake_random":
            return self.generate_fake_data()
        elif self.mode == "fake_route":
            return self.generate_fake_route_data()
        elif self.mode == "real":
            if not self.ser_gps or not self.ser_gps.is_open:
                logging.warning("Serielle GPS-Verbindung nicht offen.")
                self._reconnect_serial()  # Versuch, die Verbindung wiederherzustellen
                return None

            try:
                line = self.ser_gps.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('$'):
                    try:
                        msg = pynmea2.parse(line)
                        # --- Modification Start ---
                        # Check if the message is a GGA sentence before accessing GGA fields
                        if isinstance(msg, pynmea2.types.talker.GGA):
                            # Check for a valid GPS fix (gps_qual > 0)
                            if hasattr(msg, 'gps_qual') and msg.gps_qual is not None and msg.gps_qual > 0:
                                current_time = time.time()
                                self.last_valid_fix_time = current_time  # Update last valid fix time
                                self.last_known_position = {
                                    'lat': msg.latitude,
                                    'lon': msg.longitude,
                                    'timestamp': current_time,
                                    'satellites': msg.num_sats if hasattr(msg, 'num_sats') else 0,
                                    'mode': self.mode  # Include current mode
                                }
                                logging.debug(f"Gültige GGA-Daten empfangen: {self.last_known_position}")
                                return self.last_known_position
                            else:
                                logging.debug(
                                    f"GGA empfangen, aber kein gültiger Fix (Qual={getattr(msg, 'gps_qual', 'N/A')}).")
                                # Optional: Return last known position if no fix for a while?
                                # Or just return None
                                return None
                        # Optional: Handle other message types if needed (e.g., RMC for speed/course)
                        # elif isinstance(msg, pynmea2.RMC):
                        #     logging.debug(f"RMC empfangen: {msg}")
                        #     pass # Process RMC if necessary
                        else:
                            # Message is not GGA, ignore for position data
                            logging.debug(f"Andere NMEA-Nachricht empfangen: {msg.sentence_type}")
                            return None
                        # --- Modification End ---

                    except pynmea2.ParseError as e:
                        logging.warning(f"Fehler beim Parsen der NMEA-Zeile: {e} - Zeile: '{line}'")
                        return None
                    except AttributeError as e:
                        # This might catch errors if a field is missing even after type check (less likely)
                        logging.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Nachricht: {msg}")
                        return None
            except serial.SerialException as e:
                logging.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                self._reconnect_serial()  # Versuch, die Verbindung wiederherzustellen
                return None
            except Exception as e:
                logging.error(f"Unerwarteter Fehler in get_gps_data: {e}")
                return None
        return None  # Default return if no valid data is found

    def check_assist_now(self):
        if self.assist_now_enabled and datetime.now() - self.last_assist_now_update >= timedelta(days=1):
            data = self.download_assist_now_data()
            if data is not None:
                self.send_assist_now_data(data)
                self.last_assist_now_update = datetime.now()
            else:
                print("AssistNow Offline-Daten konnten nicht heruntergeladen werden. Nächster Versuch in 2 Sekunden.")
                time.sleep(2)  # Warte 2 Sekunden bis zum nächsten Versuch
                return False
        return True

    def change_gps_mode(self, mode):
        if mode == "fake_route":
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
        elif mode == "fake_random":
            self.is_fake_gps = True
            self.route_simulator = None
        elif mode == "real":
            self.is_fake_gps = False
            self.route_simulator = None
        else:
            return False
        return True
