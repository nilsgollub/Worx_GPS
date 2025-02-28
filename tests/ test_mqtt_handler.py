import unittest
from unittest.mock import patch, MagicMock
from mqtt_handler import MqttHandler
from config import MQTT_CONFIG


class TestMqttHandler(unittest.TestCase):
    @patch('mqtt_handler.mqtt.Client')
    def setUp(self, MockClient):
        # Vor jedem Test
        self.mock_client = MagicMock()
        MockClient.return_value = self.mock_client
        self.mqtt_handler = MqttHandler()

    def test_connect(self):
        self.mqtt_handler.connect()
        self.mock_client.connect.assert_called_once_with(MQTT_CONFIG["broker"], MQTT_CONFIG["port"])

    def test_publish_message_connected(self):
        self.mqtt_handler.is_connected = True
        self.mqtt_handler.publish_message("test_topic", "test_message")
        self.mock_client.publish.assert_called_once_with("test_topic", "test_message")

    def test_publish_message_not_connected(self):
        self.mqtt_handler.is_connected = False
        self.mqtt_handler.publish_message("test_topic", "test_message")
        self.mock_client.publish.assert_not_called()

    def test_disconnect(self):
        self.mqtt_handler.disconnect()
        self.mock_client.loop_stop.assert_called_once()
        self.mock_client.disconnect.assert_called_once()

    def test_on_connect_success(self):
        self.mqtt_handler.on_connect(self.mock_client, None, None, 0)
        self.assertTrue(self.mqtt_handler.is_connected)
        self.mock_client.subscribe.assert_any_call(self.mqtt_handler.topic_control)
        self.mock_client.subscribe.assert_any_call(self.mqtt_handler.topic_gps)
        self.mock_client.subscribe.assert_any_call(self.mqtt_handler.topic_status)

    def test_on_connect_failure(self):
        self.mqtt_handler.on_connect(self.mock_client, None, None, 1)  # Nicht-Null-Rückgabecode
        self.assertFalse(self.mqtt_handler.is_connected)
