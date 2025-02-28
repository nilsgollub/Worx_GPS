# data_recorder.py
from config import REC_CONFIG
import time


class DataRecorder:
    def __init__(self, mqtt_handler):
        self.gps_data_buffer = ""
        self.mqtt_handler = mqtt_handler

    def add_gps_data(self, gps_data):
        """Fügt GPS-Daten zum Puffer hinzu."""
        self.gps_data_buffer += f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}\n"

    def send_buffer_data(self):
        """Sendet die im Puffer gespeicherten GPS-Daten in Paketen und leert den Puffer."""
        lines = self.gps_data_buffer.splitlines()
        for i in range(0, len(lines), REC_CONFIG["gps_message_count"]):  # 100 Zeilen pro Paket
            packet = '\n'.join(lines[i:i + REC_CONFIG["gps_message_count"]])
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_gps, packet)
            time.sleep(0.1)  # Kurze Verzögerung
        self.mqtt_handler.publish_message(self.mqtt_handler.topic_gps, "-1")  # Ende-Marker
        self.clear_buffer()

    def clear_buffer(self):
        """Leert den Puffer."""
        self.gps_data_buffer = ""
