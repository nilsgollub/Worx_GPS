# tests/test_gps_handler.py
import pytest
from unittest.mock import patch, MagicMock, ANY, call
from freezegun import freeze_time
from datetime import datetime, timedelta
import time
import serial  # Import für Patch-Pfad und Exception
import pynmea2  # Import für Patch-Pfad und Exception
import requests  # Import für Patch-Pfad und Exception
import math  # Import für Berechnungen
import logging  # Import für caplog

# Importiere die zu testende Klasse und Konfigurationen
from gps_handler import GpsHandler
from config import GEO_CONFIG, ASSIST_NOW_CONFIG, REC_CONFIG


# --- FIXTURE DEFINITIONS ---
@pytest.fixture
def MockSerial():
    """Fixture to mock serial.Serial."""
    with patch('gps_handler.serial.Serial', autospec=True) as MockS:
        mock_instance = MockS.return_value
        mock_instance.is_open = True
        mock_instance.readline.return_value = b''
        mock_instance.write.return_value = 0
        mock_instance.close = MagicMock()
        yield MockS


@pytest.fixture
def MockPynmea2Parse():
    """Fixture to mock pynmea2.parse."""
    with patch('gps_handler.pynmea2.parse', autospec=True) as MockP:
        yield MockP


@pytest.fixture
def MockRequestsGet():
    """Fixture to mock requests.get."""
    with patch('gps_handler.requests.get', autospec=True) as MockR:
        mock_response = MockR.return_value
        mock_response.status_code = 200
        mock_response.content = b"dummy_assist_data"
        mock_response.raise_for_status = MagicMock()
        yield MockR


# --- END FIXTURE DEFINITIONS ---


class TestGpsHandler:

    @pytest.fixture(autouse=True)
    def setup_mocks_and_instance(self, MockRequestsGet, MockSerial, MockPynmea2Parse, monkeypatch):
        """Sets up mocks and the GpsHandler instance for each test."""

        # 1. Mocks an self binden (frühzeitig)
        self.mock_serial_class = MockSerial
        self.mock_serial_instance = MockSerial.return_value
        self.mock_pynmea2_parse = MockPynmea2Parse
        self.mock_requests_get = MockRequestsGet

        # 2. Konfiguration patchen
        self.mock_geo = GEO_CONFIG.copy()
        self.mock_assist = ASSIST_NOW_CONFIG.copy()
        self.mock_rec = REC_CONFIG.copy()
        self.mock_assist["assist_now_enabled"] = False
        self.mock_rec["serial_port"] = "COM_TEST"
        self.mock_rec["baudrate"] = 9600

        monkeypatch.setattr("gps_handler.GEO_CONFIG", self.mock_geo)
        monkeypatch.setattr("gps_handler.ASSIST_NOW_CONFIG", self.mock_assist)
        monkeypatch.setattr("gps_handler.REC_CONFIG", self.mock_rec)

        # 3. GpsHandler initialisieren (mit Patch für _connect_serial)
        try:
            with patch.object(GpsHandler, '_connect_serial', return_value=None) as mock_connect_in_init:
                self.handler = GpsHandler()
                # Speichere den Patch, um zu prüfen, ob er im init aufgerufen wurde
                self.mock_connect_serial_in_init = mock_connect_in_init
        except Exception as e:
            pytest.fail(f"Fehler bei der Initialisierung von GpsHandler in der Fixture: {e}")

        # 4. Sicherstellen, dass handler existiert
        if not hasattr(self, 'handler'):
            pytest.fail("Fixture konnte 'self.handler' nicht initialisieren (nach try-except).")

        # 5. Yield für Testausführung
        yield

    def test_gps_handler_init(self):
        """Tests the initialization of GpsHandler."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        assert self.handler.lat_bounds == self.mock_geo["lat_bounds"]
        assert self.handler.lon_bounds == self.mock_geo["lon_bounds"]
        assert self.handler.map_center == self.mock_geo["map_center"]
        assert self.handler.assist_now_token == self.mock_assist["assist_now_token"]
        assert self.handler.assist_now_offline_url == self.mock_assist["assist_now_offline_url"]
        assert self.handler.assist_now_enabled is False
        assert self.handler.serial_port == "COM_TEST"
        assert self.handler.baudrate == 9600
        assert self.handler.mode == "real"
        self.mock_connect_serial_in_init.assert_called_once()
        assert self.handler.ser_gps is None

    def test_connect_serial_success(self):
        """Tests successful serial connection call."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        self.handler.mode = "real"
        # Rufe die *echte* Methode auf (der Patch aus dem Setup ist hier nicht mehr aktiv)
        self.handler._connect_serial()
        self.mock_serial_class.assert_called_once_with("COM_TEST", 9600, timeout=1)
        assert self.handler.ser_gps is self.mock_serial_instance
        assert self.mock_serial_instance.is_open is True

    def test_connect_serial_closes_existing(self):
        """Tests that an existing connection is closed before reconnecting."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        # 1. Erste Verbindung
        self.handler.mode = "real"
        self.handler._connect_serial()
        first_instance = self.handler.ser_gps
        assert first_instance is self.mock_serial_instance
        self.mock_serial_class.assert_called_once_with("COM_TEST", 9600, timeout=1)
        first_instance.close.assert_not_called()

        # 2. Zweite Verbindung
        self.handler._connect_serial()

        # Prüfe, ob close auf der *ersten* (und einzigen Mock-) Instanz aufgerufen wurde
        first_instance.close.assert_called_once()
        # Prüfe, ob Serial() erneut aufgerufen wurde
        assert self.mock_serial_class.call_count == 2
        # Prüfe, ob die Instanz immer noch zugewiesen ist
        assert self.handler.ser_gps is self.mock_serial_instance

    def test_connect_serial_failure(self, caplog):
        """Tests serial connection failure."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        caplog.set_level(logging.ERROR)
        self.handler.mode = "real"
        # Konfiguriere MockSerial, um eine Exception auszulösen
        self.mock_serial_class.side_effect = serial.SerialException("Permission denied")
        # Rufe _connect_serial auf
        self.handler._connect_serial()
        # Prüfe, ob Serial() aufgerufen wurde (trotz Fehler)
        self.mock_serial_class.assert_called_once_with("COM_TEST", 9600, timeout=1)
        # Prüfe, ob der Fehler geloggt wurde
        assert "Fehler beim Herstellen der seriellen Verbindung: Permission denied" in caplog.text
        # Prüfe, ob ser_gps None ist
        assert self.handler.ser_gps is None

    def test_connect_serial_fake_mode(self, caplog):
        """Tests that no serial connection is attempted in fake mode."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        caplog.set_level(logging.INFO)
        # Wichtig: Zuerst Modus ändern, DANN _connect_serial aufrufen
        self.handler.change_gps_mode("fake_random")  # Schließt ggf. alte Verbindung
        self.mock_serial_class.reset_mock()  # Setze Mock zurück nach change_gps_mode
        self.handler._connect_serial()  # Rufe _connect auf, während Modus fake ist
        # Prüfe, dass Serial() NICHT aufgerufen wurde
        self.mock_serial_class.assert_not_called()
        # Prüfe, ob die Info geloggt wurde
        assert "Fake-Modus aktiv, keine serielle Verbindung erforderlich." in caplog.text
        assert self.handler.ser_gps is None

    @pytest.mark.freeze_time("2023-10-27 12:00:00")
    def test_get_gps_data_real_mode_success_gga_fix(self):
        """Tests getting valid GGA data with a fix in real mode."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        self.handler.mode = "real"
        self.handler.ser_gps = self.mock_serial_instance  # Weise Mock-Instanz explizit zu
        self.mock_serial_instance.is_open = True

        gga_line = b"$GPGGA,120000.00,4610.12345,N,00705.54321,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
        self.mock_serial_instance.readline.return_value = gga_line

        mock_gga_msg = MagicMock(spec=pynmea2.types.talker.GGA)
        mock_gga_msg.sentence_type = 'GGA'
        mock_gga_msg.latitude = 46.16872416666667
        mock_gga_msg.longitude = 7.092386833333333
        mock_gga_msg.gps_qual = 1
        mock_gga_msg.num_sats = '08'  # pynmea2 liefert es als String
        self.mock_pynmea2_parse.return_value = mock_gga_msg

        expected_timestamp = time.time()
        expected_data = {
            'lat': mock_gga_msg.latitude,
            'lon': mock_gga_msg.longitude,
            'timestamp': expected_timestamp,
            'satellites': 8,  # Erwartet wird int (wird in gps_handler.py konvertiert)
            'mode': 'real'
        }

        result = self.handler.get_gps_data()

        self.mock_serial_instance.readline.assert_called_once()
        self.mock_pynmea2_parse.assert_called_once_with(gga_line.decode().strip())
        assert result == expected_data  # Sollte jetzt passen
        assert self.handler.last_valid_fix_time == expected_timestamp
        assert self.handler.last_known_position == expected_data

    @patch('gps_handler.random.uniform', side_effect=[46.123, 7.456])
    @patch('gps_handler.random.randint', return_value=9)
    @freeze_time("2023-10-27 13:00:00")
    def test_get_gps_data_fake_random(self, mock_randint, mock_uniform):
        """Tests getting data in fake_random mode."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        self.handler.change_gps_mode("fake_random")
        expected_timestamp = time.time()
        expected_data = {
            'lat': 46.123,
            'lon': 7.456,
            'timestamp': expected_timestamp,
            'satellites': 9,
            'mode': 'fake_random'
        }
        result = self.handler.get_gps_data()
        assert result == expected_data
        assert self.handler.last_known_position == expected_data
        self.mock_serial_instance.readline.assert_not_called()

    @freeze_time("2023-10-27 14:00:00")
    def test_get_gps_data_fake_route(self):
        """Tests getting data in fake_route mode."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        self.handler.change_gps_mode("fake_route")
        assert self.handler.route_simulator is not None

        start_lat, start_lon = self.handler.map_center
        with patch.object(self.handler.route_simulator, 'move',
                          return_value=(start_lat + 0.0001, start_lon + 0.0001)) as mock_move:
            expected_timestamp = time.time()
            expected_data = {
                'lat': start_lat + 0.0001,
                'lon': start_lon + 0.0001,
                'timestamp': expected_timestamp,
                'satellites': ANY,
                'mode': 'fake_route'
            }
            result = self.handler.get_gps_data()

            mock_move.assert_called_once()
            assert result['lat'] == expected_data['lat']
            assert result['lon'] == expected_data['lon']
            assert result['timestamp'] == expected_data['timestamp']
            assert result['mode'] == expected_data['mode']
            assert self.handler.last_known_position == result
            self.mock_serial_instance.readline.assert_not_called()

    def test_is_inside_boundaries(self):
        """Tests the boundary check."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        lat_min, lat_max = self.handler.lat_bounds
        lon_min, lon_max = self.handler.lon_bounds
        assert self.handler.is_inside_boundaries(lat_min + 0.0001, lon_min + 0.0001) is True
        assert self.handler.is_inside_boundaries(lat_max - 0.0001, lon_max - 0.0001) is True
        assert self.handler.is_inside_boundaries(lat_min - 0.0001, lon_min) is False
        assert self.handler.is_inside_boundaries(lat_min, lon_min - 0.0001) is False
        assert self.handler.is_inside_boundaries(lat_max + 0.0001, lon_max) is False
        assert self.handler.is_inside_boundaries(lat_max, lon_max + 0.0001) is False

    def test_download_assist_now_data_success(self):
        """Tests successful download of AssistNow data."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        result = self.handler.download_assist_now_data()
        self.mock_requests_get.assert_called_once()
        args, kwargs = self.mock_requests_get.call_args
        assert args[0] == self.handler.assist_now_offline_url
        assert kwargs['params']['token'] == self.handler.assist_now_token
        assert result == b"dummy_assist_data"
        self.mock_requests_get.return_value.raise_for_status.assert_called_once()

    # --- KORREKTUR: Patch logging.error statt builtins.print ---
    @patch('gps_handler.logging.error')
    def test_download_assist_now_data_failure(self, mock_log_error):  # mock_print ersetzt
        """Tests failure during download of AssistNow data."""
        assert hasattr(self, 'mock_requests_get'), "self.mock_requests_get wurde nicht initialisiert"
        self.mock_requests_get.side_effect = requests.exceptions.RequestException("Network error")
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        result = self.handler.download_assist_now_data()
        self.mock_requests_get.assert_called_once()
        assert result is None
        # Prüfe, ob logging.error aufgerufen wurde
        mock_log_error.assert_called_with("Fehler beim Herunterladen der AssistNow Offline-Daten: Network error")

    # --- ENDE KORREKTUR ---

    def test_send_assist_now_data_success(self, caplog):
        """Tests successful sending of AssistNow data."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        caplog.set_level(logging.INFO)
        # Stelle sicher, dass eine Verbindung simuliert wird
        self.handler.mode = "real"
        self.handler.ser_gps = self.mock_serial_instance
        self.mock_serial_instance.is_open = True

        test_data = b"some_ubx_data"
        self.handler.send_assist_now_data(test_data)
        self.mock_serial_instance.write.assert_called_once_with(test_data)
        assert "AssistNow Offline-Daten erfolgreich gesendet." in caplog.text

    def test_send_assist_now_data_not_open(self, caplog):
        """Tests sending AssistNow data when serial port is not open."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        caplog.set_level(logging.WARNING)
        self.handler.ser_gps = None  # Simuliere geschlossene Verbindung
        test_data = b"some_ubx_data"
        self.handler.send_assist_now_data(test_data)
        self.mock_serial_instance.write.assert_not_called()
        assert "Kann AssistNow nicht senden: Serielle Verbindung nicht offen." in caplog.text

    @freeze_time("2023-10-27 15:00:00")
    @patch.object(GpsHandler, 'download_assist_now_data')
    @patch.object(GpsHandler, 'send_assist_now_data')
    def test_check_assist_now_update_needed(self, mock_send, mock_download):
        """Tests check_assist_now when an update is needed."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        self.handler.assist_now_enabled = True
        self.handler.last_assist_now_update = datetime.now() - timedelta(days=2)
        mock_download.return_value = b"new_assist_data"
        result = self.handler.check_assist_now()
        assert result is True
        mock_download.assert_called_once()
        mock_send.assert_called_once_with(b"new_assist_data")
        assert self.handler.last_assist_now_update == datetime(2023, 10, 27, 15, 0, 0)

    @freeze_time("2023-10-27 15:00:00")
    @patch.object(GpsHandler, 'download_assist_now_data')
    @patch.object(GpsHandler, 'send_assist_now_data')
    def test_check_assist_now_no_update_needed(self, mock_send, mock_download):
        """Tests check_assist_now when no update is needed."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        self.handler.assist_now_enabled = True
        # Setze eine Zeit, die *innerhalb* des Update-Intervalls liegt
        self.handler.last_assist_now_update = datetime.now() - timedelta(hours=12)
        initial_update_time = self.handler.last_assist_now_update  # Merke dir die Zeit

        result = self.handler.check_assist_now()
        assert result is True
        mock_download.assert_not_called()
        mock_send.assert_not_called()
        # Zeitstempel sollte unverändert bleiben
        assert self.handler.last_assist_now_update == initial_update_time

    @patch.object(GpsHandler, '_connect_serial')
    def test_change_gps_mode(self, mock_connect_serial, caplog):
        """Tests changing the GPS mode."""
        assert hasattr(self, 'handler'), "self.handler wurde nicht initialisiert"
        assert hasattr(self, 'mock_serial_instance'), "self.mock_serial_instance wurde nicht initialisiert"
        caplog.set_level(logging.INFO)

        # Simuliere, dass initial eine Verbindung besteht
        self.handler.ser_gps = self.mock_serial_instance
        self.mock_serial_instance.is_open = True

        # 1. Wechsel zu fake_random
        result1 = self.handler.change_gps_mode("fake_random")
        assert result1 is True
        assert self.handler.mode == "fake_random"
        assert self.handler.is_fake_gps is True
        assert self.handler.route_simulator is None
        self.mock_serial_instance.close.assert_called_once()
        assert "Serielle Verbindung für Fake-Modus geschlossen." in caplog.text
        assert self.handler.ser_gps is None
        mock_connect_serial.assert_not_called()  # _connect_serial wird nicht gerufen

        # 2. Wechsel zu fake_route
        self.mock_serial_instance.close.reset_mock()  # Setze close zurück
        caplog.clear()  # Leere caplog
        result2 = self.handler.change_gps_mode("fake_route")
        assert result2 is True
        assert self.handler.mode == "fake_route"
        assert self.handler.is_fake_gps is True
        assert isinstance(self.handler.route_simulator, GpsHandler.RouteSimulator)
        # close wird nicht erneut gerufen, da ser_gps schon None ist
        self.mock_serial_instance.close.assert_not_called()
        mock_connect_serial.assert_not_called()

        # 3. Wechsel zurück zu real
        caplog.clear()
        result3 = self.handler.change_gps_mode("real")
        assert result3 is True
        assert self.handler.mode == "real"
        assert self.handler.is_fake_gps is False
        assert self.handler.route_simulator is None
        # Prüfe, ob _connect_serial aufgerufen wurde
        mock_connect_serial.assert_called_once()

        # 4. Ungültiger Modus
        mock_connect_serial.reset_mock()  # Setze Mock zurück
        caplog.clear()
        result4 = self.handler.change_gps_mode("invalid_mode")
        assert result4 is False
        assert self.handler.mode == "real"  # Modus sollte unverändert bleiben
        assert "Ungültiger GPS-Modus angefordert: invalid_mode" in caplog.text
        mock_connect_serial.assert_not_called()  # Nicht aufgerufen bei ungültigem Modus
