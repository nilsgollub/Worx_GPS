import paho.mqtt.client as mqtt
import json
from config import MQTT_CONFIG
import time


class DataSender:
    def __init__(self, mqtt_broker, mqtt_port):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # Korrektur: Callback API Version 2
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()
        self.mqtt_topic_gps = "worx/gps"

    def send_data(self, csv_file):
        try:
            data = self.read_csv(csv_file)
            json_data = json.dumps(data)
            self.mqtt_client.publish(self.mqtt_topic_gps, json_data)
            print("Daten erfolgreich gesendet.")
        except Exception as e:
            print(f"Fehler beim Senden der Daten: {e}")

    def read_csv(self, csv_file):
        data = []
        with open(csv_file, 'r') as f:
            lines = f.readlines()
        if len(lines) <= 1:
            print(f"Keine Daten zum senden gefunden")
            return []
        for line in lines[1:]:
            # Skip the first line
            values = line.split(",")
            if len(values) >= 5:
                lat, lon, timestamp, satellites, state = values
                try:
                    data.append({
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "timestamp": float(timestamp),
                        "satellites": int(float(satellites)),  # Korrektur: Cast zu int
                        "state": state.strip(),
                    })
                except Exception as e:
                    print(f"Fehler beim konvertieren der Werte in Zeile {line}")
        return data

    def close(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        import paho.mqtt.client as mqtt


import json
from config import MQTT_CONFIG
import time


class DataSender:
    def __init__(self, mqtt_broker, mqtt_port):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # Korrektur: Callback API Version 2
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()
        self.mqtt_topic_gps = "worx/gps"

    def send_data(self, csv_file):
        try:
            data = self.read_csv(csv_file)
            json_data = json.dumps(data)
            self.mqtt_client.publish(self.mqtt_topic_gps, json_data)
            print("Daten erfolgreich gesendet.")
        except Exception as e:
            print(f"Fehler beim Senden der Daten: {e}")

    def read_csv(self, csv_file):
        data = []
        with open(csv_file, 'r') as f:
            lines = f.readlines()
        if len(lines) <= 1:
            print(f"Keine Daten zum senden gefunden")
            return []
        for line in lines[1:]:
            # Skip the first line
            values = line.split(",")
            if len(values) >= 5:
                lat, lon, timestamp, satellites, state = values
                try:
                    data.append({
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "timestamp": float(timestamp),
                        "satellites": int(float(satellites)),  # Korrektur: Cast zu int
                        "state": state.strip(),
                    })
                except Exception as e:
                    print(f"Fehler beim konvertieren der Werte in Zeile {line}")
        return data

    def close(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
