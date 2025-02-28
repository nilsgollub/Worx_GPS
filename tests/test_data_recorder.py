import unittest
from unittest.mock import MagicMock
from data_recorder import DataRecorder


class TestDataRecorder(unittest.TestCase):
    def setUp(self):
        # Vor jedem Test
        self.mock_mqtt_handler = MagicMock()
        self.data_recorder = DataRecorder(self.mock_mqtt_handler)

    def test_add_gps_data(self):
        # Testdaten
        gps_data = {"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200, "satellites": 10}
        # Funktion aufrufen
        self.data_recorder.add_gps_data(gps_data)
        # Überprüfen ob die Daten korrekt gespeichert wurden
        expected_data = "46.811819,7.132838,1672531200.0,10\n"
        self.assertEqual(self.data_recorder.gps_data_buffer, expected_data)

    def test_send_buffer_data(self):
        # Testdaten
        gps_data1 = {"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200, "satellites": 10}
        gps_data2 = {"lat": 46.811820, "lon": 7.132839, "timestamp": 1672531201, "satellites": 10}
        # Hinzufügen der Testdaten
        self.data_recorder.add_gps_data(gps_data1)
        self.data_recorder.add_gps_data(gps_data2)
        # Funktion aufrufen
        self.data_recorder.send_buffer_data()
        # Überprüfen der Publishes
        self.assertEqual(self.mock_mqtt_handler.publish_message.call_count, 2)
        # Überprüfen ob der korrekte ende Marker gesendet wurde.
        self.mock_mqtt_handler.publish_message.assert_called_with(self.mock_mqtt_handler.topic_gps, "-1")
        # Überprüfen ob der Puffer geleert wurde.
        self.assertEqual(self.data_recorder.gps_data_buffer, "")

    def test_clear_buffer(self):
        # Testdaten hinzufügen
        gps_data = {"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200, "satellites": 10}
        self.data_recorder.add_gps_data(gps_data)
        # Funktion aufrufen
        self.data_recorder.clear_buffer()
        # Überprüfen ob der Puffer geleert wurde.
        self.assertEqual(self.data_recorder.gps_data_buffer, "")
