import unittest
from unittest.mock import patch, MagicMock
from mqtt_handler import MqttHandler
from config import MQTT_CONFIG, REC_CONFIG


class TestMqttHandler(unittest.TestCase):

    @patch('mqtt_handler.mqtt.Client')  # Korrektur: Die Funktion wird gemockt.
    def setUp(self, mock_mqtt_client):
        self.mqtt_handler = MqttHandler()
        self.mqtt_handler.mqtt_client = mock_mqtt_client.return_value

    def test_connect(self):
        self.mqtt_handler.connect()
        self.mqtt_handler.mqtt_client.connect.assert_called_once()
