import unittest
import time
import os
import shutil
from unittest.mock import patch, MagicMock
from data_recorder import DataRecorder
from data_sender import DataSender
from heatmap_generator import HeatmapGenerator
from gps_handler import GpsHandler
from config import MQTT_CONFIG, GEO_CONFIG, REC_CONFIG, PROBLEM_CONFIG
import csv
import paho.mqtt.client as mqtt
import json


class TestIntegration(unittest.TestCase):

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

    def tearDown(self):
        # Aufräumen nach den Tests
        if os.path.exists(self.data_recorder.data_file):
            os.remove(self.data_recorder.data_file)
        if os.path.exists(PROBLEM_CONFIG["problem_json"]):
            os.remove(PROBLEM_CONFIG["problem_json"])

    def test_full_integration_fake(self):
        GEO_CONFIG["is_fake"] = True  # Aktiviere Fake Daten
        # Starte Datenerfassung
        self.data_recorder.start_recording()
        # Warte für Fake Daten Generierung
        time.sleep(1)
        # Stoppe Datenerfassung
        self.data_recorder.stop_recording()
        # Teste ob eine Datei erstellt wurde
        self.assertTrue(os.path.exists(self.data_recorder.data_file))
        # Setze is_fake zurück.
        GEO_CONFIG["is_fake"] = False

    def test_full_integration_mqtt(self):
        # Starte den DataRecorder mit der Run Funktion
        self.data_recorder.run()
        # Erstelle eine Message
        message = mqtt.MQTTMessage()  # Korrektur: Erstelle ein MQTTMessage Objekt
        message.topic = "worx/start"
        message.payload = b"start"
        # Teste ob die Message gesendet werden kann.
        self.data_recorder.on_message(self.mock_mqtt_client, None, message)
        # Warte für die Aufnahme.
        time.sleep(1)
        # Erstelle eine Message
        message = mqtt.MQTTMessage()  # Korrektur: Erstelle ein MQTTMessage Objekt
        message.topic = "worx/stop"
        message.payload = b"stop"
        # Sende die Stopp Nachricht
        self.data_recorder.on_message(self.mock_mqtt_client, None, message)
        # Teste ob eine Datei erstellt wurde
        self.assertTrue(os.path.exists(self.data_recorder.data_file))
