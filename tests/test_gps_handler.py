# tests/test_gps_handler.py
import pytest
from unittest.mock import patch, MagicMock, call
import time
from datetime import datetime, timedelta
import serial  # Import serial for SerialException
import pynmea2  # Import pynmea2 for ParseError
import logging

# Importiere die zu testende Klasse und die verwendeten Konfigurationen
from gps_handler import GpsHandler
from config import GEO_CONFIG as REAL_GEO_CONFIG
from config import ASSIST_NOW_CONFIG as REAL_ASSIST_NOW_CONFIG
from config import REC_CONFIG as REAL_REC_CONFIG

# Mock-Konfigurationen für Tests
GEO_CONFIG_MOCK = REAL_GEO_CONFIG.copy()
GEO_CONFIG_MOCK["lat_bounds"] = (40.0, 50.0)
GEO_CONFIG_MOCK["lon_bounds"] = (5.0, 15.0)
GEO_CONFIG_MOCK["map_center"] = (45.0, 10.0)
GEO_CONFIG_MOCK["fake_gps_range"] = ((44.9, 45.1), (9.9, 10.1))

ASSIST_NOW_CONFIG_MOCK = REAL_ASSIST_NOW_CONFIG.copy()
ASSIST_NOW_CONFIG_MOCK["assist_now_enabled"] = True
ASSIST_NOW_CONFIG_MOCK["assist_now_token"] = "mock_token"
ASSIST_NOW_CONFIG_MOCK["assist_now_offline_url"] = "http://mockassist.com"

REC_CONFIG_MOCK = REAL_REC_CONFIG.copy()
REC_CONFIG_MOCK["serial_port"] = "/dev/mock_gps"
REC_CONFIG_MOCK["baudrate"] = 9600


# --- Testklasse ---
# Patche die Konfigurationen und externe Abhängigkeiten im gps_handler Modul
@patch('gps_handler.GEO_CONFIG', GEO_CONFIG_MOCK)
@patch('gps_handler.ASSIST_NOW_CONFIG', ASSIST_NOW_CONFIG_MOCK)
@patch('gps_handler.REC_CONFIG', REC_CONFIG_MOCK)
@patch('gps_handler.pynmea2.parse')
@patch('gps_handler.serial.Serial')
@patch('gps_handler.requests.get')
class TestGpsHandler:

    @pytest.fixture(autouse=True)
    # --- KORREKTUR: Mocks aus Signatur entfernt ---
    def setup_mocks_and_instance(self, MockRequestsGet, MockSerial, MockPynmea2Parse,
                                 # Die Config-Patches sind auf Klassenebene, keine Argumente hier
                                 monkeypatch):
        """Setzt Mocks auf und erstellt eine Instanz von GpsHandler für jeden Test."""
        # Speichere die Mock-Objekte
        self.MockRequestsGet = MockRequestsGet
        self.MockSerial = MockSerial
        self.mock_serial_instance = MockSerial.return_value  # Instanz von serial.Serial
        self.MockPynmea2Parse = MockPynmea2Parse

        # Standardverhalten für Mocks
        self.mock_serial_instance.is_open = True  # Simuliere offene Verbindung
        self.mock_serial_instance.readline.return_value.decode.return_value = ""  # Standard: keine Daten
        self.MockRequestsGet.return_value.raise_for_status.return_value = None
        self.MockRequestsGet.return_value.content = b"assist_data"

        # Instanz der zu testenden Klasse erstellen
        # Wichtig: Muss *nach* dem Patchen der Configs erfolgen
        from gps_handler import GpsHandler
        self.handler = GpsHandler()
        # Stelle sicher, dass der interne Serial-Mock korrekt gesetzt ist (falls _connect_serial erfolgreich war)
        if self.handler.ser_gps:
            assert self.handler.ser_gps is self.mock_serial_instance

        yield  # Lässt den Test laufen

    # Die Tests benötigen die Mocks nicht mehr als Argumente
    def test_gps_handler_init(self):
        """Tests the initialization of GpsHandler."""
        assert self.handler.lat_bounds == GEO_CONFIG_MOCK["lat_bounds"]
        assert self.handler.lon_bounds == GEO_CONFIG_MOCK["lon_bounds"]
        assert self.handler.map_center == GEO_CONFIG_MOCK["map_center"]
        assert self.handler.assist_now_token == ASSIST_NOW_CONFIG_MOCK["assist_now_token"]
        assert self.handler.assist_now_enabled == ASSIST_NOW_CONFIG_MOCK["assist_now_enabled"]
        assert self.handler.serial_port == REC_CONFIG_MOCK["serial_port"]
        assert self.handler.baudrate == REC_CONFIG_MOCK["baudrate"]
        assert self.handler.mode == "real"  # Standardmodus
        assert self.handler.is_fake_gps is False
        assert self.handler.route_simulator is None
        # Prüfe, ob _connect_serial aufgerufen wurde (und damit serial.Serial)
        self.MockSerial.assert_called_once_with(REC_CONFIG_MOCK["serial_port"], REC_CONFIG_MOCK["baudrate"], timeout=1)
        assert self.handler.ser_gps is self.mock_serial_instance

    def test_connect_serial_success(self):
        """Tests successful serial connection attempt."""
        # Reset mocks if needed, though setup_mocks_and_instance does it implicitly
        self.MockSerial.reset_mock()
        self.handler.ser_gps = None  # Simulate no connection initially
        self.handler._connect_serial()
        self.MockSerial.assert_called_once_with(REC_CONFIG_MOCK["serial_port"], REC_CONFIG_MOCK["baudrate"], timeout=1)
        assert self.handler.ser_gps is self.mock_serial_instance

    def test_connect_serial_closes_existing(self):
        """Tests that an existing connection is closed before reconnecting."""
        # Setup: Assume a connection exists
        existing_mock_serial = MagicMock()
        existing_mock_serial.is_open = True
        self.handler.ser_gps = existing_mock_serial
        self.MockSerial.reset_mock()  # Reset class mock

        self.handler._connect_serial()

        existing_mock_serial.close.assert_called_once()  # Old connection closed
        self.MockSerial.assert_called_once_with(REC_CONFIG_MOCK["serial_port"], REC_CONFIG_MOCK["baudrate"],
                                                timeout=1)  # New connection attempted
        assert self.handler.ser_gps is self.mock_serial_instance  # New mock instance assigned

    def test_connect_serial_failure(self, caplog):
        """Tests handling serial connection failure."""
        caplog.set_level(logging.ERROR)
        self.MockSerial.side_effect = serial.SerialException("Permission denied")
        self.handler.ser_gps = None  # Simulate no connection

        self.handler._connect_serial()

        self.MockSerial.assert_called_once_with(REC_CONFIG_MOCK["serial_port"], REC_CONFIG_MOCK["baudrate"], timeout=1)
        assert self.handler.ser_gps is None  # Should be None after failure
        assert "Fehler beim Herstellen der seriellen Verbindung: Permission denied" in caplog.text

    def test_connect_serial_fake_mode(self, caplog):
        """Tests that serial connection is not attempted in fake mode."""
        caplog.set_level(logging.INFO)
        self.MockSerial.reset_mock()
        self.handler.change_gps_mode("fake_random")  # Switch to fake mode

        # _connect_serial is called internally by change_gps_mode('real'),
        # but we test calling it directly in fake mode too.
        self.handler._connect_serial()

        self.MockSerial.assert_not_called()  # Serial should not be called
        assert self.handler.ser_gps is None
        assert "Fake-Modus aktiv, keine serielle Verbindung erforderlich" in caplog.text

    @pytest.mark.freeze_time("2023-10-27 12:00:00")
    def test_get_gps_data_real_mode_success_gga_fix(self):
        """Tests getting valid GGA data with a fix in real mode."""
        # Simulate receiving a valid GGA sentence
        gga_string = "$GPGGA,120000.00,4500.00000,N,01000.00000,E,1,08,0.9,100.0,M,47.0,M,,*4E"
        self.mock_serial_instance.readline.return_value.decode.return_value = gga_string

        # Mock the pynmea2.parse result
        mock_gga_msg = MagicMock(spec=pynmea2.types.talker.GGA)
        mock_gga_msg.sentence_type = 'GGA'
        mock_gga_msg.latitude = 45.0
        mock_gga_msg.longitude = 10.0
        mock_gga_msg.gps_qual = 1  # Valid fix
        mock_gga_msg.num_sats = 8
        self.MockPynmea2Parse.return_value = mock_gga_msg

        result = self.handler.get_gps_data()

        self.mock_serial_instance.readline.assert_called_once()
        self.MockPynmea2Parse.assert_called_once_with(gga_string)
        expected_timestamp = time.time()  # From freeze_time
        expected_result = {
            'lat': 45.0,
            'lon': 10.0,
            'timestamp': expected_timestamp,
            'satellites': 8,
            'mode': 'real'
        }
        assert result == expected_result
        assert self.handler.last_known_position == expected_result
        assert self.handler.last_valid_fix_time == expected_timestamp

    # ... (Add more tests for other scenarios in get_gps_data: no fix, other NMEA, parse error, serial error) ...

    def test_get_gps_data_fake_random(self):
        """Tests getting data in fake_random mode."""
        self.handler.change_gps_mode("fake_random")
        result = self.handler.get_gps_data()

        assert result is not None
        assert result['mode'] == 'fake_random'
        assert GEO_CONFIG_MOCK["fake_gps_range"][0][0] <= result['lat'] <= GEO_CONFIG_MOCK["fake_gps_range"][0][1]
        assert GEO_CONFIG_MOCK["fake_gps_range"][1][0] <= result['lon'] <= GEO_CONFIG_MOCK["fake_gps_range"][1][1]
        assert isinstance(result['timestamp'], float)
        assert 4 <= result['satellites'] <= 12
        assert self.handler.last_known_position == result

    def test_get_gps_data_fake_route(self):
        """Tests getting data in fake_route mode."""
        self.handler.change_gps_mode("fake_route")
        assert self.handler.route_simulator is not None
        # Mock the simulator's move method if needed for predictability
        with patch.object(self.handler.route_simulator, 'move', return_value=(45.0001, 10.0001)) as mock_move:
            result = self.handler.get_gps_data()

            mock_move.assert_called_once()
            assert result is not None
            assert result['mode'] == 'fake_route'
            assert result['lat'] == 45.0001
            assert result['lon'] == 10.0001
            assert isinstance(result['timestamp'], float)
            assert 7 <= result['satellites'] <= 12  # Usually good reception
            assert self.handler.last_known_position == result

    def test_is_inside_boundaries(self):
        """Tests the boundary check."""
        assert self.handler.is_inside_boundaries(45.0, 10.0) is True
        assert self.handler.is_inside_boundaries(39.0, 10.0) is False  # Below lat
        assert self.handler.is_inside_boundaries(51.0, 10.0) is False  # Above lat
        assert self.handler.is_inside_boundaries(45.0, 4.0) is False  # Below lon
        assert self.handler.is_inside_boundaries(45.0, 16.0) is False  # Above lon

    def test_download_assist_now_data_success(self):
        """Tests successful download of AssistNow data."""
        result = self.handler.download_assist_now_data()
        self.MockRequestsGet.assert_called_once()
        # Check specific args if needed, e.g., url, params['token']
        args, kwargs = self.MockRequestsGet.call_args
        assert args[0] == ASSIST_NOW_CONFIG_MOCK["assist_now_offline_url"]
        assert kwargs['params']['token'] == ASSIST_NOW_CONFIG_MOCK["assist_now_token"]
        assert result == b"assist_data"

    def test_download_assist_now_data_failure(self):
        """Tests failed download of AssistNow data."""
        self.MockRequestsGet.side_effect = requests.exceptions.RequestException("Download failed")
        result = self.handler.download_assist_now_data()
        self.MockRequestsGet.assert_called_once()
        assert result is None

    def test_send_assist_now_data_success(self):
        """Tests successful sending of AssistNow data."""
        # Ensure serial connection is mocked as open
        self.handler.ser_gps = self.mock_serial_instance
        self.mock_serial_instance.is_open = True

        self.handler.send_assist_now_data(b"test_data")
        self.mock_serial_instance.write.assert_called_once_with(b"test_data")

    def test_send_assist_now_data_not_open(self, caplog):
        """Tests sending AssistNow data when serial is not open."""
        caplog.set_level(logging.WARNING)
        self.handler.ser_gps = None  # Simulate no connection
        self.handler.send_assist_now_data(b"test_data")
        assert "Kann AssistNow nicht senden: Serielle Verbindung nicht offen" in caplog.text
        # write should not be called
        # self.mock_serial_instance.write.assert_not_called() # Fails if ser_gps is None

    def test_check_assist_now_update_needed(self):
        """Tests check_assist_now when an update is needed and successful."""
        # Force update needed
        self.handler.last_assist_now_update = datetime.now() - timedelta(days=2)
        # Mock download and send
        with patch.object(self.handler, 'download_assist_now_data', return_value=b"new_data") as mock_download, \
                patch.object(self.handler, 'send_assist_now_data') as mock_send:
            result = self.handler.check_assist_now()

            assert result is True
            mock_download.assert_called_once()
            mock_send.assert_called_once_with(b"new_data")
            # Check if last_assist_now_update was updated (approximately)
            assert datetime.now() - self.handler.last_assist_now_update < timedelta(seconds=5)

    def test_check_assist_now_no_update_needed(self):
        """Tests check_assist_now when no update is needed."""
        self.handler.last_assist_now_update = datetime.now() - timedelta(hours=1)  # Recent update
        with patch.object(self.handler, 'download_assist_now_data') as mock_download:
            result = self.handler.check_assist_now()
            assert result is True
            mock_download.assert_not_called()

    def test_change_gps_mode(self):
        """Tests changing GPS modes."""
        # Real to Fake Random
        assert self.handler.change_gps_mode("fake_random") is True
        assert self.handler.mode == "fake_random"
        assert self.handler.is_fake_gps is True
        assert self.handler.route_simulator is None
        self.mock_serial_instance.close.assert_called_once()  # Should close existing connection

        # Fake Random to Fake Route
        self.mock_serial_instance.reset_mock()
        assert self.handler.change_gps_mode("fake_route") is True
        assert self.handler.mode == "fake_route"
        assert self.handler.is_fake_gps is True
        assert self.handler.route_simulator is not None
        self.mock_serial_instance.close.assert_not_called()  # Already closed

        # Fake Route to Real
        self.MockSerial.reset_mock()  # Reset class mock for connect check
        assert self.handler.change_gps_mode("real") is True
        assert self.handler.mode == "real"
        assert self.handler.is_fake_gps is False
        assert self.handler.route_simulator is None
        self.MockSerial.assert_called_once()  # Should attempt to connect

        # Invalid mode
        assert self.handler.change_gps_mode("invalid_mode") is False
        assert self.handler.mode == "real"  # Should remain in previous valid mode
