import serial
import time
import pynmea2
import random
from config import GEO_CONFIG, REC_CONFIG, MQTT_CONFIG
import os
from pathlib import Path
import datetime
import threading
import csv
import sys
import paho.mqtt.client as mqtt
from data_sender import DataSender


class DataRecorder:
    def __init__(self, serial_port, baud_rate, mqtt_broker, mqtt_port):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.gps_data = []
        self.is_recording = False
        self.is_fake = False
        self.gps_coordinates = None
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.V2)  # Korrektur: Callback API Version 2
        self.current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.data_file = f"gps_data_{self.current_datetime}.csv"
        self.data_sender = DataSender(self.mqtt_broker, self.mqtt_port)

    def start_recording(self):
        self.is_recording = True
        if self.is_fake:
            self.generate_fake_data()
        else:
            self.read_gps_data()

    def stop_recording(self):
        self.is_recording = False

    def read_gps_data(self):
        try:
            with serial.Serial(self.serial_port, self.baud_rate, timeout=1) as ser:
                print(f"Verbindung mit GPS Modul auf {self.serial_port} hergestellt.")
                while self.is_recording:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line.startswith('$'):
                        try:
                            msg = pynmea2.parse(line)
                            if isinstance(msg, pynmea2.GGA):
                                if msg.gps_qual != 0:
                                    self.gps_coordinates = {
                                        'lat': msg.latitude,
                                        'lon': msg.longitude,
                                        'timestamp': time.time(),
                                        'satellites': msg.num_sats
                                    }
                                    self.process_gps_data("moving")
                        except pynmea2.ParseError as e:
                            print(f"Fehler beim Parsen: {e}")
        except serial.SerialException as e:
            print(f"Fehler bei der seriellen Verbindung: {e}")

    def generate_fake_data(self):
        print("Generiere Fake Daten")
        while self.is_recording:
            if GEO_CONFIG["fake_gps_range"]:
                lat_range, lon_range = GEO_CONFIG["fake_gps_range"]
                self.gps_coordinates = {
                    'lat': random.uniform(*lat_range),
                    'lon': random.uniform(*lon_range),
                    'timestamp': time.time(),
                    'satellites': random.randint(4, 12)
                }
                self.process_gps_data("moving")
            time.sleep(2)

    def process_gps_data(self, state):
        if self.gps_coordinates:
            try:
                self.gps_data.append({"latitude": self.gps_coordinates['lat'],
                                      "longitude": self.gps_coordinates['lon'],
                                      "timestamp": self.gps_coordinates['timestamp'],
                                      "satellites": self.gps_coordinates['satellites'],
                                      "state": state})
            except Exception as e:
                print(f"Fehler beim verarbeiten der Daten {e}")
            if len(self.gps_data) >= GEO_CONFIG["save_interval"]:
                self.save_data_to_csv()

    def save_data_to_csv(self):
        try:
            with open(self.data_file, 'a', newline='') as csvfile:
                fieldnames = ['latitude', 'longitude', 'timestamp', 'satellites', "state"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if csvfile.tell() == 0:
                    writer.writeheader()
                for data in self.gps_data:
                    if type(data["timestamp"]) == float or type(
                            data["timestamp"]) == int:  # Korrektur: Nur Float und Int Werte schreiben.
                        writer.writerow(data)
                    else:
                        print(f"Fehler: Ungültige Werte in Zeile: {data}")
                print("GPS Daten geschrieben")
            self.gps_data = []
        except Exception as e:
            print(f"Fehler beim schreiben der Daten: {e}")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Verbunden mit MQTT Broker mit Result Code {rc}")
        self.mqtt_client.subscribe("worx/start")
        self.mqtt_client.subscribe("worx/stop")

    def on_message(self, client, userdata, msg):
        print(f"MQTT Nachricht empfangen: {msg.topic} {str(msg.payload.decode())}")
        if msg.topic == "worx/start":
            self.start_recording()
        elif msg.topic == "worx/stop":
            self.stop_recording()
            self.send_data_mqtt()
            self.clear_data()

    def send_data_mqtt(self):
        self.save_data_to_csv()
        self.data_sender.send_data(self.data_file)

    def clear_data(self):
        if os.path.exists(self.data_file):
            os.remove(self.data_file)

    def run(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()

        # Hier wird entschieden ob Fake Daten verwendet werden sollen.
        if GEO_CONFIG["is_fake"]:
            self.is_fake = True
        else:
            self.is_fake = False
        try:
            if self.is_fake:
                print("Starte Fake Datenerfassung")
                self.start_recording()
                while self.is_recording:  # Korrektur: Endlosschleife anpassen
                    time.sleep(1)
            else:
                print("Starte GPS Datenerfassung")
                self.start_recording()
                while self.is_recording:  # Korrektur: Endlosschleife anpassen
                    time.sleep(1)
        except KeyboardInterrupt:
            print("Programm beendet.")
        finally:
            self.mqtt_client.disconnect()
            self.data_sender.close()


if __name__ == "__main__":
    from config import MQTT_CONFIG, REC_CONFIG

    serial_port = REC_CONFIG["serial_port"]
    baud_rate = REC_CONFIG["baudrate"]
    mqtt_broker = MQTT_CONFIG["host"]
    mqtt_port = MQTT_CONFIG["port"]
    # Erstelle ein DataRecorder Objekt.
    recorder = DataRecorder(serial_port, baud_rate, mqtt_broker, mqtt_port)
    recorder.run()
    import serial
import time
import pynmea2
import random
from config import GEO_CONFIG, REC_CONFIG, MQTT_CONFIG
import os
from pathlib import Path
import datetime
import threading
import csv
import sys
import paho.mqtt.client as mqtt
from data_sender import DataSender


class DataRecorder:
    def __init__(self, serial_port, baud_rate, mqtt_broker, mqtt_port):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.gps_data = []
        self.is_recording = False
        self.is_fake = False
        self.gps_coordinates = None
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.V2)  # Korrektur: Callback API Version 2
        self.current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.data_file = f"gps_data_{self.current_datetime}.csv"
        self.data_sender = DataSender(self.mqtt_broker, self.mqtt_port)

    def start_recording(self):
        self.is_recording = True
        if self.is_fake:
            self.generate_fake_data()
        else:
            self.read_gps_data()

    def stop_recording(self):
        self.is_recording = False

    def read_gps_data(self):
        try:
            with serial.Serial(self.serial_port, self.baud_rate, timeout=1) as ser:
                print(f"Verbindung mit GPS Modul auf {self.serial_port} hergestellt.")
                while self.is_recording:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line.startswith('$'):
                        try:
                            msg = pynmea2.parse(line)
                            if isinstance(msg, pynmea2.GGA):
                                if msg.gps_qual != 0:
                                    self.gps_coordinates = {
                                        'lat': msg.latitude,
                                        'lon': msg.longitude,
                                        'timestamp': time.time(),
                                        'satellites': msg.num_sats
                                    }
                                    self.process_gps_data("moving")
                        except pynmea2.ParseError as e:
                            print(f"Fehler beim Parsen: {e}")
        except serial.SerialException as e:
            print(f"Fehler bei der seriellen Verbindung: {e}")

    def generate_fake_data(self):
        print("Generiere Fake Daten")
        while self.is_recording:
            if GEO_CONFIG["fake_gps_range"]:
                lat_range, lon_range = GEO_CONFIG["fake_gps_range"]
                self.gps_coordinates = {
                    'lat': random.uniform(*lat_range),
                    'lon': random.uniform(*lon_range),
                    'timestamp': time.time(),
                    'satellites': random.randint(4, 12)
                }
                self.process_gps_data("moving")
            time.sleep(2)

    def process_gps_data(self, state):
        if self.gps_coordinates:
            try:
                self.gps_data.append({"latitude": self.gps_coordinates['lat'],
                                      "longitude": self.gps_coordinates['lon'],
                                      "timestamp": self.gps_coordinates['timestamp'],
                                      "satellites": self.gps_coordinates['satellites'],
                                      "state": state})
            except Exception as e:
                print(f"Fehler beim verarbeiten der Daten {e}")
            if len(self.gps_data) >= GEO_CONFIG["save_interval"]:
                self.save_data_to_csv()

    def save_data_to_csv(self):
        try:
            with open(self.data_file, 'a', newline='') as csvfile:
                fieldnames = ['latitude', 'longitude', 'timestamp', 'satellites', "state"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if csvfile.tell() == 0:
                    writer.writeheader()
                for data in self.gps_data:
                    if type(data["timestamp"]) == float or type(
                            data["timestamp"]) == int:  # Korrektur: Nur Float und Int Werte schreiben.
                        writer.writerow(data)
                    else:
                        print(f"Fehler: Ungültige Werte in Zeile: {data}")
                print("GPS Daten geschrieben")
            self.gps_data = []
        except Exception as e:
            print(f"Fehler beim schreiben der Daten: {e}")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Verbunden mit MQTT Broker mit Result Code {rc}")
        self.mqtt_client.subscribe("worx/start")
        self.mqtt_client.subscribe("worx/stop")

    def on_message(self, client, userdata, msg):
        print(f"MQTT Nachricht empfangen: {msg.topic} {str(msg.payload.decode())}")
        if msg.topic == "worx/start":
            self.start_recording()
        elif msg.topic == "worx/stop":
            self.stop_recording()
            self.send_data_mqtt()
            self.clear_data()

    def send_data_mqtt(self):
        self.save_data_to_csv()
        self.data_sender.send_data(self.data_file)

    def clear_data(self):
        if os.path.exists(self.data_file):
            os.remove(self.data_file)

    def run(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()

        # Hier wird entschieden ob Fake Daten verwendet werden sollen.
        if GEO_CONFIG["is_fake"]:
            self.is_fake = True
        else:
            self.is_fake = False
        try:
            if self.is_fake:
                print("Starte Fake Datenerfassung")
                self.start_recording()
                while self.is_recording:  # Korrektur: Endlosschleife anpassen
                    time.sleep(1)
            else:
                print("Starte GPS Datenerfassung")
                self.start_recording()
                while self.is_recording:  # Korrektur: Endlosschleife anpassen
                    time.sleep(1)
        except KeyboardInterrupt:
            print("Programm beendet.")
        finally:
            self.mqtt_client.disconnect()
            self.data_sender.close()


if __name__ == "__main__":
    from config import MQTT_CONFIG, REC_CONFIG

    serial_port = REC_CONFIG["serial_port"]
    baud_rate = REC_CONFIG["baudrate"]
    mqtt_broker = MQTT_CONFIG["host"]
    mqtt_port = MQTT_CONFIG["port"]
    # Erstelle ein DataRecorder Objekt.
    recorder = DataRecorder(serial_port, baud_rate, mqtt_broker, mqtt_port)
    recorder.run()
