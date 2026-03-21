import threading
import time
import math
import random
import logging

logger = logging.getLogger(__name__)


class ChaosSimulator:
    def __init__(self, geo_config, mqtt_service, data_manager=None):
        """
        Simuliert einen Mähroboter nach dem Chaos-Prinzip.
        Sendet alle MQTT-Nachrichten wie der echte Recorder (Worx_GPS_Rec.py):
        - "recording started" / "recording stopped" auf worx/status
        - GPS-Status periodisch auf worx/status
        - "problem,lat,lon" bei simuliertem Stillstand auf worx/status
        - CSV-Sessiondaten auf worx/gps bei Stop
        
        :param geo_config: Dictionary mit Grundstücksgrenzen (lat_bounds, lon_bounds)
        :param mqtt_service: MqttService-Instanz zum Publizieren von MQTT-Nachrichten
        :param data_manager: Optionaler DataManager zum Laden der Geofences
        """
        self.running = False
        self.thread = None
        self.mqtt_service = mqtt_service
        self.data_manager = data_manager
        
        # Grundstücksgrenzen (Fallback auf config)
        self.lat_min, self.lat_max = geo_config.get("lat_bounds", (46.777500, 46.777800))
        self.lon_min, self.lon_max = geo_config.get("lon_bounds", (7.162400, 7.162750))
        
        # Startposition in der Mitte des Grundstücks
        self.current_lat = (self.lat_min + self.lat_max) / 2
        self.current_lon = (self.lon_min + self.lon_max) / 2
        
        # Startrichtung in Grad (0 = Nord, 90 = Ost, etc.)
        self.heading = random.uniform(0, 360)
        
        # Mäh-Parameter
        self.base_speed = 1.5  # Basis-Geschwindigkeit
        self.speed_ms = self.base_speed 
        self.update_interval = 1.0  
        
        # Erdradius für Entfernungsberechnung (Meter)
        self.R = 6371000
        
        # Session-Datenpuffer (wie DataRecorder)
        self.gps_buffer = []
        
        # Problem-Simulation
        self._stall_counter = 0
        self._stall_threshold = random.randint(120, 240)  # Seltener Probleme (alle 2-4 Min)
        self._last_problem_time = 0
        self._problem_cooldown = 120  # Längere Pause zwischen Problemen
        
        self.start_time = 0

    def _publish_status(self, payload):
        """Publiziert eine Nachricht auf dem Status-Topic (worx/status)."""
        handler = self.mqtt_service.handler
        handler.publish_message(handler.topic_status, payload)

    def _publish_gps_data(self, payload):
        """Publiziert eine Nachricht auf dem GPS-Topic (worx/gps)."""
        handler = self.mqtt_service.handler
        handler.publish_message(handler.topic_gps, payload)

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
        """Prüft ob die Koordinaten außerhalb der Geofences oder forbidden_areas sind."""
        # 1. Grober Check gegen Rechteck (Performance)
        if not (self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max):
            return True
            
        # 2. Feiner Check gegen Polygone
        if self.data_manager:
            from utils import is_point_in_polygon
            geofences = self.data_manager.get_geofences()
            mow_areas = [f['coordinates'] for f in geofences if f.get('type') == 'mow_area']
            forbidden_areas = [f['coordinates'] for f in geofences if f.get('type') == 'forbidden_area']
            
            if mow_areas or forbidden_areas:
                # Prüfe auf erlaubte Zonen
                if mow_areas:
                    allowed = False
                    for area in mow_areas:
                        if is_point_in_polygon(lat, lon, area):
                            allowed = True
                            break
                    if not allowed:
                        return True
                
                # Prüfe auf Verbotszonen
                for area in forbidden_areas:
                    if is_point_in_polygon(lat, lon, area):
                        return True
        
        return False

    def _generate_status_payload(self):
        """Generiert ein Payload im Format des echten Roboters ('status,...')"""
        status_text = "Mowing (Simulated)"
        sats = str(random.randint(10, 18)) # Mehr Satelliten für Stabilität
        lat_str = str(round(self.current_lat, 8))
        lon_str = str(round(self.current_lon, 8))
        agps = "AGPS: On"
        # HDOP Simulation: ca 0.9 (sehr gut)
        hdop = str(round(random.uniform(0.7, 1.1), 2))
        
        # Format: status,fix,sats,lat,lon,agps,hdop
        return f"status,{status_text},{sats},{lat_str},{lon_str},{agps},{hdop}"

    def _buffer_gps_point(self):
        """Puffert den aktuellen GPS-Punkt für die Session-Daten (inkl. HDOP)."""
        timestamp = time.time()
        sats = random.randint(12, 18)
        wifi_dbm = random.randint(-65, -40) # Besseres Wifi im Simulator
        hdop = random.uniform(0.7, 1.0)
        self.gps_buffer.append(
            f"{self.current_lat:.8f},{self.current_lon:.8f},{timestamp:.3f},{sats},{wifi_dbm},{hdop:.2f}"
        )

    def _check_simulate_problem(self):
        """Simuliert gelegentlich einen Stillstand (wie ProblemDetector)."""
        self._stall_counter += 1
        now = time.time()
        
        # Problem nur simulieren, wenn Schwellwert erreicht und Cooldown vorbei
        if self._stall_counter >= self._stall_threshold and \
           (now - self._last_problem_time) >= self._problem_cooldown:
            
            # Zufällige Problem-Art wählen
            issues = [
                f"problem,stuck,{self.current_lat:.6f},{self.current_lon:.6f}",
                f"problem,lifted,{self.current_lat:.6f},{self.current_lon:.6f}",
                f"problem,outside_wire,{self.current_lat:.6f},{self.current_lon:.6f}"
            ]
            problem_payload = random.choice(issues)
            
            logger.warning(f"[Simulator] KRITISCHES PROBLEM SIMULIERT: {problem_payload}")
            self._publish_status(problem_payload)
            
            self._last_problem_time = now
            self._stall_counter = 0
            self._stall_threshold = random.randint(120, 240)
            
            # Simuliere längeren Stillstand (10-20s) zur Fehlererkennungs-Testung
            stall_time = random.uniform(10, 20)
            for _ in range(int(stall_time)):
                if not self.running:
                    return
                # Sende weiterhin GPS Status (Mäher steht still aber GPS sendet)
                self._publish_status(self._generate_status_payload())
                time.sleep(2)
            
            # Automatische "Heilung" nach dem Stillstand
            logger.info("[Simulator] Problem behoben - Mäher setzt Arbeit fort.")
            self._publish_status("recording started")

    def _send_session_data(self):
        """Sendet die gepufferten GPS-Daten als CSV auf worx/gps."""
        if not self.gps_buffer:
            logger.info("[Simulator] Keine GPS-Daten im Puffer, sende nur End-Marker.")
            self._publish_gps_data("-1")
            return
        
        csv_data = "\n".join(self.gps_buffer)
        logger.info(f"[Simulator] Sende {len(self.gps_buffer)} GPS-Punkte als Session-Daten.")
        self._publish_gps_data(csv_data)
        self._publish_gps_data("-1")

    def simulation_loop(self):
        logger.info("[Simulator] Simulations-Loop gestartet.")
        
        while self.running:
            # Laufzeit-Check (max 10 Minuten)
            if time.time() - self.start_time > 600:
                logger.info("[Simulator] Maximale Laufzeit von 10 Min erreicht, stoppe automatisch.")
                break

            # Dynamische Geschwindigkeit: Variiert leicht um die Basis
            # Langsamer in "Kurven" (nach Kollision)
            self.speed_ms = self.base_speed * random.uniform(0.8, 1.2)

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
                # Drehung simulieren (Wenden)
                turn_angle = random.uniform(120, 210) # Worx-typisches Wenden
                if random.choice([True, False]):
                    self.heading = (self.heading + turn_angle) % 360
                else:
                    self.heading = (self.heading - turn_angle) % 360
                
                # Beim Wenden kurz anhalten / langsamer werden
                time.sleep(0.5) 
                continue

            # Keine Kollision -> weiterfahren
            self.current_lat = new_lat
            self.current_lon = new_lon
            
            # GPS-Status via MQTT senden
            try:
                self._publish_status(self._generate_status_payload())
                self._buffer_gps_point()
            except Exception as e:
                logger.error(f"[Simulator] Fehler beim Senden: {e}")

            # Gelegentlich Problem simulieren
            self._check_simulate_problem()
                
            time.sleep(self.update_interval)

        # Cleanup am Ende (Timeout oder Stop)
        self._send_session_data()
        self._publish_status("recording stopped")
        logger.info(f"[Simulator] Simulation beendet, {len(self.gps_buffer)} Punkte verarbeitet.")
        self.gps_buffer = []

    def start(self):
        """Startet die Simulation."""
        if not self.running:
            # Zufällige Startposition innerhalb der Grenzen (statt immer Mitte)
            self.current_lat = random.uniform(self.lat_min, self.lat_max)
            self.current_lon = random.uniform(self.lon_min, self.lon_max)
            # Sicherstellen, dass Startpunkt valide ist
            if self.is_out_of_bounds(self.current_lat, self.current_lon):
                self.current_lat = (self.lat_min + self.lat_max) / 2
                self.current_lon = (self.lon_min + self.lon_max) / 2

            self.heading = random.uniform(0, 360)
            self.gps_buffer = []
            self._stall_counter = 0
            
            self.running = True
            self.start_time = time.time()
            
            self._publish_status("recording started")
            logger.info("[Simulator] Turbo-Chaos-Simulation gestartet.")
            
            self.thread = threading.Thread(target=self.simulation_loop, daemon=True)
            self.thread.start()

    def stop(self):
        """Signaliert manuellen Stop."""
        if self.running:
            logger.info("[Simulator] Manueller Stop angefordert.")
            self.running = False

    def is_running(self):
        return self.running
