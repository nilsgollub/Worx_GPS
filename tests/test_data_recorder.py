import unittest
import threading
from unittest.mock import patch, MagicMock
import paho.mqtt.client as mqtt
from data_recorder import DataRecorder
import os
import csv
from config import MQTT_CONFIG, GEO_CONFIG
import time
import serial


class TestDataRecorder(unittest.TestCase):

    def setUp(self):
        self.mock_mqtt_client = MagicMock()
        self.mock_mqtt_client.publish = MagicMock()
        self.data_recorder = DataRecorder(
            serial_port="/dev/ttyFAKE",
            baud_rate=9600,
            mqtt_broker=MQTT_CONFIG["host"],
            mqtt_port=MQTT_CONFIG["port"]
        )
        self.data_recorder.mqtt_client = self.mock_mqtt_client
        self.data_recorder.start_recording = MagicMock()  # Methode Moken
        self.data_recorder.read_gps_data = MagicMock()
        self.data_recorder.generate_fake_data = MagicMock()
        self.data_recorder.send_data_mqtt = MagicMock()
        # Erstellen einer temporären CSV-Datei für Testzwecke
        self.temp_csv_file = "temp_data.csv"
        self.data_recorder.data_file = self.temp_csv_file
        with open(self.temp_csv_file, 'w', newline='') as csvfile:
            fieldnames = ['latitude', 'longitude', 'timestamp', 'satellites', "state"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {'latitude': 46.811819, 'longitude': 7.132838, 'timestamp': 1672531200.0, 'satellites': 10,
                 "state": "moving"})
            writer.writerow(
                {'latitude': 46.811919, 'longitude': 7.132938, 'timestamp': 1672531201.0, 'satellites': 10,
                 "state": "moving"})

    def tearDown(self):
        # Aufräumen nach den Tests
        if os.path.exists(self.temp_csv_file):
            os.remove(self.temp_csv_file)

    @patch('data_recorder.serial.Serial')
    def test_read_gps_data(self, mock_serial):
        # Mocken der seriellen Verbindung
        mock_instance = mock_serial.return_value
        mock_instance.readline.return_value = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,"
        # Aufrufen der zu testenden Funktion
        self.data_recorder.is_recording = True
        self.data_recorder.read_gps_data()
        # Überprüfungen
        self.assertTrue(mock_instance.readline.called)
        self.assertIsNotNone(self.data_recorder.gps_coordinates)
        # Beende Aufnahme
        self.data_recorder.is_recording = False

    def test_generate_fake_data(self):
        # Aktivieren von Fake-Daten
        GEO_CONFIG["is_fake"] = True
        self.data_recorder.is_fake = True
        # Aufrufen der Funktion zum Generieren von Fake-Daten
        self.data_recorder.is_recording = True
        # Starte den Fake Daten Stream
        threading.Thread(target=self.data_recorder.generate_fake_data, daemon=True).start()
        time.sleep(1)
        # Überprüfen, ob GPS-Koordinaten generiert wurden
        self.assertIsNotNone(self.data_recorder.gps_coordinates)
        # Beende Aufnahme
        self.data_recorder.is_recording = False

    def test_save_data_to_csv(self):
        # Fügen Testdaten hinzu
        test_data = {
            'latitude': 46.811819,
            'longitude': 7.132838,
            'timestamp': 1672531200.0,  # Korrektur: Float
            'satellites': 10,
            'state': "test"
        }
        self.data_recorder.gps_data.append(test_data)
        # Test
        self.data_recorder.save_data_to_csv()
        # Überprüfen, ob die Datei existiert
        self.assertTrue(os.path.exists(self.temp_csv_file))

    def test_on_connect(self):
        self.data_recorder.on_connect(self.mock_mqtt_client, None, None, 0)
        self.mock_mqtt_client.subscribe.assert_called()

    def test_on_message(self):
        # Starte den Recorder
        self.data_recorder.start_recording()
        # Sende die Start Nachricht
        message = mqtt.MQTTMessage()  # Korrektur: Erstelle ein MQTTMessage Objekt
        message.topic = "worx/start"
        message.payload = b"start"
        self.data_recorder.on_message(self.mock_mqtt_client, None, message)
        # Teste ob der Recorder läuft
        self.assertTrue(self.data_recorder.is_recording)
        # Sende die Stop Nachricht
        message = mqtt.MQTTMessage()  # Korrektur: Erstelle ein MQTTMessage Objekt
        message.topic = "worx/stop"
        message.payload = b"stop"
        self.data_recorder.on_message(self.mock_mqtt_client, None, message)
        # Teste ob der Recorder gestoppt ist
        self.assertFalse(self.data_recorder.is_recording)

    @patch('data_sender.DataSender.send_data')
    def test_send_data_mqtt(self, mock_send_data):
        self.data_recorder.send_data_mqtt()
        mock_send_data.assert_called_once()
        self.assertTrue(os.path.exists(self.temp_csv_file))

    def test_clear_data(self):
        self.data_recorder.clear_data()
        self.assertFalse(os.path.exists(self.temp_csv_file))
