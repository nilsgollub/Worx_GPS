# tests/test_data_recorder.py
import unittest
from unittest.mock import MagicMock, call, patch
import io # Für StringIO
from data_recorder import DataRecorder

class TestDataRecorder(unittest.TestCase):
    """
    Testet die DataRecorder Klasse.
    """

    def setUp(self):
        """
        Setzt die Testumgebung für jeden Test auf.
        """
        # Erstelle einen Mock für den MqttHandler
        self.mock_mqtt_handler = MagicMock()
        # Definiere das Topic, das der Recorder verwenden soll
        self.test_topic = "test/worx/gps"
        self.mock_mqtt_handler.topic_gps = self.test_topic

        # Instanziiere den DataRecorder mit dem Mock-Handler
        self.data_recorder = DataRecorder(self.mock_mqtt_handler)

    def test_init(self):
        """Testet die Initialisierung."""
        self.assertEqual(self.data_recorder.mqtt_handler, self.mock_mqtt_handler)
        self.assertEqual(self.data_recorder.gps_data_buffer, [])

    def test_init_no_handler(self):
        """Testet, ob ein Fehler ausgelöst wird, wenn kein Handler übergeben wird."""
        with self.assertRaises(ValueError):
            DataRecorder(None)

    def test_add_gps_data_valid(self):
        """Testet das Hinzufügen gültiger GPS-Daten."""
        data1 = {'lat': 46.1, 'lon': 7.1, 'timestamp': 1000.0, 'satellites': 5}
        data2 = {'lat': 46.2, 'lon': 7.2, 'timestamp': 1001.5, 'satellites': 6}

        self.data_recorder.add_gps_data(data1)
        self.assertEqual(self.data_recorder.gps_data_buffer, [data1])

        self.data_recorder.add_gps_data(data2)
        self.assertEqual(self.data_recorder.gps_data_buffer, [data1, data2])

    def test_add_gps_data_invalid(self):
        """Testet das Hinzufügen ungültiger Daten (kein Dict oder None)."""
        initial_buffer = list(self.data_recorder.gps_data_buffer) # Kopie erstellen

        with patch('data_recorder.logging') as mock_logging:
            self.data_recorder.add_gps_data(None)
            # Buffer sollte unverändert sein, keine Warnung für None
            self.assertEqual(self.data_recorder.gps_data_buffer, initial_buffer)
            mock_logging.warning.assert_not_called()

            self.data_recorder.add_gps_data("not a dict")
            # Buffer sollte unverändert sein, Warnung sollte geloggt werden
            self.assertEqual(self.data_recorder.gps_data_buffer, initial_buffer)
            mock_logging.warning.assert_called_once()
            self.assertIn("Ignoriere ungültige GPS-Daten", mock_logging.warning.call_args[0][0])

    def test_clear_buffer(self):
        """Testet das Leeren des Puffers."""
        self.data_recorder.add_gps_data({'lat': 46.1, 'lon': 7.1, 'timestamp': 1000.0, 'satellites': 5})
        self.assertNotEqual(self.data_recorder.gps_data_buffer, []) # Sicherstellen, dass er nicht leer ist

        self.data_recorder.clear_buffer()
        self.assertEqual(self.data_recorder.gps_data_buffer, [])

    def test_send_buffer_data_with_data(self):
        """Testet das Senden von Daten, wenn der Puffer gefüllt ist."""
        data1 = {'lat': 46.1, 'lon': 7.1, 'timestamp': 1000.0, 'satellites': 5}
        data2 = {'lat': 46.2, 'lon': 7.2, 'timestamp': 1001.5, 'satellites': 6}
        data3 = {'lat': 46.3, 'lon': 7.3} # Fehlende Keys testen

        self.data_recorder.add_gps_data(data1)
        self.data_recorder.add_gps_data(data2)
        self.data_recorder.add_gps_data(data3)

        # Erwarteter CSV-String (ohne Kopfzeile, fehlende Werte sind leer)
        expected_csv_string = f"{data1['lat']},{data1['lon']},{data1['timestamp']},{data1['satellites']}\n" \
                              f"{data2['lat']},{data2['lon']},{data2['timestamp']},{data2['satellites']}\n" \
                              f"{data3['lat']},{data3['lon']},,\n" # timestamp und satellites fehlen

        self.data_recorder.send_buffer_data()

        # Überprüfe, ob publish_message zweimal aufgerufen wurde:
        # 1. Mit den CSV-Daten
        # 2. Mit dem End-Marker "-1"
        expected_calls = [
            call(self.test_topic, expected_csv_string),
            call(self.test_topic, "-1")
        ]
        self.mock_mqtt_handler.publish_message.assert_has_calls(expected_calls)
        self.assertEqual(self.mock_mqtt_handler.publish_message.call_count, 2)

    def test_send_buffer_data_empty_buffer(self):
        """Testet das Senden von Daten, wenn der Puffer leer ist."""
        self.assertEqual(self.data_recorder.gps_data_buffer, []) # Sicherstellen, dass er leer ist

        with patch('data_recorder.logging') as mock_logging:
             self.data_recorder.send_buffer_data()

             # Überprüfe, ob publish_message nur einmal aufgerufen wurde (mit dem End-Marker)
             self.mock_mqtt_handler.publish_message.assert_called_once_with(self.test_topic, "-1")
             # Überprüfe, ob eine Warnung geloggt wurde
             mock_logging.warning.assert_called_once()
             self.assertIn("Kein Daten im Puffer zum Senden", mock_logging.warning.call_args[0][0])


    def test_send_buffer_data_mqtt_error(self):
        """Testet das Verhalten bei einem Fehler während des MQTT-Publish."""
        data1 = {'lat': 46.1, 'lon': 7.1, 'timestamp': 1000.0, 'satellites': 5}
        self.data_recorder.add_gps_data(data1)

        # Simuliere einen Fehler beim ersten Publish-Aufruf (Daten)
        self.mock_mqtt_handler.publish_message.side_effect = [Exception("MQTT Publish Error"), None] # Fehler beim ersten, Erfolg beim zweiten (-1)

        with patch('data_recorder.logging') as mock_logging:
            self.data_recorder.send_buffer_data()

            # Überprüfe, ob publish_message zweimal versucht wurde
            self.assertEqual(self.mock_mqtt_handler.publish_message.call_count, 2)
            # Überprüfe, ob der Fehler geloggt wurde
            mock_logging.error.assert_called_once()
            self.assertIn("Fehler beim Senden der Daten oder des End-Markers via MQTT", mock_logging.error.call_args[0][0])

    def test_send_buffer_data_no_topic(self):
        """Testet das Verhalten, wenn das MQTT-Topic im Handler fehlt."""
        # Entferne das Topic-Attribut vom Mock-Handler
        del self.mock_mqtt_handler.topic_gps

        data1 = {'lat': 46.1, 'lon': 7.1, 'timestamp': 1000.0, 'satellites': 5}
        self.data_recorder.add_gps_data(data1)

        with patch('data_recorder.logging') as mock_logging:
            self.data_recorder.send_buffer_data()

            # publish_message sollte nicht aufgerufen worden sein
            self.mock_mqtt_handler.publish_message.assert_not_called()
            # Fehler sollte geloggt werden
            mock_logging.error.assert_called_once()
            self.assertIn("MQTT handler hat kein 'topic_gps' Attribut", mock_logging.error.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
