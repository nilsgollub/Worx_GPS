import threading
import time
import math
import random
import json

class ChaosSimulator:
    def __init__(self, geo_config, callback):
        """
        Simuliert einen Mähroboter nach dem Chaos-Prinzip:
        - Fährt geradeaus bis er auf eine Grenze trifft.
        - Dreht sich dann in einem zufälligen Winkel.
        
        :param geo_config: Dictionary mit den Grundstücksgrenzen (lat_bounds, lon_bounds)
        :param callback: Funktion, die mit dem neuen GPS-Status aufgerufen wird (als Dictionary)
        """
        self.running = False
        self.thread = None
        self.callback = callback
        
        # Grundstücksgrenzen
        self.lat_min, self.lat_max = geo_config.get("lat_bounds", (46.777500, 46.777800))
        self.lon_min, self.lon_max = geo_config.get("lon_bounds", (7.162400, 7.162750))
        
        # Startposition in der Mitte des Grundstücks
        self.current_lat = (self.lat_min + self.lat_max) / 2
        self.current_lon = (self.lon_min + self.lon_max) / 2
        
        # Startrichtung in Grad (0 = Nord, 90 = Ost, etc.)
        self.heading = random.uniform(0, 360)
        
        # Mäh-Parameter
        self.speed_ms = 0.35  # Landroid fährt ca. 35cm pro Sekunde
        self.update_interval = 1.0  # Update jede Sekunde
        
        # Erdradius für Entfernungsberechnung (Meter)
        self.R = 6371000

    def calculate_new_position(self, lat, lon, heading, distance):
        """Berechnet neue Koordinaten basierend auf aktueller Position, Richtung und Distanz"""
        angular_distance = distance / self.R
        heading_rad = math.radians(heading)
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        new_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(angular_distance) +
            math.cos(lat_rad) * math.sin(angular_distance) * math.cos(heading_rad)
        )

        new_lon_rad = lon_rad + math.atan2(
            math.sin(heading_rad) * math.sin(angular_distance) * math.cos(lat_rad),
            math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat_rad)
        )

        return math.degrees(new_lat_rad), math.degrees(new_lon_rad)

    def is_out_of_bounds(self, lat, lon):
        """Prüft ob die Koordinaten außerhalb der konfigurierten Grenzen sind"""
        return not (self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max)

    def generate_payload(self):
        """Generiert ein Payload im Format des echten Roboters ('status,...')"""
        # Format: status,fix_desc,sats,lat,lon,agps_info
        status_text = "GPS Fix (SPS)"
        sats = str(random.randint(8, 12))
        lat_str = str(round(self.current_lat, 8))
        lon_str = str(round(self.current_lon, 8))
        agps = "AGPS: On"
        
        return f"status,{status_text},{sats},{lat_str},{lon_str},{agps}"

    def simulation_loop(self):
        while self.running:
            # Berechne potentielle neue Position
            distance_to_travel = self.speed_ms * self.update_interval
            new_lat, new_lon = self.calculate_new_position(
                self.current_lat, 
                self.current_lon, 
                self.heading, 
                distance_to_travel
            )
            
            # Prüfen ob wir auf eine Grenze stoßen (Kollision / Begrenzungsdraht)
            if self.is_out_of_bounds(new_lat, new_lon):
                # Drehen (wie der echte Roboter am Kabel)
                # Normalerweise prallt er in einem flachen oder spitzen Winkel ab
                turn_angle = random.uniform(90, 180) 
                
                # Zufällig nach links oder rechts drehen
                if random.choice([True, False]):
                    self.heading = (self.heading + turn_angle) % 360
                else:
                    self.heading = (self.heading - turn_angle) % 360
                    
                # In diesem Schritt bewegen wir uns nicht, sondern drehen nur
                # (Simuliert das Stoppen, Zurücksetzen und Drehen des Roboters)
                time.sleep(self.update_interval)
                continue

            # Keine Kollision -> weiterfahren
            self.current_lat = new_lat
            self.current_lon = new_lon
            
            # An Callback senden
            try:
                self.callback(self.generate_payload())
            except Exception as e:
                print(f"[Simulator] Fehler im Callback: {e}")
                
            time.sleep(self.update_interval)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.simulation_loop, daemon=True)
            self.thread.start()
            print("[Simulator] Chaos-Simulation gestartet")

    def stop(self):
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=2)
            print("[Simulator] Chaos-Simulation gestoppt")

    def is_running(self):
        return self.running
