import threading
import time
import math
import random
import logging

logger = logging.getLogger(__name__)


class ChaosSimulator:
    def __init__(self, geo_config, mqtt_service):
        """
        Simuliert einen Mähroboter nach dem Chaos-Prinzip.
        Sendet alle MQTT-Nachrichten wie der echte Recorder (Worx_GPS_Rec.py):
        - "recording started" / "recording stopped" auf worx/status
        - GPS-Status periodisch auf worx/status
        - "problem,lat,lon" bei simuliertem Stillstand auf worx/status
        - CSV-Sessiondaten auf worx/gps bei Stop
        
        :param geo_config: Dictionary mit Grundstücksgrenzen (lat_bounds, lon_bounds)
        :param mqtt_service: MqttService-Instanz zum Publizieren von MQTT-Nachrichten
        """
        self.running = False
        self.thread = None
        self.mqtt_service = mqtt_service
        
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
        
        # Session-Datenpuffer (wie DataRecorder)
        self.gps_buffer = []
        
        # Problem-Simulation: Stillstand-Erkennung
        self._stall_counter = 0
        self._stall_threshold = random.randint(45, 120)  # Nach 45-120s ein Problem simulieren
        self._last_problem_time = 0
        self._problem_cooldown = 60  # Min. 60s zwischen Problemen

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
        """Prüft ob die Koordinaten außerhalb der konfigurierten Grenzen sind"""
        return not (self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max)

    def _generate_status_payload(self):
        """Generiert ein Payload im Format des echten Roboters ('status,...')"""
        status_text = "GPS Fix (SPS)"
        sats = str(random.randint(8, 12))
        lat_str = str(round(self.current_lat, 8))
        lon_str = str(round(self.current_lon, 8))
        agps = "AGPS: On (Sim)"
        
        return f"status,{status_text},{sats},{lat_str},{lon_str},{agps}"

    def _buffer_gps_point(self):
        """Puffert den aktuellen GPS-Punkt für die Session-Daten (wie DataRecorder)."""
        timestamp = time.time()
        sats = random.randint(8, 12)
        wifi_dbm = random.randint(-75, -45)
        self.gps_buffer.append(
            f"{self.current_lat:.8f},{self.current_lon:.8f},{timestamp:.3f},{sats},{wifi_dbm}"
        )

    def _check_simulate_problem(self):
        """Simuliert gelegentlich einen Stillstand (wie ProblemDetector)."""
        self._stall_counter += 1
        now = time.time()
        
        if self._stall_counter >= self._stall_threshold and \
           (now - self._last_problem_time) >= self._problem_cooldown:
            # Problem melden
            problem_payload = f"problem,{self.current_lat:.6f},{self.current_lon:.6f}"
            logger.info(f"[Simulator] Problem simuliert: {problem_payload}")
            self._publish_status(problem_payload)
            
            self._last_problem_time = now
            self._stall_counter = 0
            self._stall_threshold = random.randint(45, 120)  # Neuer Schwellwert
            
            # Simuliere kurzen Stillstand (3-5s)
            stall_time = random.uniform(3, 5)
            for _ in range(int(stall_time)):
                if not self.running:
                    return
                time.sleep(1)

    def _send_session_data(self):
        """Sendet die gepufferten GPS-Daten als CSV auf worx/gps (wie DataRecorder.send_buffer_data)."""
        if not self.gps_buffer:
            logger.info("[Simulator] Kein GPS-Daten im Puffer, sende nur End-Marker.")
            self._publish_gps_data("-1")
            return
        
        csv_data = "\n".join(self.gps_buffer)
        logger.info(f"[Simulator] Sende {len(self.gps_buffer)} GPS-Punkte als Session-Daten.")
        self._publish_gps_data(csv_data)
        self._publish_gps_data("-1")

    def simulation_loop(self):
        logger.info("[Simulator] Simulations-Loop gestartet.")
        
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
                turn_angle = random.uniform(90, 180) 
                
                if random.choice([True, False]):
                    self.heading = (self.heading + turn_angle) % 360
                else:
                    self.heading = (self.heading - turn_angle) % 360
                    
                time.sleep(self.update_interval)
                continue

            # Keine Kollision -> weiterfahren
            self.current_lat = new_lat
            self.current_lon = new_lon
            
            # GPS-Status via MQTT senden (wie der echte Recorder)
            try:
                self._publish_status(self._generate_status_payload())
                self._buffer_gps_point()
            except Exception as e:
                logger.error(f"[Simulator] Fehler beim Senden: {e}")

            # Gelegentlich Problem simulieren
            self._check_simulate_problem()
                
            time.sleep(self.update_interval)

    def start(self):
        """Startet die Simulation und sendet 'recording started' via MQTT."""
        if not self.running:
            # Position zurücksetzen
            self.current_lat = (self.lat_min + self.lat_max) / 2
            self.current_lon = (self.lon_min + self.lon_max) / 2
            self.heading = random.uniform(0, 360)
            self.gps_buffer = []
            self._stall_counter = 0
            self._stall_threshold = random.randint(45, 120)
            
            self.running = True
            
            # "recording started" senden (wie Worx_GPS_Rec.start_recording)
            self._publish_status("recording started")
            logger.info("[Simulator] Chaos-Simulation gestartet, 'recording started' gesendet.")
            
            self.thread = threading.Thread(target=self.simulation_loop, daemon=True)
            self.thread.start()

    def stop(self):
        """Stoppt die Simulation, sendet Session-Daten und 'recording stopped' via MQTT."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=2)
            
            # Session-Daten senden (wie Worx_GPS_Rec.stop_recording → DataRecorder.send_buffer_data)
            self._send_session_data()
            
            # "recording stopped" senden (wie Worx_GPS_Rec.stop_recording)
            self._publish_status("recording stopped")
            logger.info(f"[Simulator] Chaos-Simulation gestoppt, {len(self.gps_buffer)} Punkte gesendet.")
            self.gps_buffer = []

    def is_running(self):
        return self.running
