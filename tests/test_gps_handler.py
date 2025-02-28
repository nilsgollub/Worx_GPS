import unittest
from unittest.mock import patch, MagicMock
from gps_handler import GpsHandler
from config import GEO_CONFIG, REC_CONFIG
import pynmea2
import serial


@patch('gps_handler.serial.Serial')
class TestGpsHandler(unittest.TestCase):
    def setUp(self, MockSerial):
        self.gps_handler = GpsHandler()

    def test_change_gps_mode_fake(self, mock_serial):  # Korrektur: self hinzugefügt
        mock_instance = mock_serial.return_value
        self.gps_handler.change_gps_mode("fake")
        self.assertFalse(mock_instance.write.called)

    def test_change_gps_mode_fake_route(self, mock_serial):  # Korrektur: self hinzugefügt
        mock_instance = mock_serial.return_value
        self.gps_handler.change_gps_mode("fake_route")
        self.assertFalse(mock_instance.write.called)

    def test_change_gps_mode_real(self, mock_serial):  # Korrektur: self hinzugefügt
        mock_instance = mock_serial.return_value
        self.gps_handler.change_gps_mode("real")
        self.assertTrue(mock_instance.write.called)

    def test_change_gps_mode_wrong(self, mock_serial):  # Korrektur: self hinzugefügt
        mock_instance = mock_serial.return_value
        with self.assertRaises(ValueError):
            self.gps_handler.change_gps_mode("wrong")
        self.assertFalse(mock_instance.write.called)

    def test_check_assist_now(self, mock_serial):  # Korrektur: self hinzugefügt
        self.gps_handler.check_assist_now()
        self.assertFalse(mock_serial.called)

    def test_get_gps_data_fake(self, mock_serial):  # Korrektur: self hinzugefügt
        self.gps_handler.change_gps_mode("fake")
        self.gps_handler.get_gps_data()
        self.assertIsNotNone(self.gps_handler.gps_data)

    def test_get_gps_data_invalid(self, mock_serial):  # Korrektur: self hinzugefügt
        mock_instance = mock_serial.return_value
        mock_instance.readline.return_value = b"wrong"
        self.gps_handler.change_gps_mode("real")
        self.gps_handler.get_gps_data()
        self.assertIsNone(self.gps_handler.gps_data)

    def test_get_gps_data_real(self, mock_serial):  # Korrektur: self hinzugefügt
        mock_instance = mock_serial.return_value
        mock_instance.readline.return_value = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,"
        self.gps_handler.change_gps_mode("real")
        self.gps_handler.get_gps_data()
        self.assertIsNotNone(self.gps_handler.gps_data)

    def test_is_inside_boundaries(self):  # Korrektur: self hinzugefügt
        self.assertTrue(self.gps_handler.is_inside_boundaries(GEO_CONFIG["lat_bounds"][0], GEO_CONFIG["lon_bounds"][0]))
        self.assertFalse(
            self.gps_handler.is_inside_boundaries(GEO_CONFIG["lat_bounds"][0] - 1, GEO_CONFIG["lon_bounds"][0] - 1))
