import pytest
from unittest.mock import patch, MagicMock, call
import serial  # Required for mocking SerialException
import pynmea2  # Required for mocking parse results
import requests  # Required for mocking requests
from datetime import datetime, timedelta
import time
from freezegun import freeze_time

# Mock config before importing GpsHandler
GEO_CONFIG_MOCK = {
    "lat_bounds": (46.0, 47.0),
    "lon_bounds": (7.0, 8.0),
    "map_center": (46.5, 7.5),
    "fake_gps_range": ((46.1, 46.2), (7.1, 7.2)),  # Added for fake data tests
}
ASSIST_NOW_CONFIG_MOCK = {
    "assist_now_token": "assist_token",
    "assist_now_offline_url": "http://fake-assist.com",
    "assist_now_enabled": True,
}
REC_CONFIG_MOCK = {
    "serial_port": "/dev/ttyGPS0",
    "baudrate": 9600,
}


# Mock dependencies used by GpsHandler
@patch('gps_handler.serial.Serial')
@patch('gps_handler.requests.get')
@patch('gps_handler.pynmea2.parse')
@patch('gps_handler.GEO_CONFIG', GEO_CONFIG_MOCK)
@patch('gps_handler.ASSIST_NOW_CONFIG', ASSIST_NOW_CONFIG_MOCK)
@patch('gps_handler.REC_CONFIG', REC_CONFIG_MOCK)
class TestGpsHandler:

    @pytest.fixture(autouse=True)
    def setup_mocks_and_instance(self, MockPynmea2Parse, MockRequestsGet, MockSerial):
        # Store mocks
        self.MockSerial = MockSerial
        self.mock_serial_instance = MockSerial.return_value
        self.mock_serial_instance.is_open = True  # Assume open by default after successful mock connection
        self.mock_serial_instance.readline.return_value = b''  # Default empty read
        self.mock_serial_instance.write = MagicMock()
        self.mock_serial_instance.close = MagicMock()

        self.MockRequestsGet = MockRequestsGet
        self.MockPynmea2Parse = MockPynmea2Parse

        # Create GpsHandler instance for tests
        # Patch _connect_serial during init to prevent real connection attempt
        with patch('gps_handler.GpsHandler._connect_serial') as mock_connect:
            from gps_handler import GpsHandler
            self.handler = GpsHandler()
            # Manually set ser_gps after mocked init connection
            self.handler.ser_gps = self.mock_serial_instance
            self.handler.mode = "real"  # Default to real mode for most tests
        yield  # Run the test

    def test_gps_handler_init(self):
        """Tests GpsHandler initialization."""
        # Re-init to check constructor calls
        with patch('gps_handler.GpsHandler._connect_serial') as mock_connect:
            from gps_handler import GpsHandler
            handler = GpsHandler()
            assert handler.lat_bounds == GEO_CONFIG_MOCK["lat_bounds"]
            assert handler.lon_bounds == GEO_CONFIG_MOCK["lon_bounds"]
            assert handler.map_center == GEO_CONFIG_MOCK["map_center"]
            assert handler.assist_now_token == ASSIST_NOW_CONFIG_MOCK["assist_now_token"]
            assert handler.assist_now_offline_url == ASSIST_NOW_CONFIG_MOCK["assist_now_offline_url"]
            assert handler.assist_now_enabled == ASSIST_NOW_CONFIG_MOCK["assist_now_enabled"]
            assert handler.serial_port == REC_CONFIG_MOCK["serial_port"]
            assert handler.baudrate == REC_CONFIG_MOCK["baudrate"]
            assert handler.mode == "real"  # Default mode
            assert handler.is_fake_gps is False
            assert handler.route_simulator is None
            assert handler.last_valid_fix_time == 0
            assert handler.last_known_position is None
            mock_connect.assert_called_once()  # Check connection attempt during init

    def test_connect_serial_success(self):
        """Tests the _connect_serial method success."""
        # Reset mock and instance for clean test
        self.MockSerial.reset_mock()
        self.mock_serial_instance = self.MockSerial.return_value
        self.handler.ser_gps = None  # Ensure it's None before connect
        self.handler.mode = "real"

        self.handler._connect_serial()

        self.MockSerial.assert_called_once_with(self.handler.serial_port, self.handler.baudrate, timeout=1)
        assert self.handler.ser_gps == self.mock_serial_instance

    def test_connect_serial_closes_existing(self):
        """Tests that _connect_serial closes an existing connection."""
        self.handler.ser_gps = self.mock_serial_instance  # Assume existing connection
        self.handler.mode = "real"

        self.handler._connect_serial()

        self.mock_serial_instance.close.assert_called_once()
        self.MockSerial.assert_called_once_with(self.handler.serial_port, self.handler.baudrate, timeout=1)
        assert self.handler.ser_gps == self.MockSerial.return_value  # Should be the new instance

    def test_connect_serial_failure(self, caplog):
        """Tests _connect_serial handling SerialException."""
        self.MockSerial.side_effect = serial.SerialException("Connection failed")
        self.handler.ser_gps = None
        self.handler.mode = "real"

        self.handler._connect_serial()

        self.MockSerial.assert_called_once()
        assert self.handler.ser_gps is None
        assert "Fehler beim Herstellen der seriellen Verbindung: Connection failed" in caplog.text

    def test_connect_serial_fake_mode(self, caplog):
        """Tests _connect_serial does nothing in fake mode."""
        self.MockSerial.reset_mock()
        self.handler.ser_gps = None
        self.handler.mode = "fake_random"  # Set fake mode

        self.handler._connect_serial()

        self.MockSerial.assert_not_called()
        assert self.handler.ser_gps is None
        assert "Fake-Modus aktiv, keine serielle Verbindung erforderlich." in caplog.text

    def test_is_inside_boundaries(self):
        """Tests the boundary check."""
        assert self.handler.is_inside_boundaries(46.5, 7.5) is True  # Inside
        assert self.handler.is_inside_boundaries(46.0, 7.0) is True  # On boundary min
        assert self.handler.is_inside_boundaries(47.0, 8.0) is True  # On boundary max
        assert self.handler.is_inside_boundaries(45.9, 7.5) is False  # Below lat
        assert self.handler.is_inside_boundaries(47.1, 7.5) is False  # Above lat
        assert self.handler.is_inside_boundaries(46.5, 6.9) is False  # Below lon
        assert self.handler.is_inside_boundaries(46.5, 8.1) is False  # Above lon

    def test_download_assist_now_data_success(self):
        """Tests successful AssistNow download."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'assist_data'
        mock_response.raise_for_status.return_value = None
        self.MockRequestsGet.return_value = mock_response

        data = self.handler.download_assist_now_data()

        assert data == b'assist_data'
        self.MockRequestsGet.assert_called_once_with(
            self.handler.assist_now_offline_url,
            headers={"useragent": "Thingstream Client"},
            params={
                "token": self.handler.assist_now_token,
                "gnss": "gps", "alm": "gps", "days": 7, "resolution": 1
            }
        )
        mock_response.raise_for_status.assert_called_once()

    def test_download_assist_now_data_failure(self, capsys):
        """Tests failed AssistNow download."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Network Error")
        self.MockRequestsGet.return_value = mock_response

        data = self.handler.download_assist_now_data()

        assert data is None
        captured = capsys.readouterr()
        assert "Fehler beim Herunterladen der AssistNow Offline-Daten: Network Error" in captured.out

    def test_send_assist_now_data_success(self):
        """Tests sending AssistNow data successfully."""
        test_data = b'assist_data_to_send'
        self.handler.ser_gps = self.mock_serial_instance  # Ensure serial mock is set
        self.mock_serial_instance.is_open = True

        self.handler.send_assist_now_data(test_data)

        self.mock_serial_instance.write.assert_called_once_with(test_data)

    def test_send_assist_now_data_not_open(self, caplog):
        """Tests sending AssistNow data when serial is not open."""
        self.handler.ser_gps = self.mock_serial_instance
        self.mock_serial_instance.is_open = False  # Simulate closed port

        self.handler.send_assist_now_data(b'data')

        self.mock_serial_instance.write.assert_not_called()
        assert "Kann AssistNow nicht senden: Serielle Verbindung nicht offen." in caplog.text

    def test_send_assist_now_data_serial_error(self, caplog):
        """Tests sending AssistNow data with SerialException during write."""
        self.handler.ser_gps = self.mock_serial_instance
        self.mock_serial_instance.is_open = True
        self.mock_serial_instance.write.side_effect = serial.SerialException("Write failed")

        # Mock reconnect to check if it's called
        with patch.object(self.handler, '_reconnect_serial') as mock_reconnect:
            self.handler.send_assist_now_data(b'data')

            self.mock_serial_instance.write.assert_called_once_with(b'data')
            assert "Serieller Fehler beim Senden der AssistNow Offline-Daten: Write failed" in caplog.text
            mock_reconnect.assert_called_once()  # Check reconnect attempt

    @freeze_time("2023-10-27 12:00:00")
    def test_get_gps_data_real_mode_success_gga_fix(self):
        """Tests get_gps_data in real mode with a valid GGA fix."""
        nmea_string = "$GPGGA,120000.00,4630.1234,N,00730.5678,E,1,08,0.9,100.0,M,48.0,M,,*47"
        self.mock_serial_instance.readline.return_value = nmea_string.encode('utf-8')

        # Mock the parsed message
        mock_gga_msg = MagicMock(spec=pynmea2.types.talker.GGA)
        mock_gga_msg.sentence_type = 'GGA'
        mock_gga_msg.latitude = 46.502056  # Example conversion
        mock_gga_msg.longitude = 7.509463  # Example conversion
        mock_gga_msg.gps_qual = 1  # GPS fix
        mock_gga_msg.num_sats = '08'
        self.MockPynmea2Parse.return_value = mock_gga_msg

        expected_timestamp = time.time()
        result = self.handler.get_gps_data()

        self.mock_serial_instance.readline.assert_called_once()
        self.MockPynmea2Parse.assert_called_once_with(nmea_string)
        expected_result = {
            'lat': mock_gga_msg.latitude,
            'lon': mock_gga_msg.longitude,
            'timestamp': expected_timestamp,
            'satellites': 8,  # Converted from string '08'
            'mode': 'real'
        }
        assert result == expected_result
        assert self.handler.last_valid_fix_time == expected_timestamp
        assert self.handler.last_known_position == expected_result

    def test_get_gps_data_real_mode_gga_no_fix(self):
        """Tests get_gps_data in real mode with GGA but no fix."""
        nmea_string = "$GPGGA,120001.00,,,,0,,,,,,,,,*67"  # No fix data
        self.mock_serial_instance.readline.return_value = nmea_string.encode('utf-8')
        mock_gga_msg = MagicMock(spec=pynmea2.types.talker.GGA)
        mock_gga_msg.sentence_type = 'GGA'
        mock_gga_msg.gps_qual = 0  # No fix
        self.MockPynmea2Parse.return_value = mock_gga_msg

        result = self.handler.get_gps_data()

        assert result is None  # Should return None if no fix
        self.MockPynmea2Parse.assert_called_once_with(nmea_string)

    def test_get_gps_data_real_mode_other_nmea(self):
        """Tests get_gps_data in real mode with a non-GGA sentence."""
        nmea_string = "$GPRMC,120002.00,A,4630.1234,N,00730.5678,E,0.0,0.0,271023,,,A*70"
        self.mock_serial_instance.readline.return_value = nmea_string.encode('utf-8')
        mock_rmc_msg = MagicMock(spec=pynmea2.types.talker.RMC)  # Mock different type
        mock_rmc_msg.sentence_type = 'RMC'
        self.MockPynmea2Parse.return_value = mock_rmc_msg

        result = self.handler.get_gps_data()

        assert result is None  # Should return None for non-GGA
        self.MockPynmea2Parse.assert_called_once_with(nmea_string)

    def test_get_gps_data_real_mode_parse_error(self, caplog):
        """Tests get_gps_data handling pynmea2.ParseError."""
        nmea_string = "$GPGGA,invalid_data*XX"
        self.mock_serial_instance.readline.return_value = nmea_string.encode('utf-8')
        self.MockPynmea2Parse.side_effect = pynmea2.ParseError("Bad checksum")

        result = self.handler.get_gps_data()

        assert result is None
        self.MockPynmea2Parse.assert_called_once_with(nmea_string)
        assert "Fehler beim Parsen der NMEA-Zeile: Bad checksum" in caplog.text

    def test_get_gps_data_real_mode_serial_error(self, caplog):
        """Tests get_gps_data handling serial.SerialException."""
        self.mock_serial_instance.readline.side_effect = serial.SerialException("Read error")

        with patch.object(self.handler, '_reconnect_serial') as mock_reconnect:
            result = self.handler.get_gps_data()

            assert result is None
            assert "Serieller Fehler beim Lesen von GPS: Read error" in caplog.text
            mock_reconnect.assert_called_once()

    def test_get_gps_data_real_mode_not_open(self, caplog):
        """Tests get_gps_data when serial port is not open."""
        self.mock_serial_instance.is_open = False

        with patch.object(self.handler, '_reconnect_serial') as mock_reconnect:
            result = self.handler.get_gps_data()

            assert result is None
            assert "Serielle GPS-Verbindung nicht offen." in caplog.text
            mock_reconnect.assert_called_once()

    @freeze_time("2023-10-27 13:00:00")
    @patch('gps_handler.random.uniform', side_effect=[46.15, 7.15])  # Mock lat, lon
    @patch('gps_handler.random.randint', return_value=7)  # Mock satellites
    def test_get_gps_data_fake_random_mode(self, mock_randint, mock_uniform):
        """Tests get_gps_data in fake_random mode."""
        self.handler.mode = "fake_random"
        expected_time = time.time()

        result = self.handler.get_gps_data()

        mock_uniform.assert_has_calls([call(46.1, 46.2), call(7.1, 7.2)])
        mock_randint.assert_called_once_with(4, 12)
        expected_result = {
            'lat': 46.15, 'lon': 7.15, 'timestamp': expected_time, 'satellites': 7, 'mode': 'fake_random'
        }
        assert result == expected_result
        assert self.handler.last_known_position == expected_result

    @freeze_time("2023-10-27 14:00:00")
    @patch('gps_handler.random.randint', return_value=9)  # Mock satellites
    def test_get_gps_data_fake_route_mode(self, mock_randint):
        """Tests get_gps_data in fake_route mode."""
        self.handler.mode = "fake_route"
        # Initialize the simulator for the test
        from gps_handler import GpsHandler  # Re-import locally if needed for RouteSimulator
        self.handler.route_simulator = GpsHandler.RouteSimulator(46.5, 7.5, speed=0.0001, direction=90)  # Move East
        expected_time = time.time()

        # Mock the simulator's move method
        with patch.object(self.handler.route_simulator, 'move', return_value=(46.5, 7.5001)) as mock_move:
            result = self.handler.get_gps_data()

            mock_move.assert_called_once()
            mock_randint.assert_called_once_with(7, 12)
            expected_result = {
                'lat': 46.5, 'lon': 7.5001, 'timestamp': expected_time, 'satellites': 9, 'mode': 'fake_route'
            }
            assert result == expected_result
            assert self.handler.last_known_position == expected_result

    def test_get_gps_data_fake_route_mode_no_simulator(self, caplog):
        """Tests fake_route mode when simulator is not initialized."""
        self.handler.mode = "fake_route"
        self.handler.route_simulator = None  # Ensure simulator is None

        # It should fall back to generate_fake_data
        with patch.object(self.handler, 'generate_fake_data', return_value={'fake': True}) as mock_gen_fake:
            result = self.handler.get_gps_data()
            assert result == {'fake': True}
            mock_gen_fake.assert_called_once()
            assert "Routenmodus aktiv, aber kein Routensimulator initialisiert." in caplog.text

    @freeze_time("2023-10-27 15:00:00")
    def test_check_assist_now_update_needed_success(self):
        """Tests check_assist_now when update is needed and successful."""
        self.handler.assist_now_enabled = True
        self.handler.last_assist_now_update = datetime.now() - timedelta(days=2)  # Make it old

        with patch.object(self.handler, 'download_assist_now_data', return_value=b'new_data') as mock_download, \
                patch.object(self.handler, 'send_assist_now_data') as mock_send:
            result = self.handler.check_assist_now()

            assert result is True
            mock_download.assert_called_once()
            mock_send.assert_called_once_with(b'new_data')
            # Check last update time was reset (within tolerance for freeze_time)
            assert (datetime.now() - self.handler.last_assist_now_update).total_seconds() < 1

    @freeze_time("2023-10-27 15:00:00")
    def test_check_assist_now_update_needed_download_fail(self, capsys):
        """Tests check_assist_now when update is needed but download fails."""
        self.handler.assist_now_enabled = True
        self.handler.last_assist_now_update = datetime.now() - timedelta(days=2)
        original_update_time = self.handler.last_assist_now_update

        with patch.object(self.handler, 'download_assist_now_data', return_value=None) as mock_download, \
                patch.object(self.handler, 'send_assist_now_data') as mock_send, \
                patch('time.sleep') as mock_sleep:  # Mock sleep

            result = self.handler.check_assist_now()

            assert result is False  # Should return False on failure
            mock_download.assert_called_once()
            mock_send.assert_not_called()
            mock_sleep.assert_called_once_with(2)
            # Check last update time was NOT reset
            assert self.handler.last_assist_now_update == original_update_time
            captured = capsys.readouterr()
            assert "AssistNow Offline-Daten konnten nicht heruntergeladen werden." in captured.out

    @freeze_time("2023-10-27 15:00:00")
    def test_check_assist_now_not_needed(self):
        """Tests check_assist_now when update is not needed."""
        self.handler.assist_now_enabled = True
        self.handler.last_assist_now_update = datetime.now() - timedelta(hours=12)  # Recent update

        with patch.object(self.handler, 'download_assist_now_data') as mock_download, \
                patch.object(self.handler, 'send_assist_now_data') as mock_send:
            result = self.handler.check_assist_now()

            assert result is True
            mock_download.assert_not_called()
            mock_send.assert_not_called()

    def test_check_assist_now_disabled(self):
        """Tests check_assist_now when it's disabled."""
        self.handler.assist_now_enabled = False
        self.handler.last_assist_now_update = datetime.now() - timedelta(days=5)  # Make it old

        with patch.object(self.handler, 'download_assist_now_data') as mock_download, \
                patch.object(self.handler, 'send_assist_now_data') as mock_send:
            result = self.handler.check_assist_now()

            assert result is True  # Still returns True if disabled
            mock_download.assert_not_called()
            mock_send.assert_not_called()

    def test_change_gps_mode_to_fake_random(self):
        """Tests changing mode to fake_random."""
        self.handler.mode = "real"
        self.handler.ser_gps = self.mock_serial_instance  # Assume connected
        self.mock_serial_instance.is_open = True

        result = self.handler.change_gps_mode("fake_random")

        assert result is True
        assert self.handler.mode == "fake_random"
        assert self.handler.is_fake_gps is True
        assert self.handler.route_simulator is None
        # Check serial port was closed
        self.mock_serial_instance.close.assert_called_once()
        assert self.handler.ser_gps is None

    @patch('gps_handler.GpsHandler.RouteSimulator')
    def test_change_gps_mode_to_fake_route(self, MockRouteSimulator):
        """Tests changing mode to fake_route."""
        self.handler.mode = "real"
        self.handler.ser_gps = self.mock_serial_instance
        self.mock_serial_instance.is_open = True
        mock_sim_instance = MockRouteSimulator.return_value

        result = self.handler.change_gps_mode("fake_route")

        assert result is True
        assert self.handler.mode == "fake_route"
        assert self.handler.is_fake_gps is True
        # Check simulator was initialized
        MockRouteSimulator.assert_called_once_with(self.handler.map_center[0], self.handler.map_center[1],
                                                   direction=pytest.approx(0, abs=360))  # Direction is random
        assert self.handler.route_simulator == mock_sim_instance
        # Check serial port was closed
        self.mock_serial_instance.close.assert_called_once()
        assert self.handler.ser_gps is None

    def test_change_gps_mode_to_real(self):
        """Tests changing mode to real."""
        self.handler.mode = "fake_random"
        self.handler.ser_gps = None  # Assume disconnected
        self.handler.route_simulator = MagicMock()  # Assume simulator exists

        with patch.object(self.handler, '_connect_serial') as mock_connect:
            result = self.handler.change_gps_mode("real")

            assert result is True
            assert self.handler.mode == "real"
            assert self.handler.is_fake_gps is False
            assert self.handler.route_simulator is None  # Simulator should be cleared
            # Check connection attempt was made
            mock_connect.assert_called_once()

    def test_change_gps_mode_invalid(self, caplog):
        """Tests changing to an invalid mode."""
        original_mode = self.handler.mode
        result = self.handler.change_gps_mode("invalid_mode")

        assert result is False
        assert self.handler.mode == original_mode  # Mode should not change
        assert "Ungültiger GPS-Modus angefordert: invalid_mode" in caplog.text
