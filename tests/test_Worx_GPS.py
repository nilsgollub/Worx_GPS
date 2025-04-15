# tests/test_Worx_GPS.py
import pytest
from unittest.mock import patch, MagicMock, call, ANY
from freezegun import freeze_time
import time
from collections import deque
import logging  # Import logging

# Importiere die zu testende Klasse und die Konfigurationen, die sie verwendet
from Worx_GPS import WorxGps
from config import HEATMAP_CONFIG as REAL_HEATMAP_CONFIG
from config import REC_CONFIG as REAL_REC_CONFIG

# --- Mock-Konfigurationen für Tests ---
MOCK_HEATMAP_CONFIG = REAL_HEATMAP_CONFIG.copy()
MOCK_REC_CONFIG = REAL_REC_CONFIG.copy()
MOCK_REC_CONFIG["test_mode"] = False


# --- Testklasse ---
class TestWorxGps:

    @pytest.fixture(autouse=True)
    def setup_mocks_and_instance(self, monkeypatch):
        """Setzt Mocks auf und erstellt eine Instanz von WorxGps für jeden Test."""

        # --- Start Patches ---
        self.patcher_mqtt = patch('Worx_GPS.MqttHandler')
        self.MockMqttHandler = self.patcher_mqtt.start()

        self.patcher_heatmap = patch('Worx_GPS.HeatmapGenerator')
        self.MockHeatmapGenerator = self.patcher_heatmap.start()

        self.patcher_data_manager = patch('Worx_GPS.DataManager')
        self.MockDataManager = self.patcher_data_manager.start()

        self.patcher_read_gps = patch('Worx_GPS.read_gps_data_from_csv_string')
        self.mock_read_gps = self.patcher_read_gps.start()

        # --- Konfiguriere Mock-Instanzen (Return Values) ---
        self.mock_mqtt_instance = MagicMock()
        self.MockMqttHandler.return_value = self.mock_mqtt_instance

        self.mock_heatmap_instance = MagicMock()
        self.MockHeatmapGenerator.return_value = self.mock_heatmap_instance

        self.mock_data_manager_instance = MagicMock()
        self.MockDataManager.return_value = self.mock_data_manager_instance

        # Konfiguriere MQTT-Instanz-Attribute
        self.mock_mqtt_instance.topic_gps = "mock/worx/gps"
        self.mock_mqtt_instance.topic_status = "mock/worx/status"
        self.mock_mqtt_instance.topic_control = "mock/worx/control"

        # Konfiguriere DataManager-Instanz-Methoden
        mock_dm_instance = self.mock_data_manager_instance
        mock_dm_instance.get_next_mow_filename.return_value = "maehvorgang_1.json"
        mock_dm_instance.remove_old_problemzonen.return_value = None
        self._initial_problemzonen_deque = deque(maxlen=100)
        mock_dm_instance.read_problemzonen_data.return_value = self._initial_problemzonen_deque

        # Patch REC_CONFIG und HEATMAP_CONFIG im Zielmodul
        monkeypatch.setitem(MOCK_REC_CONFIG, "test_mode", False)
        monkeypatch.setattr("Worx_GPS.REC_CONFIG", MOCK_REC_CONFIG, raising=False)
        monkeypatch.setattr("Worx_GPS.HEATMAP_CONFIG", MOCK_HEATMAP_CONFIG, raising=False)

        # --- Erstelle die Instanz der zu testenden Klasse ---
        self.worx_gps = WorxGps()
        self.worx_gps.problemzonen_data = self._initial_problemzonen_deque

        yield  # Lässt den Test laufen

        # --- Stop Patches ---
        self.patcher_read_gps.stop()
        self.patcher_data_manager.stop()
        self.patcher_heatmap.stop()
        self.patcher_mqtt.stop()

    def test_worx_gps_init(self):
        """Testet die Initialisierung von WorxGps."""
        self.MockMqttHandler.assert_called_once_with(False)
        self.MockHeatmapGenerator.assert_called_once()
        self.MockDataManager.assert_called_once()

        assert self.worx_gps.mqtt_handler is self.mock_mqtt_instance
        assert self.worx_gps.heatmap_generator is self.mock_heatmap_instance
        assert self.worx_gps.data_manager is self.mock_data_manager_instance

        self.mock_mqtt_instance.set_message_callback.assert_called_once_with(self.worx_gps.on_mqtt_message)
        self.mock_mqtt_instance.connect.assert_called_once()
        self.mock_data_manager_instance.read_problemzonen_data.assert_called_once()
        assert self.worx_gps.problemzonen_data is self._initial_problemzonen_deque

    def test_on_mqtt_message_gps_topic(self):
        """Testet die Verarbeitung einer Nachricht auf dem GPS-Topic."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_gps
        mock_msg.payload.decode.return_value = "46.1,7.1,100,5"

        with patch.object(self.worx_gps, 'handle_gps_data') as mock_handle_gps:
            self.worx_gps.on_mqtt_message(mock_msg)
            mock_handle_gps.assert_called_once_with("46.1,7.1,100,5")

    def test_on_mqtt_message_status_topic(self):
        """Testet die Verarbeitung einer Nachricht auf dem Status-Topic."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_status
        mock_msg.payload.decode.return_value = "problem,46.5,7.5"

        with patch.object(self.worx_gps, 'handle_status_data') as mock_handle_status:
            self.worx_gps.on_mqtt_message(mock_msg)
            mock_handle_status.assert_called_once_with("problem,46.5,7.5")

    def test_on_mqtt_message_other_topic(self):
        """Testet, dass Nachrichten auf anderen Topics ignoriert werden."""
        mock_msg = MagicMock()
        mock_msg.topic = "some/other/topic"
        mock_msg.payload.decode.return_value = "some data"

        with patch.object(self.worx_gps, 'handle_gps_data') as mock_handle_gps, \
                patch.object(self.worx_gps, 'handle_status_data') as mock_handle_status:
            self.worx_gps.on_mqtt_message(mock_msg)
            mock_handle_gps.assert_not_called()
            mock_handle_status.assert_not_called()

    def test_handle_gps_data_buffering(self):
        """Testet, dass Daten korrekt gepuffert werden, bis der End-Marker kommt."""
        self.worx_gps.gps_data_buffer = ""
        self.worx_gps.handle_gps_data("46.1,7.1,100,5\n")
        assert self.worx_gps.gps_data_buffer == "46.1,7.1,100,5\n"
        self.worx_gps.handle_gps_data("46.2,7.2,101,6\n")
        assert self.worx_gps.gps_data_buffer == "46.1,7.1,100,5\n46.2,7.2,101,6\n"
        self.mock_read_gps.assert_not_called()

    def test_handle_gps_data_processing_success(self):
        """Testet die erfolgreiche Verarbeitung nach dem End-Marker."""
        self.worx_gps.gps_data_buffer = "46.1,7.1,100,5\n46.2,7.2,101,6"
        mock_parsed_data = [
            {'lat': 46.1, 'lon': 7.1, 'timestamp': 100, 'satellites': 5},
            {'lat': 46.2, 'lon': 7.2, 'timestamp': 101, 'satellites': 6}
        ]
        self.mock_read_gps.return_value = mock_parsed_data

        self.worx_gps.maehvorgang_data = deque(maxlen=10)
        self.worx_gps.alle_maehvorgang_data = []
        self.worx_gps.problemzonen_data.clear()

        self.worx_gps.handle_gps_data("-1")

        assert self.worx_gps.gps_data_buffer == ""
        self.mock_read_gps.assert_called_once_with("46.1,7.1,100,5\n46.2,7.2,101,6")

        self.mock_data_manager_instance.get_next_mow_filename.assert_called_once()
        self.mock_data_manager_instance.save_gps_data.assert_called_once_with(
            mock_parsed_data, "maehvorgang_1.json"
        )
        assert list(self.worx_gps.maehvorgang_data) == [mock_parsed_data]
        assert self.worx_gps.alle_maehvorgang_data == mock_parsed_data

        expected_data_last_10 = [point for sublist in self.worx_gps.maehvorgang_data for point in sublist]
        expected_data_problem = list(self.worx_gps.problemzonen_data)

        # --- Korrektur: Erwarte nur den Dateipfad als zweites Argument ---
        expected_calls = [
            call(mock_parsed_data, MOCK_HEATMAP_CONFIG["heatmap_aktuell"]["output"], True),
            call(expected_data_last_10, MOCK_HEATMAP_CONFIG["heatmap_10_maehvorgang"]["output"], False),
            call(self.worx_gps.alle_maehvorgang_data, MOCK_HEATMAP_CONFIG["heatmap_kumuliert"]["output"], False),
            call(expected_data_problem, MOCK_HEATMAP_CONFIG["problemzonen_heatmap"]["output"], False),
        ]
        # --- Ende Korrektur ---
        self.mock_heatmap_instance.create_heatmap.assert_has_calls(expected_calls, any_order=False)
        assert self.mock_heatmap_instance.create_heatmap.call_count == 4

        # --- Korrektur: Prüfe save_html_as_png Aufrufe separat ---
        expected_png_calls = [
            call(MOCK_HEATMAP_CONFIG["heatmap_aktuell"]["output"],
                 MOCK_HEATMAP_CONFIG["heatmap_aktuell"]["png_output"]),
            call(MOCK_HEATMAP_CONFIG["heatmap_10_maehvorgang"]["output"],
                 MOCK_HEATMAP_CONFIG["heatmap_10_maehvorgang"]["png_output"]),
            call(MOCK_HEATMAP_CONFIG["heatmap_kumuliert"]["output"],
                 MOCK_HEATMAP_CONFIG["heatmap_kumuliert"]["png_output"]),
            call(MOCK_HEATMAP_CONFIG["problemzonen_heatmap"]["output"],
                 MOCK_HEATMAP_CONFIG["problemzonen_heatmap"]["png_output"]),
        ]
        self.mock_heatmap_instance.save_html_as_png.assert_has_calls(expected_png_calls, any_order=True)
        assert self.mock_heatmap_instance.save_html_as_png.call_count == 4
        # --- Ende Korrektur ---

    def test_handle_gps_data_processing_parse_fail(self, caplog):
        """Testet das Verhalten, wenn das Parsen der GPS-Daten fehlschlägt."""
        caplog.set_level(logging.ERROR)
        self.worx_gps.gps_data_buffer = "invalid data"
        self.mock_read_gps.return_value = []

        self.worx_gps.handle_gps_data("-1")

        assert self.worx_gps.gps_data_buffer == ""
        self.mock_read_gps.assert_called_once_with("invalid data")
        self.mock_data_manager_instance.get_next_mow_filename.assert_not_called()
        self.mock_data_manager_instance.save_gps_data.assert_not_called()
        self.mock_heatmap_instance.create_heatmap.assert_not_called()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "error_gps")
        assert "Fehler: Konnte keine GPS-Daten aus dem Puffer lesen oder Puffer war leer." in caplog.text

    @freeze_time("2023-10-27 16:00:00")
    def test_handle_status_data_problem_success(self, caplog):  # caplog statt capsys
        """Testet die Verarbeitung einer gültigen Problemzonen-Nachricht."""
        # --- Korrektur: Setze Log-Level für Debug-Nachricht ---
        caplog.set_level(logging.DEBUG)
        # --- Ende Korrektur ---

        csv_data = "problem,46.5,7.5"
        expected_timestamp = time.time()
        expected_problem_data = {"lat": 46.5, "lon": 7.5, "timestamp": expected_timestamp}

        self.worx_gps.problemzonen_data.clear()

        expected_deque_after_append = deque([expected_problem_data], maxlen=100)
        self.mock_data_manager_instance.read_problemzonen_data.return_value = expected_deque_after_append

        self.worx_gps.handle_status_data(csv_data)

        assert len(self.worx_gps.problemzonen_data) == 1
        assert self.worx_gps.problemzonen_data[0] == expected_problem_data
        assert self.worx_gps.problemzonen_data is expected_deque_after_append

        self.mock_data_manager_instance.remove_old_problemzonen.assert_called_once()
        self.mock_data_manager_instance.save_problemzonen_data.assert_called_once_with(expected_deque_after_append)

        # --- Korrektur: Erwarte nur den Dateipfad als zweites Argument ---
        self.mock_heatmap_instance.create_heatmap.assert_called_once_with(
            list(expected_deque_after_append),
            MOCK_HEATMAP_CONFIG["problemzonen_heatmap"]["output"],  # Nur der Pfad
            False
        )
        # --- Ende Korrektur ---

        # --- Korrektur: Prüfe save_html_as_png Aufruf separat ---
        self.mock_heatmap_instance.save_html_as_png.assert_called_once_with(
            MOCK_HEATMAP_CONFIG["problemzonen_heatmap"]["output"],
            MOCK_HEATMAP_CONFIG["problemzonen_heatmap"]["png_output"]
        )
        # --- Ende Korrektur ---

        # --- Korrektur: Prüfe Log-Ausgabe statt print ---
        # captured = capsys.readouterr() # ALT
        # assert f"Empfangene Problemzonen-Daten: {csv_data}" in captured.out # ALT
        assert f"Empfangene Problemzonen-Daten: {csv_data}" in caplog.text  # NEU (prüft DEBUG log)
        assert f"Problemzone hinzugefügt: {expected_problem_data}" in caplog.text  # NEU (prüft INFO log)
        # --- Ende Korrektur ---

    def test_handle_status_data_problem_end_marker(self):
        """Testet, dass der spezielle End-Marker 'problem,-1,-1' ignoriert wird."""
        csv_data = "problem,-1,-1"
        initial_deque = self.mock_data_manager_instance.read_problemzonen_data()
        initial_len = len(initial_deque)

        self.worx_gps.handle_status_data(csv_data)

        assert len(self.worx_gps.problemzonen_data) == initial_len
        self.mock_data_manager_instance.remove_old_problemzonen.assert_not_called()
        self.mock_data_manager_instance.save_problemzonen_data.assert_not_called()
        self.mock_heatmap_instance.create_heatmap.assert_not_called()

    def test_handle_status_data_problem_parse_error(self, caplog):
        """Testet das Verhalten bei ungültigen Koordinaten in Problemzonen-Nachricht."""
        caplog.set_level(logging.ERROR)
        csv_data = "problem,invalid,7.5"
        initial_deque = self.mock_data_manager_instance.read_problemzonen_data()
        initial_len = len(initial_deque)

        self.worx_gps.handle_status_data(csv_data)

        assert len(self.worx_gps.problemzonen_data) == initial_len
        self.mock_data_manager_instance.remove_old_problemzonen.assert_not_called()
        self.mock_data_manager_instance.save_problemzonen_data.assert_not_called()
        self.mock_heatmap_instance.create_heatmap.assert_not_called()
        assert f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}" in caplog.text

    def test_handle_status_data_other_status(self, caplog):  # caplog statt capsys
        """Testet die Verarbeitung anderer (nicht-Problem) Statusmeldungen."""
        # --- Korrektur: Setze Log-Level für Info-Nachricht ---
        caplog.set_level(logging.INFO)
        # --- Ende Korrektur ---

        csv_data = "status,ok,123"
        initial_deque = self.mock_data_manager_instance.read_problemzonen_data()
        initial_len = len(initial_deque)

        self.worx_gps.handle_status_data(csv_data)

        assert len(self.worx_gps.problemzonen_data) == initial_len
        self.mock_data_manager_instance.remove_old_problemzonen.assert_not_called()
        self.mock_data_manager_instance.save_problemzonen_data.assert_not_called()
        self.mock_heatmap_instance.create_heatmap.assert_not_called()

        # --- Korrektur: Prüfe Log-Ausgabe statt print ---
        # captured = capsys.readouterr() # ALT
        # assert f"Empfangene Statusmeldung: {csv_data}" in captured.out # ALT
        assert f"Empfangene Statusmeldung: {csv_data}" in caplog.text  # NEU
        # --- Ende Korrektur ---
