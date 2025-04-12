# tests/test_gps_handler.py
import unittest
from unittest.mock import patch, MagicMock, call
import time
import serial # Importiere serial für SerialException
import pynmea2 # Importiere pynmea2 für ParseError
from gps_handler import GpsHandler
from config import GEO_CONFIG, ASSIST_NOW_CONFIG, REC_CONFIG # Importiere Konfigurationen

# Mock-Konfigurationen für Tests
MOCK_GEO_CONFIG = {
    "lat_bounds": (46.0, 47.0),
    "lon_bounds": (7.0, 8.0),
    "map_center": (46.5, 7.5),
    "fake_gps_range": ((46.1, 46.2), (7.1, 7.2)),
    # Weitere GEO_CONFIG Werte hier, falls benötigt
}
MOCK_ASSIST_NOW_CONFIG = {
    "assist_now_token": "dummy_token",
    "assist_now_offline_url": "http://dummy.url/offline",
    "assist_now_enabled": True,
}
MOCK_REC_CONFIG = {
    "serial_port": "/dev/ttyFAKEGPS",
    "baudrate": 9600,
    # Weitere REC_CONFIG Werte hier, falls benötigt
}

# Kombiniere die Mock-Konfigs für den Patch
FULL_MOCK_CONFIG = {
    "GEO_CONFIG": MOCK_GEO_CONFIG,
    "ASSIST_NOW_CONFIG": MOCK_ASSIST_NOW_CONFIG,
    "REC_CONFIG": MOCK_REC_CONFIG,
}

@patch.dict('gps_handler.GEO_CONFIG', MOCK_GEO_CONFIG, clear=True)
@patch.dict('gps_handler.ASSIST_NOW_CONFIG', MOCK_ASSIST_NOW_CONFIG, clear=True)
@patch.dict('gps_handler.REC_CONFIG', MOCK_REC_CONFIG, clear=True)
class TestGpsHandler(unittest.TestCase):
    """
    Testet die GpsHandler Klasse.
    """

    @patch('gps_handler.serial.Serial') # Mocke die Serial-Klasse
    def setUp(self, mock_serial_constructor):
        """
        Setzt die Testumgebung für jeden Test auf.
        """
        # Erstelle eine Mock-Instanz für die serielle Verbindung
        self.mock_serial_instance = MagicMock(spec=serial.Serial)
        self.mock_serial_instance.is_open = True # Standardmässig offen simulieren
        # Konfiguriere den Konstruktor-Mock, um unsere Instanz zurückzugeben
        mock_serial_constructor.return_value = self.mock_serial_instance

        # Instanziiere den GpsHandler
        self.gps_handler = GpsHandler()

        # Stelle sicher, dass beim Init versucht wird, die serielle Verbindung herzustellen (im 'real' Modus)
        mock_serial_constructor.assert_called_once_with(
            MOCK_REC_CONFIG["serial_port"], MOCK_REC_CONFIG["baudrate"], timeout=1
        )
        # Setze den Modus explizit zurück, falls ein Test ihn ändert
        self.gps_handler.mode = "real"
        self.gps_handler.ser_gps = self.mock_serial_instance # Weise den Mock zu

    def test_init(self):
        """Testet die Initialisierungswerte."""
        self.assertEqual(self.gps_handler.lat_bounds, MOCK_GEO_CONFIG["lat_bounds"])
        self.assertEqual(self.gps_handler.lon_bounds, MOCK_GEO_CONFIG["lon_bounds"])
        self.assertEqual(self.gps_handler.assist_now_token, MOCK_ASSIST_NOW_CONFIG["assist_now_token"])
        self.assertEqual(self.gps_handler.serial_port, MOCK_REC_CONFIG["serial_port"])
        self.assertEqual(self.gps_handler.baudrate, MOCK_REC_CONFIG["baudrate"])
        self.assertEqual(self.gps_handler.mode, "real") # Standardmodus
        self.assertIsNotNone(self.gps_handler.ser_gps)

    def test_is_inside_boundaries(self):
        """Testet die Funktion is_inside_boundaries."""
        self.assertTrue(self.gps_handler.is_inside_boundaries(46.5, 7.5)) # Mitten drin
        self.assertTrue(self.gps_handler.is_inside_boundaries(46.0, 7.0)) # Untere Grenze
        self.assertTrue(self.gps_handler.is_inside_boundaries(47.0, 8.0)) # Obere Grenze
        self.assertFalse(self.gps_handler.is_inside_boundaries(45.9, 7.5)) # Zu tief (lat)
        self.assertFalse(self.gps_handler.is_inside_boundaries(47.1, 7.5)) # Zu hoch (lat)
        self.assertFalse(self.gps_handler.is_inside_boundaries(46.5, 6.9)) # Zu weit links (lon)
        self.assertFalse(self.gps_handler.is_inside_boundaries(46.5, 8.1)) # Zu weit rechts (lon)

    @patch('gps_handler.requests.get')
    def test_download_assist_now_data_success(self, mock_requests_get):
        """Testet erfolgreichen Download von AssistNow Daten."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"assist_data"
        mock_requests_get.return_value = mock_response

        data = self.gps_handler.download_assist_now_data()

        self.assertEqual(data, b"assist_data")
        mock_requests_get.assert_called_once_with(
            MOCK_ASSIST_NOW_CONFIG["assist_now_offline_url"],
            headers=ANY, # Prüfe nicht exakte Header, nur dass sie da sind
            params={
                "token": MOCK_ASSIST_NOW_CONFIG["assist_now_token"],
                "gnss": "gps",
                "alm": "gps",
                "days": 7,
                "resolution": 1
            }
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('gps_handler.requests.get')
    def test_download_assist_now_data_failure(self, mock_requests_get):
        """Testet fehlgeschlagenen Download von AssistNow Daten."""
        mock_response = MagicMock()
        # Simuliere einen HTTP-Fehler
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Download failed")
        mock_requests_get.return_value = mock_response

        with patch('builtins.print'): # Unterdrücke Fehlermeldung
            data = self.gps_handler.download_assist_now_data()

        self.assertIsNone(data)
        mock_requests_get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    def test_send_assist_now_data_success(self):
        """Testet erfolgreiches Senden von AssistNow Daten."""
        test_data = b"ubx_assist_data"
        self.gps_handler.send_assist_now_data(test_data)
        self.mock_serial_instance.write.assert_called_once_with(test_data)

    def test_send_assist_now_data_serial_error(self):
        """Testet Senden von AssistNow Daten bei seriellem Fehler."""
        test_data = b"ubx_assist_data"
        # Simuliere einen SerialException beim Schreiben
        self.mock_serial_instance.write.side_effect = serial.SerialException("Write failed")
        # Mocke _reconnect_serial, um zu prüfen, ob es aufgerufen wird
        with patch.object(self.gps_handler, '_reconnect_serial') as mock_reconnect:
             with patch('gps_handler.logging') as mock_logging:
                 self.gps_handler.send_assist_now_data(test_data)
                 mock_logging.error.assert_called() # Prüfe, ob Fehler geloggt wird
                 mock_reconnect.assert_called_once() # Prüfe, ob Wiederverbindung versucht wird

    def test_send_assist_now_data_not_connected(self):
        """Testet Senden von AssistNow Daten, wenn nicht verbunden."""
        test_data = b"ubx_assist_data"
        self.gps_handler.ser_gps = None # Simuliere keine Verbindung

        with patch('gps_handler.logging') as mock_logging:
             self.gps_handler.send_assist_now_data(test_data)
             self.mock_serial_instance.write.assert_not_called() # write sollte nicht aufgerufen werden
             mock_logging.warning.assert_called() # Warnung sollte geloggt werden

    def test_get_gps_data_real_mode_valid_gga(self):
        """Testet get_gps_data im 'real' Modus mit gültiger GGA Nachricht."""
        # Gültige GGA Nachricht simulieren
        gga_string = "$GPGGA,123519,4630.0000,N,00730.0000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        self.mock_serial_instance.readline.return_value = gga_string.encode('utf-8')

        start_time = time.time()
        gps_data = self.gps_handler.get_gps_data()
        end_time = time.time()

        self.assertIsNotNone(gps_data)
        self.assertAlmostEqual(gps_data['lat'], 46.5, places=5) # 46 Grad 30.0000 Min = 46.5 Grad
        self.assertAlmostEqual(gps_data['lon'], 7.5, places=5)  # 7 Grad 30.0000 Min = 7.5 Grad
        self.assertGreaterEqual(gps_data['timestamp'], start_time)
        self.assertLessEqual(gps_data['timestamp'], end_time)
        self.assertEqual(gps_data['satellites'], 8)
        self.assertEqual(gps_data['mode'], 'real')
        self.mock_serial_instance.readline.assert_called_once()

    def test_get_gps_data_real_mode_invalid_gga(self):
        """Testet get_gps_data im 'real' Modus mit GGA ohne Fix (gps_qual=0)."""
        gga_string_no_fix = "$GPGGA,123519,4630.0000,N,00730.0000,E,0,08,0.9,545.4,M,46.9,M,,*48" # gps_qual = 0
        self.mock_serial_instance.readline.return_value = gga_string_no_fix.encode('utf-8')

        gps_data = self.gps_handler.get_gps_data()

        self.assertIsNone(gps_data) # Sollte None zurückgeben, da kein Fix
        self.mock_serial_instance.readline.assert_called_once()

    def test_get_gps_data_real_mode_other_nmea(self):
        """Testet get_gps_data im 'real' Modus mit einer anderen NMEA Nachricht (kein GGA)."""
        gsa_string = "$GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39" # Beispiel GSA
        self.mock_serial_instance.readline.return_value = gsa_string.encode('utf-8')

        gps_data = self.gps_handler.get_gps_data()

        self.assertIsNone(gps_data) # Sollte None zurückgeben, da kein GGA
        self.mock_serial_instance.readline.assert_called_once()

    def test_get_gps_data_real_mode_parse_error(self):
        """Testet get_gps_data im 'real' Modus mit einer fehlerhaften NMEA Nachricht."""
        invalid_string = "$GPGGA,123519,4630.0000,N,,E,1,08,0.9,545.4,M,46.9,M,,*XX" # Ungültige Checksumme/Format
        self.mock_serial_instance.readline.return_value = invalid_string.encode('utf-8')

        with patch('gps_handler.logging') as mock_logging:
            gps_data = self.gps_handler.get_gps_data()
            self.assertIsNone(gps_data)
            mock_logging.warning.assert_called() # ParseError sollte geloggt werden
            self.assertIn("Fehler beim Parsen", mock_logging.warning.call_args[0][0])
        self.mock_serial_instance.readline.assert_called_once()

    def test_get_gps_data_real_mode_serial_error(self):
        """Testet get_gps_data im 'real' Modus bei einem SerialException."""
        self.mock_serial_instance.readline.side_effect = serial.SerialException("Read failed")

        with patch.object(self.gps_handler, '_reconnect_serial') as mock_reconnect:
             with patch('gps_handler.logging') as mock_logging:
                 gps_data = self.gps_handler.get_gps_data()
                 self.assertIsNone(gps_data)
                 mock_logging.error.assert_called()
                 self.assertIn("Serieller Fehler beim Lesen", mock_logging.error.call_args[0][0])
                 mock_reconnect.assert_called_once() # Wiederverbindung sollte versucht werden

    def test_get_gps_data_fake_random_mode(self):
        """Testet get_gps_data im 'fake_random' Modus."""
        self.gps_handler.change_gps_mode("fake_random")
        start_time = time.time()
        gps_data = self.gps_handler.get_gps_data()
        end_time = time.time()

        self.assertIsNotNone(gps_data)
        self.assertGreaterEqual(gps_data['lat'], MOCK_GEO_CONFIG["fake_gps_range"][0][0])
        self.assertLessEqual(gps_data['lat'], MOCK_GEO_CONFIG["fake_gps_range"][0][1])
        self.assertGreaterEqual(gps_data['lon'], MOCK_GEO_CONFIG["fake_gps_range"][1][0])
        self.assertLessEqual(gps_data['lon'], MOCK_GEO_CONFIG["fake_gps_range"][1][1])
        self.assertGreaterEqual(gps_data['timestamp'], start_time)
        self.assertLessEqual(gps_data['timestamp'], end_time)
        self.assertGreaterEqual(gps_data['satellites'], 4)
        self.assertLessEqual(gps_data['satellites'], 12)
        self.assertEqual(gps_data['mode'], 'fake_random')
        # Serielle Schnittstelle sollte nicht gelesen werden
        self.mock_serial_instance.readline.assert_not_called()

    @patch('gps_handler.random.random', return_value=0.05) # Erzwinge Richtungsänderung
    @patch('gps_handler.random.randint', return_value=10) # Feste Richtungsänderung
    def test_get_gps_data_fake_route_mode(self, mock_randint, mock_random):
        """Testet get_gps_data im 'fake_route' Modus."""
        self.gps_handler.change_gps_mode("fake_route")
        self.assertIsNotNone(self.gps_handler.route_simulator)
        initial_lat = self.gps_handler.route_simulator.current_lat
        initial_lon = self.gps_handler.route_simulator.current_lon
        initial_direction = self.gps_handler.route_simulator.direction

        start_time = time.time()
        gps_data = self.gps_handler.get_gps_data() # Erster Aufruf bewegt
        gps_data_2 = self.gps_handler.get_gps_data() # Zweiter Aufruf bewegt weiter + ändert Richtung
        end_time = time.time()

        # Teste Daten vom zweiten Aufruf (nach möglicher Richtungsänderung)
        self.assertIsNotNone(gps_data_2)
        # Position sollte sich geändert haben
        self.assertNotEqual(gps_data_2['lat'], initial_lat)
        self.assertNotEqual(gps_data_2['lon'], initial_lon)
        self.assertGreaterEqual(gps_data_2['timestamp'], start_time)
        self.assertLessEqual(gps_data_2['timestamp'], end_time)
        self.assertGreaterEqual(gps_data_2['satellites'], 7)
        self.assertLessEqual(gps_data_2['satellites'], 12)
        self.assertEqual(gps_data_2['mode'], 'fake_route')

        # Richtung sollte sich geändert haben (da random < 0.1 und randint=10)
        self.assertNotEqual(self.gps_handler.route_simulator.direction, initial_direction)

        # Serielle Schnittstelle sollte nicht gelesen werden
        self.mock_serial_instance.readline.assert_not_called()


    @patch('gps_handler.serial.Serial') # Mocke Konstruktor neu für diesen Test
    def test_change_gps_mode(self, mock_serial_constructor):
        """Testet die change_gps_mode Methode."""
        # --- Von real zu fake_random ---
        self.gps_handler.ser_gps = self.mock_serial_instance # Stelle sicher, dass eine Verbindung existiert
        self.mock_serial_instance.is_open = True
        result = self.gps_handler.change_gps_mode("fake_random")
        self.assertTrue(result)
        self.assertEqual(self.gps_handler.mode, "fake_random")
        self.assertTrue(self.gps_handler.is_fake_gps)
        self.assertIsNone(self.gps_handler.route_simulator)
        self.mock_serial_instance.close.assert_called_once() # Verbindung sollte geschlossen werden
        self.assertIsNone(self.gps_handler.ser_gps) # ser_gps sollte None sein

        # --- Von fake_random zu fake_route ---
        self.mock_serial_instance.reset_mock() # Reset mocks
        result = self.gps_handler.change_gps_mode("fake_route")
        self.assertTrue(result)
        self.assertEqual(self.gps_handler.mode, "fake_route")
        self.assertTrue(self.gps_handler.is_fake_gps)
        self.assertIsNotNone(self.gps_handler.route_simulator)
        # close sollte nicht erneut aufgerufen werden, da ser_gps None war
        self.mock_serial_instance.close.assert_not_called()
        self.assertIsNone(self.gps_handler.ser_gps) # ser_gps sollte immer noch None sein

        # --- Von fake_route zu real ---
        # Mocke den Konstruktor neu, damit er eine Instanz zurückgibt
        mock_new_serial_instance = MagicMock(spec=serial.Serial)
        mock_serial_constructor.return_value = mock_new_serial_instance
        self.mock_serial_instance.reset_mock()
        result = self.gps_handler.change_gps_mode("real")
        self.assertTrue(result)
        self.assertEqual(self.gps_handler.mode, "real")
        self.assertFalse(self.gps_handler.is_fake_gps)
        self.assertIsNone(self.gps_handler.route_simulator)
        # Serielle Verbindung sollte neu aufgebaut werden
        mock_serial_constructor.assert_called_with(MOCK_REC_CONFIG["serial_port"], MOCK_REC_CONFIG["baudrate"], timeout=1)
        self.assertEqual(self.gps_handler.ser_gps, mock_new_serial_instance) # Neue Instanz sollte zugewiesen sein

        # --- Ungültiger Modus ---
        with patch('gps_handler.logging') as mock_logging:
             result = self.gps_handler.change_gps_mode("invalid_mode")
             self.assertFalse(result)
             mock_logging.warning.assert_called() # Warnung sollte geloggt werden

    # TODO: Tests für check_assist_now hinzufügen (mocke datetime, download, send)


if __name__ == '__main__':
    unittest.main()
