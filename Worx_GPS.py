# Worx_GPS.py
from mqtt_handler import MqttHandler
from heatmap_generator import HeatmapGenerator
from data_manager import DataManager
from utils import read_gps_data_from_csv_string
from config import HEATMAP_CONFIG
import time


class WorxGps:
    def __init__(self, test_mode=False):
        self.mqtt_handler = MqttHandler(test_mode)
        self.heatmap_generator = HeatmapGenerator()
        self.data_manager = DataManager()
        self.gps_data_buffer = ""
        self.maehvorgang_data = []
        self.alle_maehvorgang_data = []
        self.maehvorgang_count = 0
        self.problemzonen_data = self.data_manager.read_problemzonen_data()
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()

    def on_mqtt_message(self, msg):
        if msg.topic == self.mqtt_handler.topic_gps:
            self.handle_gps_data(msg.payload.decode())
        elif msg.topic == self.mqtt_handler.topic_status:
            self.handle_status_data(msg.payload.decode())

    def handle_gps_data(self, csv_data):
        if csv_data != "-1":  # Ende-Marker noch nicht erreicht
            self.gps_data_buffer += csv_data  # Daten zum Puffer hinzufügen
        else:
            # Ende-Marker erreicht, Daten verarbeiten
            gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            if gps_data:
                self.maehvorgang_data.append(gps_data)
                self.alle_maehvorgang_data.extend(gps_data)
                filename = self.data_manager.get_next_mow_filename()
                self.data_manager.save_gps_data(gps_data, filename)
                self.heatmap_generator.create_heatmap([gps_data], HEATMAP_CONFIG["heatmap_aktuell"], True)
                self.heatmap_generator.create_heatmap(list(self.maehvorgang_data),
                                                      HEATMAP_CONFIG["heatmap_10_maehvorgang"], False)
                self.heatmap_generator.create_heatmap([self.alle_maehvorgang_data],
                                                      HEATMAP_CONFIG["heatmap_kumuliert"], False)
                self.heatmap_generator.create_heatmap([list(self.problemzonen_data)],
                                                      HEATMAP_CONFIG["problemzonen_heatmap"], False)
            else:
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")
            self.gps_data_buffer = ""  # Puffer leeren

    def handle_status_data(self, csv_data):
        # Überprüfen, ob es sich um eine Problemmeldung handelt
        parts = csv_data.split(",")
        if len(parts) >= 3 and parts[0] == "problem":  # Mindestens 3 Teile und beginnt mit "problem"
            print("Empfangene Problemzonen-Daten:", csv_data)
            if csv_data != "problem,-1,-1":  # Ende-Marker ignorieren
                # CSV-Daten in Dictionary umwandeln (nur lat und lon)
                _, lat, lon = parts  # Ignoriere "problem"
                problem_data = {"lat": float(lat), "lon": float(lon), "timestamp": time.time()}
                self.problemzonen_data.append(problem_data)
                self.problemzonen_data = self.data_manager.remove_old_problemzonen()
                self.data_manager.save_problemzonen_data(self.problemzonen_data)
                self.heatmap_generator.create_heatmap([list(self.problemzonen_data)],
                                                      HEATMAP_CONFIG["problemzonen_heatmap"], False)
        else:
            # Statusmeldung ausgeben
            print("Empfangene Statusmeldung:", csv_data)


if __name__ == "__main__":
    worx_gps = WorxGps()
    while True:
        time.sleep(1)
