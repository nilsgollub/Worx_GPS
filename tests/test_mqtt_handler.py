# tests/test_mqtt_handler.py
import unittest
from unittest.mock import patch, MagicMock, ANY
import paho.mqtt.client as paho_mqtt_client # Importiere das Originalmodul
from mqtt_handler import MqttHandler
from config import MQTT_CONFIG # Wird für Standardwerte benötigt

# Mock-Konfiguration für Tests
MOCK_CONFIG_REAL = {
    "host": "mqtt.real.com",
    "port": 1883,
    "user": "user_real",
    "password": "pw_real",
    "topic_control": "worx/control",
    "topic_gps": "worx/gps",
    "topic_status": "worx/status",
}

MOCK_CONFIG_TEST = {
    "host_lokal": "localhost",
    "port_lokal": 1884, # Anderer Port für Test
    "user_local": "user_test",
    "password_local": "pw_test",
    "topic_control": "test/worx/control",
    "topic_gps": "test/worx/gps",
    "topic_status": "test/worx/status",
}

class TestMqttHandler(unittest.TestCase):
    """
    Testet die MqttHandler Klasse.
    """

    @patch('mqtt_handler.paho_mqtt_client.Client') # Mocke den Client *innerhalb* des Moduls
    @patch('mqtt_handler.MQTT_CONFIG', {**MOCK_CONFIG_REAL, **MOCK_CONFIG_TEST}) # Mocke die Config
    def setUp(self, mock_mqtt_config, mock_client_constructor):
        """
        Setzt die Testumgebung für jeden Test auf.
        """
        # Erstelle eine Mock-Instanz des Clients
        self.mock_mqtt_client_instance = MagicMock(spec=paho_mqtt_client.Client)
        self.mock_mqtt_client_instance.is_connected.return_value = False # Standardmässig nicht verbunden
        # Konfiguriere den Konstruktor-Mock, um unsere Instanz zurückzugeben
        mock_client_constructor.return_value = self.mock_mqtt_client_instance

        # Instanziiere den MqttHandler (test_mode=False -> Real Config)
        self.mqtt_handler_real = MqttHandler(test_mode=False)
        # Instanziiere den MqttHandler (test_mode=True -> Test Config)
        self.mqtt_handler_test = MqttHandler(test_mode=True)

        # Stelle sicher, dass der Client-Konstruktor korrekt aufgerufen wurde
        mock_client_constructor.assert_called_with(paho_mqtt_client.CallbackAPIVersion.VERSION2)


    def test_init_real_mode(self):
        """Testet die Initialisierung im Real-Modus."""
        self.assertEqual(self.mqtt_handler_real.broker, MOCK_CONFIG_REAL["host"])
        self.assertEqual(self.mqtt_handler_real.port, MOCK_CONFIG_REAL["port"])
        self.assertEqual(self.mqtt_handler_real.user, MOCK_CONFIG_REAL["user"])
        self.assertEqual(self.mqtt_handler_real.password, MOCK_CONFIG_REAL["password"])
        self.assertEqual(self.mqtt_handler_real.topic_control, MOCK_CONFIG_REAL["topic_control"])
        self.assertEqual(self.mqtt_handler_real.topic_gps, MOCK_CONFIG_REAL["topic_gps"])
        self.assertEqual(self.mqtt_handler_real.topic_status, MOCK_CONFIG_REAL["topic_status"])
        self.assertIsNotNone(self.mqtt_handler_real.mqtt_client)

    def test_init_test_mode(self):
        """Testet die Initialisierung im Test-Modus."""
        self.assertEqual(self.mqtt_handler_test.broker, MOCK_CONFIG_TEST["host_lokal"])
        self.assertEqual(self.mqtt_handler_test.port, MOCK_CONFIG_TEST["port_lokal"])
        self.assertEqual(self.mqtt_handler_test.user, MOCK_CONFIG_TEST["user_local"])
        self.assertEqual(self.mqtt_handler_test.password, MOCK_CONFIG_TEST["password_local"])
        # Topics sollten aus der Test-Config kommen (hier sind sie gleich, aber das testet es)
        self.assertEqual(self.mqtt_handler_test.topic_control, MOCK_CONFIG_TEST["topic_control"])
        self.assertEqual(self.mqtt_handler_test.topic_gps, MOCK_CONFIG_TEST["topic_gps"])
        self.assertEqual(self.mqtt_handler_test.topic_status, MOCK_CONFIG_TEST["topic_status"])
        self.assertIsNotNone(self.mqtt_handler_test.mqtt_client)

    def test_connect(self):
        """Testet die connect Methode."""
        self.mqtt_handler_real.connect()

        # Überprüfe, ob username_pw_set aufgerufen wurde (da User/PW in MOCK_CONFIG_REAL gesetzt sind)
        self.mock_mqtt_client_instance.username_pw_set.assert_called_once_with(
            MOCK_CONFIG_REAL["user"], MOCK_CONFIG_REAL["password"]
        )
        # Überprüfe, ob connect aufgerufen wurde
        self.mock_mqtt_client_instance.connect.assert_called_once_with(
            MOCK_CONFIG_REAL["host"], MOCK_CONFIG_REAL["port"], 60
        )
        # Überprüfe, ob loop_start aufgerufen wurde
        self.mock_mqtt_client_instance.loop_start.assert_called_once()

    def test_connect_test_mode_no_auth(self):
        """Testet connect im Test-Modus ohne User/Passwort."""
        # Ändere die Mock-Config temporär für diesen Test
        with patch('mqtt_handler.MQTT_CONFIG', {**MOCK_CONFIG_REAL, **{**MOCK_CONFIG_TEST, "user_local": None, "password_local": None}}):
            handler_no_auth = MqttHandler(test_mode=True)
            handler_no_auth.mqtt_client = self.mock_mqtt_client_instance # Weise den Mock zu
            handler_no_auth.connect()

            # username_pw_set sollte NICHT aufgerufen worden sein
            self.mock_mqtt_client_instance.username_pw_set.assert_not_called()
            # connect und loop_start sollten aufgerufen worden sein
            self.mock_mqtt_client_instance.connect.assert_called_once_with(
                MOCK_CONFIG_TEST["host_lokal"], MOCK_CONFIG_TEST["port_lokal"], 60
            )
            self.mock_mqtt_client_instance.loop_start.assert_called_once()


    def test_disconnect(self):
        """Testet die disconnect Methode."""
        # Simuliere, dass der Client verbunden ist
        self.mqtt_handler_real.mqtt_client = self.mock_mqtt_client_instance # Sicherstellen, dass der Mock verwendet wird

        self.mqtt_handler_real.disconnect()

        # Überprüfe, ob loop_stop und disconnect aufgerufen wurden
        self.mock_mqtt_client_instance.loop_stop.assert_called_once()
        self.mock_mqtt_client_instance.disconnect.assert_called_once()

    def test_publish_message_when_connected(self):
        """Testet das Senden einer Nachricht, wenn verbunden."""
        self.mqtt_handler_real.mqtt_client = self.mock_mqtt_client_instance
        self.mock_mqtt_client_instance.is_connected.return_value = True # Simuliere Verbindung

        topic = "test/topic"
        payload = "test_payload"
        retain = True

        # Mocke das Ergebnis von publish, um wait_for_publish zu simulieren
        mock_publish_result = MagicMock()
        mock_publish_result.rc = paho_mqtt_client.MQTT_ERR_SUCCESS
        self.mock_mqtt_client_instance.publish.return_value = mock_publish_result

        self.mqtt_handler_real.publish_message(topic, payload, retain=retain)

        # Überprüfe, ob publish korrekt aufgerufen wurde
        self.mock_mqtt_client_instance.publish.assert_called_once_with(topic, payload, retain=retain)
        # Überprüfe, ob wait_for_publish aufgerufen wurde
        mock_publish_result.wait_for_publish.assert_called_once_with(timeout=5)

    def test_publish_message_when_not_connected(self):
        """Testet das Senden einer Nachricht, wenn nicht verbunden."""
        self.mqtt_handler_real.mqtt_client = self.mock_mqtt_client_instance
        self.mock_mqtt_client_instance.is_connected.return_value = False # Simuliere keine Verbindung

        topic = "test/topic"
        payload = "test_payload"

        # Mock logging.warning to check if the warning is logged
        with patch('mqtt_handler.logging') as mock_logging:
             self.mqtt_handler_real.publish_message(topic, payload)

             # Überprüfe, ob publish NICHT aufgerufen wurde
             self.mock_mqtt_client_instance.publish.assert_not_called()
             # Überprüfe, ob eine Warnung geloggt wurde
             mock_logging.warning.assert_called_once()


    def test_subscribe_when_connected(self):
        """Testet das Abonnieren eines Topics, wenn verbunden."""
        self.mqtt_handler_real.mqtt_client = self.mock_mqtt_client_instance
        self.mock_mqtt_client_instance.is_connected.return_value = True # Simuliere Verbindung

        topic = "subscribe/topic"
        # Simuliere erfolgreiches Abonnieren
        self.mock_mqtt_client_instance.subscribe.return_value = (paho_mqtt_client.MQTT_ERR_SUCCESS, 123)

        self.mqtt_handler_real.subscribe(topic)

        # Überprüfe, ob subscribe korrekt aufgerufen wurde
        self.mock_mqtt_client_instance.subscribe.assert_called_once_with(topic)

    def test_subscribe_when_not_connected(self):
        """Testet das Abonnieren eines Topics, wenn nicht verbunden."""
        self.mqtt_handler_real.mqtt_client = self.mock_mqtt_client_instance
        self.mock_mqtt_client_instance.is_connected.return_value = False # Simuliere keine Verbindung

        topic = "subscribe/topic"

        with patch('mqtt_handler.logging') as mock_logging:
            self.mqtt_handler_real.subscribe(topic)

            # Überprüfe, ob subscribe NICHT aufgerufen wurde
            self.mock_mqtt_client_instance.subscribe.assert_not_called()
            # Überprüfe, ob eine Warnung geloggt wurde
            mock_logging.warning.assert_called_once()

    def test_set_message_callback(self):
        """Testet das Setzen und Aufrufen des Nachrichten-Callbacks."""
        self.mqtt_handler_real.mqtt_client = self.mock_mqtt_client_instance
        mock_callback = MagicMock()

        self.mqtt_handler_real.set_message_callback(mock_callback)

        # Überprüfe, ob der on_message Handler des Clients gesetzt wurde
        self.assertIsNotNone(self.mock_mqtt_client_instance.on_message)

        # Simuliere eine eingehende Nachricht
        mock_msg = MagicMock(spec=paho_mqtt_client.MQTTMessage)
        mock_msg.topic = "incoming/topic"
        mock_msg.payload = b"incoming_payload"

        # Rufe den gesetzten on_message Handler manuell auf (simuliert Paho-Aufruf)
        # Das Lambda in set_message_callback erwartet (client, userdata, msg)
        self.mock_mqtt_client_instance.on_message(self.mock_mqtt_client_instance, None, mock_msg)

        # Überprüfe, ob der benutzerdefinierte Callback mit der Nachricht aufgerufen wurde
        mock_callback.assert_called_once_with(mock_msg)

    def test_internal_on_connect_success(self):
        """Testet den internen _on_connect Callback bei Erfolg."""
        with patch('mqtt_handler.logging') as mock_logging:
             # Rufe den internen Callback direkt auf
             self.mqtt_handler_real._on_connect(self.mock_mqtt_client_instance, None, None, 0) # rc=0 -> Erfolg
             mock_logging.info.assert_called() # Prüfe, ob Info geloggt wurde
             # Optional: Prüfe die Log-Nachricht genauer
             self.assertIn("Erfolgreich mit MQTT Broker verbunden", mock_logging.info.call_args[0][0])

    def test_internal_on_connect_failure(self):
        """Testet den internen _on_connect Callback bei Fehler."""
        with patch('mqtt_handler.logging') as mock_logging:
             # Rufe den internen Callback direkt auf
             self.mqtt_handler_real._on_connect(self.mock_mqtt_client_instance, None, None, 5) # rc=5 -> Fehler
             mock_logging.error.assert_called() # Prüfe, ob Error geloggt wurde
             self.assertIn("Verbindung zum MQTT Broker fehlgeschlagen", mock_logging.error.call_args[0][0])

    def test_internal_on_disconnect(self):
        """Testet den internen _on_disconnect Callback."""
        with patch('mqtt_handler.logging') as mock_logging:
             # Rufe den internen Callback direkt auf
             self.mqtt_handler_real._on_disconnect(self.mock_mqtt_client_instance, None, 0) # rc spielt hier weniger Rolle
             mock_logging.warning.assert_called() # Prüfe, ob Warning geloggt wurde
             self.assertIn("Verbindung zum MQTT Broker getrennt", mock_logging.warning.call_args[0][0])

    def test_internal_on_message(self):
        """Testet den internen _on_message Callback (Standard)."""
        mock_msg = MagicMock(spec=paho_mqtt_client.MQTTMessage)
        mock_msg.topic = "default/topic"
        mock_msg.payload = b"default_payload"

        with patch('mqtt_handler.logging') as mock_logging:
             # Rufe den internen Callback direkt auf
             self.mqtt_handler_real._on_message(self.mock_mqtt_client_instance, None, mock_msg)
             # Prüfe, ob Debug geloggt wurde (oder die entsprechende Log-Aktion)
             mock_logging.debug.assert_called()
             self.assertIn("Standard-Nachricht empfangen", mock_logging.debug.call_args[0][0])

if __name__ == '__main__':
    unittest.main()
