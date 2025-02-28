# problem_detection.py
import time
from collections import deque


class ProblemDetector:
    def __init__(self, mqtt_handler, threshold_time=30):
        self.mqtt_handler = mqtt_handler
        self.threshold_time = threshold_time  # Zeit in Sekunden, wie lange der Worx an einer Stelle stehen darf
        self.position_history = deque(maxlen=10)  # Letzte 10 Positionen speichern
        self.last_problem_time = 0  # Zeit des letzten Problems

    def add_position(self, gps_data):
        """Fügt eine neue Position zur Historie hinzu und prüft auf Probleme."""
        if not gps_data:
            return  # Keine Daten vorhanden
        self.position_history.append((gps_data["lat"], gps_data["lon"], gps_data["timestamp"]))
        self.check_for_problem()

    def check_for_problem(self):
        """Überprüft, ob ein Problem vorliegt (Worx steht zu lange an einer Stelle)."""
        if len(self.position_history) < 5:
            return  # Noch nicht genug Positionen vorhanden

        # Überprüfen, ob die letzten Positionen nahe beieinander liegen
        (last_lat, last_lon, last_timestamp) = self.position_history[-1]
        (first_lat, first_lon, first_timestamp) = self.position_history[0]

        # Zeitdifferenz berechnen
        time_diff = last_timestamp - first_timestamp
        # Positionsdifferenz berechnen
        lat_diff = abs(last_lat - first_lat)
        lon_diff = abs(last_lon - first_lon)

        # Problem erkennen: Lange an gleicher Stelle
        if time_diff >= self.threshold_time and lat_diff < 0.00001 and lon_diff < 0.00001:
            current_time = time.time()
            if current_time - self.last_problem_time >= 60:  # Sperre von 60 Sekunden
                self.last_problem_time = current_time
                self.report_problem(self.position_history[-1])

    def report_problem(self, problem_position):
        """Meldet ein Problem an die Worx_GPS_Rec.py."""
        print("Problem erkannt!")
        self.mqtt_handler.publish_message(self.mqtt_handler.topic_control, "problem")
