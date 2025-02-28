# gps_handler.py
import random
import time
import serial
import pynmea2
import requests
import platform
from datetime import datetime, timedelta
from config import GEO_CONFIG, ASSIST_NOW_CONFIG, REC_CONFIG
from pyubx2 import UBXMessage
import math


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
        if self.is_fake_gps:  # Fake-GPS-Modus
            # Route Simulation
            if self.route_simulator:
                latitude, longitude = self.route_simulator.move()
                # Bei erreichen der Grenze neue Richtung wählen
                if not self.is_inside_boundaries(latitude, longitude):
                    self.route_simulator.change_direction(random.uniform(120, 240))  # Zufällige Richtungsänderung
                    latitude, longitude = self.route_simulator.move()
            else:  # zufällige punkte
                latitude = random.uniform(self.lat_bounds[0], self.lat_bounds[1])
                longitude = random.uniform(self.lon_bounds[0], self.lon_bounds[1])
            timestamp = time.time()
            satellites = random.randint(4, 12)
            return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites}
        else:  # Linux oder Windows (NMEA-Kommunikation)
            try:
                line = self.ser_gps.readline().decode('latin-1').strip()
                if line:  # prüfe ob eine Zeile vorhanden ist
                    if line.startswith('$GP'):  # Überprüfen, ob es eine GP-Nachricht ist
                        msg = pynmea2.parse(line)
                        if msg.gps_qual > 0:  # GPS-Fix vorhanden
                            latitude = msg.latitude
                            longitude = msg.longitude
                            timestamp = msg.timestamp
                            satellites = msg.num_sats
                            return {"lat": latitude, "lon": longitude, "timestamp": timestamp, "satellites": satellites}
                        else:
                            print("Kein GPS-Fix vorhanden.")
                            return None
                    else:
                        print("Ungültige NMEA-Nachricht empfangen:", line)
                        return None
                else:
                    print("Keine Daten vom GPS-Modul empfangen.")
                    return None
            except (serial.SerialException, ValueError, pynmea2.ParseError) as e:
                print(f"Fehler beim Abrufen der GPS-Daten: {e}")
                return None

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
