import unittest
from unittest.mock import patch, MagicMock
from gps_handler import GpsHandler
import time
import os


class TestGpsHandler(unittest.TestCase):
    @patch('gps_handler.serial.Serial')
    def setUp(self, MockSerial):
        # Vor jedem Test
        self.mock_serial = MagicMock()
        MockSerial.return_value = self.mock_serial
        self.gps_handler = GpsHandler()

    def test_is_inside_boundaries(self):
        self.assertTrue(self.gps_handler.is_inside_boundaries(46.8119, 7.1329))
        self.assertFalse(self.gps_handler.is_inside_boundaries(0, 0))

    def test_get_gps_data_fake(self):
        self.gps_handler.change_gps_mode("fake_random")
        gps_data = self.gps_handler.get_gps_data()
        self.assertIsNotNone(gps_data)
        self.assertIn("lat", gps_data)
        self.assertIn("lon", gps_data)
        self.assertIn("timestamp", gps_data)
        self.assertIn("satellites", gps_data)
        self.gps_handler.change_gps_mode("real")

    def test_get_gps_data_real(self):
        self.mock_serial.readline.return_value = b'$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n'  # Gültige NMEA-Nachricht
        gps_data = self.gps_handler.get_gps_data()
        self.assertIsNotNone(gps_data)
        self.assertIn("lat", gps_data)
        self.assertIn("lon", gps_data)
        self.assertIn("timestamp", gps_data)
        self.assertIn("satellites", gps_data)

    def test_get_gps_data_invalid(self):
        self.mock_serial.readline.return_value = b'Ungueltige Daten\r\n'
        gps_data = self.gps_handler.get_gps_data()
        self.assertIsNone(gps_data)

    def test_check_assist_now(self):
        self.gps_handler.assist_now_enabled = False
        self.gps_handler.check_assist_now()
        self.gps_handler.assist_now_enabled = True
        self.gps_handler.last_assist_now_update = time.time()
        self.gps_handler.check_assist_now()
        self.gps_handler.last_assist_now_update = os.path.getctime(__file__)
        with patch('gps_handler.GpsHandler.download_assist_now_data') as mock_download:
            mock_download.return_value = b"test"
            with patch('gps_handler.GpsHandler.send_assist_now_data') as mock_send:
                self.gps_handler.check_assist_now()
                self.assertTrue(mock_send.called)

    def test_change_gps_mode_fake(self):
        self.gps_handler.change_gps_mode("fake_random")
        self.assertTrue(self.gps_handler.is_fake_gps)
        self.assertIsNone(self.gps_handler.route_simulator)

    def test_change_gps_mode_fake_route(self):
        self.gps_handler.change_gps_mode("fake_route")
        self.assertTrue(self.gps_handler.is_fake_gps)
        self.assertIsNotNone(self.gps_handler.route_simulator)

    def test_change_gps_mode_real(self):
        self.gps_handler.change_gps_mode("real")
        self.assertFalse(self.gps_handler.is_fake_gps)
        self.assertIsNone(self.gps_handler.route_simulator)

    def test_change_gps_mode_wrong(self):
        self.assertFalse(self.gps_handler.change_gps_mode("wrong"))
