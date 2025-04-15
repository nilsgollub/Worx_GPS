# tests/test_Worx_GPS_Rec.py (Final fix for status_sending_logic counts)
import pytest
from unittest.mock import patch, MagicMock, call, ANY
from freezegun import freeze_time
import time
from datetime import datetime, timedelta
import logging

# Importiere die zu testende Klasse und die verwendeten Konfigurationen/Klassen
from Worx_GPS_Rec import WorxGpsRec
from config import REC_CONFIG as REAL_REC_CONFIG


# --- Custom Exception for Tests ---
class StopTestLoopException(Exception):
    """Custom exception to stop the main_loop simulation in tests."""
    pass


# --- End Custom Exception ---

# Mock-Konfigurationen
MOCK_REC_CONFIG = REAL_REC_CONFIG.copy()
MOCK_REC_CONFIG["test_mode"] = False
MOCK_REC_CONFIG["storage_interval"] = 0.1  # Use a small interval for faster testing


# --- Explicit Fixtures for Mocks ---

@pytest.fixture
def mock_mqtt_handler():
    """Fixture for mocking MqttHandler."""
    with patch('Worx_GPS_Rec.MqttHandler', autospec=True) as MockClass:
        instance = MockClass.return_value
        instance.topic_control = "mock/worx/control"
        instance.topic_status = "mock/worx/status"
        instance.topic_gps = "mock/worx/gps"
        yield instance


@pytest.fixture
def mock_gps_handler():
    """Fixture for mocking GpsHandler."""
    with patch('Worx_GPS_Rec.GpsHandler', autospec=True) as MockClass:
        instance = MockClass.return_value
        instance.get_gps_data.return_value = {
            'lat': 46.0, 'lon': 7.0, 'timestamp': time.time(), 'satellites': 5, 'mode': 'real'
        }
        instance.is_inside_boundaries.return_value = True
        instance.last_known_position = instance.get_gps_data.return_value
        yield instance


@pytest.fixture
def mock_data_recorder():
    """Fixture for mocking DataRecorder."""
    with patch('Worx_GPS_Rec.DataRecorder', autospec=True) as MockClass:
        instance = MockClass.return_value
        yield instance


@pytest.fixture
def mock_problem_detector():
    """Fixture for mocking ProblemDetector."""
    with patch('Worx_GPS_Rec.ProblemDetector', autospec=True) as MockClass:
        instance = MockClass.return_value
        yield instance


@pytest.fixture
def mock_subprocess_call():
    """Fixture for mocking subprocess.call."""
    with patch('Worx_GPS_Rec.subprocess.call', autospec=True) as mock_call:
        yield mock_call


# --- Testklasse ---
class TestWorxGpsRec:

    @pytest.fixture
    def setup_instance(self,
                       mock_mqtt_handler,
                       mock_gps_handler,
                       mock_data_recorder,
                       mock_problem_detector,
                       mock_subprocess_call,
                       monkeypatch):
        """Sets mock instances on self and creates WorxGpsRec instance."""
        self.mock_mqtt_instance = mock_mqtt_handler
        self.mock_gps_instance = mock_gps_handler
        self.mock_recorder_instance = mock_data_recorder
        self.mock_detector_instance = mock_problem_detector
        self.mock_subprocess_call = mock_subprocess_call
        monkeypatch.setattr("Worx_GPS_Rec.REC_CONFIG", MOCK_REC_CONFIG, raising=False)
        self.worx_rec = WorxGpsRec()
        yield

    # --- Tests for on_mqtt_message ---
    def test_on_mqtt_message_command_start(self, setup_instance, caplog):
        """Testet die Verarbeitung des 'start'-Befehls via MQTT."""
        payload = "start"
        expected_method_call = "start_recording"
        method_args = []
        caplog.set_level(logging.DEBUG)
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = payload
        with patch.object(self.worx_rec, expected_method_call) as mocked_method:
            self.worx_rec.on_mqtt_message(mock_msg)
            if method_args:
                mocked_method.assert_called_once_with(*method_args)
            else:
                mocked_method.assert_called_once()
        assert f"Nachricht empfangen - Topic: '{self.mock_mqtt_instance.topic_control}', Payload: '{payload}'" in caplog.text

    @pytest.mark.parametrize("payload, expected_method_call, method_args", [
        ("start", "start_recording", []),
        ("stop", "stop_recording", []),
        ("problem", "send_problem_message", []),
        ("fakegps_on", "self.mock_gps_instance.change_gps_mode", ["fake_route"]),
        ("fakegps_off", "self.mock_gps_instance.change_gps_mode", ["real"]),
        ("start_route", "self.mock_gps_instance.change_gps_mode", ["fake_route"]),
        ("stop_route", "self.mock_gps_instance.change_gps_mode", ["fake_random"]),
        ("random_points", "self.mock_gps_instance.change_gps_mode", ["fake_random"]),
        ("shutdown", "self.mock_subprocess_call", [["sudo", "shutdown", "-h", "now"]]),
    ])
    def test_on_mqtt_message_commands_parametrized(self, setup_instance, payload, expected_method_call, method_args,
                                                   caplog):
        """Testet die Verarbeitung verschiedener Befehle via MQTT (Parametrized)."""
        caplog.set_level(logging.DEBUG)
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = payload
        if payload == "stop":
            self.worx_rec.is_recording = True

        if expected_method_call.startswith("self.mock_"):
            target_path = expected_method_call.split('.')
            if target_path[1] == "mock_subprocess_call":
                self.worx_rec.on_mqtt_message(mock_msg)
                self.mock_subprocess_call.assert_called_once_with(*method_args)
            else:
                target_obj = getattr(self, target_path[1])
                method_name = target_path[2]
                with patch.object(target_obj, method_name) as mocked_method:
                    self.worx_rec.on_mqtt_message(mock_msg)
                    if method_args:
                        mocked_method.assert_called_once_with(*method_args)
                    else:
                        mocked_method.assert_called_once()
        else:
            with patch.object(self.worx_rec, expected_method_call) as mocked_method:
                self.worx_rec.on_mqtt_message(mock_msg)
                if method_args:
                    mocked_method.assert_called_once_with(*method_args)
                else:
                    mocked_method.assert_called_once()
        assert f"Nachricht empfangen - Topic: '{self.mock_mqtt_instance.topic_control}', Payload: '{payload}'" in caplog.text

    def test_on_mqtt_message_stop_not_recording(self, setup_instance):
        """Testet, dass 'stop' ignoriert wird, wenn nicht aufgenommen wird."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = "stop"
        self.worx_rec.is_recording = False
        with patch.object(self.worx_rec, 'stop_recording') as mock_stop:
            self.worx_rec.on_mqtt_message(mock_msg)
            mock_stop.assert_not_called()

    def test_on_mqtt_message_unknown_command(self, setup_instance, caplog):
        """Testet die Reaktion auf einen unbekannten Befehl."""
        caplog.set_level(logging.WARNING)
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = "unknown_command"
        self.worx_rec.on_mqtt_message(mock_msg)
        self.mock_mqtt_instance.publish_message.assert_called_with(
            self.mock_mqtt_instance.topic_status, "error_command"
        )
        assert "Unbekannter Befehl empfangen: unknown_command" in caplog.text

    # --- Tests for other methods ---
    def test_worx_gps_rec_init(self, setup_instance):
        """Testet die Initialisierung von WorxGpsRec."""
        assert self.worx_rec.mqtt_handler is self.mock_mqtt_instance
        assert self.worx_rec.gps_handler is self.mock_gps_instance
        assert self.worx_rec.data_recorder is self.mock_recorder_instance
        assert self.worx_rec.problem_detector is self.mock_detector_instance
        assert not self.worx_rec.is_recording
        self.mock_mqtt_instance.set_message_callback.assert_called_once_with(self.worx_rec.on_mqtt_message)
        self.mock_mqtt_instance.connect.assert_called_once()

    def test_start_recording(self, setup_instance):
        """Testet die start_recording Methode."""
        self.worx_rec.is_recording = False
        self.worx_rec.start_recording()
        assert self.worx_rec.is_recording is True
        self.mock_recorder_instance.clear_buffer.assert_called_once()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "recording started"
        )

    def test_stop_recording(self, setup_instance):
        """Testet die stop_recording Methode."""
        self.worx_rec.is_recording = True
        self.worx_rec.stop_recording()
        assert self.worx_rec.is_recording is False
        self.mock_recorder_instance.send_buffer_data.assert_called_once()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "recording stopped"
        )

    def test_send_problem_message_gps_ok(self, setup_instance):
        """Testet send_problem_message bei verfügbaren GPS-Daten."""
        assert self.mock_gps_instance.last_known_position is not None
        gps_data = self.mock_gps_instance.last_known_position
        expected_payload = f"problem,{gps_data['lat']},{gps_data['lon']}"
        self.worx_rec.send_problem_message()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, expected_payload
        )

    def test_send_problem_message_gps_fail(self, setup_instance):
        """Testet send_problem_message, wenn keine GPS-Daten verfügbar sind."""
        self.mock_gps_instance.last_known_position = None
        self.worx_rec.send_problem_message()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "error_gps"
        )

    # --- Tests for main_loop ---
    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_recording_logic(self, mock_sleep, setup_instance):
        """Testet die Logik innerhalb der main_loop bei aktiver Aufnahme."""
        self.worx_rec.is_recording = True
        gps_data_in = {'lat': 46.1, 'lon': 7.1, 'timestamp': time.time(), 'satellites': 6, 'mode': 'real'}
        self.mock_gps_instance.get_gps_data.return_value = gps_data_in
        self.mock_gps_instance.is_inside_boundaries.return_value = True

        mock_sleep.side_effect = [None, None, StopTestLoopException("Stop Loop")]
        with pytest.raises(StopTestLoopException, match="Stop Loop"):
            self.worx_rec.main_loop()

        assert self.mock_gps_instance.get_gps_data.call_count == 3
        assert self.mock_gps_instance.is_inside_boundaries.call_count == 3
        self.mock_gps_instance.is_inside_boundaries.assert_called_with(gps_data_in['lat'], gps_data_in['lon'])
        assert self.mock_recorder_instance.add_gps_data.call_count == 3
        self.mock_recorder_instance.add_gps_data.assert_called_with(gps_data_in)
        assert self.mock_detector_instance.add_position.call_count == 3
        self.mock_detector_instance.add_position.assert_called_with(gps_data_in)
        expected_status = f"{gps_data_in['lat']},{gps_data_in['lon']},{gps_data_in['timestamp']},{gps_data_in['satellites']}"
        publish_calls = [
            c for c in self.mock_mqtt_instance.publish_message.call_args_list
            if c == call(self.mock_mqtt_instance.topic_status, expected_status)
        ]
        assert len(publish_calls) >= 1
        assert self.mock_gps_instance.check_assist_now.call_count == 3
        assert mock_sleep.call_count == 3  # Exception is raised during the 3rd call
        mock_sleep.assert_any_call(MOCK_REC_CONFIG["storage_interval"])

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_recording_outside_boundaries(self, mock_sleep, setup_instance):
        """Testet, dass Daten aurhalb der Grenzen nicht verarbeitet werden."""
        self.worx_rec.is_recording = True
        gps_data_out = {'lat': 1.0, 'lon': 1.0, 'timestamp': time.time(), 'satellites': 6, 'mode': 'real'}
        self.mock_gps_instance.get_gps_data.return_value = gps_data_out
        self.mock_gps_instance.is_inside_boundaries.return_value = False

        mock_sleep.side_effect = [None, None, StopTestLoopException("Stop Loop")]
        with pytest.raises(StopTestLoopException, match="Stop Loop"):
            self.worx_rec.main_loop()

        assert self.mock_gps_instance.get_gps_data.call_count == 3
        assert self.mock_gps_instance.is_inside_boundaries.call_count == 3
        self.mock_gps_instance.is_inside_boundaries.assert_called_with(gps_data_out['lat'], gps_data_out['lon'])
        self.mock_recorder_instance.add_gps_data.assert_not_called()
        self.mock_detector_instance.add_position.assert_not_called()
        expected_status = f"{gps_data_out['lat']},{gps_data_out['lon']},{gps_data_out['timestamp']},{gps_data_out['satellites']}"
        publish_calls = [
            c for c in self.mock_mqtt_instance.publish_message.call_args_list
            if c == call(self.mock_mqtt_instance.topic_status, expected_status)
        ]
        assert len(publish_calls) >= 1
        assert self.mock_gps_instance.check_assist_now.call_count == 3
        assert mock_sleep.call_count == 3  # Exception is raised during the 3rd call
        mock_sleep.assert_any_call(MOCK_REC_CONFIG["storage_interval"])

    # --- CORRECTED TEST ---
    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_status_sending_logic(self, mock_sleep, setup_instance):
        """Testet, dass Statusmeldungen auch gesendet werden, wenn nicht aufgenommen wird."""
        self.worx_rec.is_recording = False
        gps_data = {'lat': 46.2, 'lon': 7.2, 'timestamp': time.time(), 'satellites': 7, 'mode': 'real'}
        self.mock_gps_instance.get_gps_data.return_value = gps_data

        start_time = datetime.fromtimestamp(time.time())  # t=0
        # Define time points representing the START of each loop iteration
        # We need enough iterations to pass the 10-second mark relative to the first send (at t=0)
        # Let's simulate roughly 11 seconds using the storage interval
        num_steps = int(11 / MOCK_REC_CONFIG["storage_interval"]) + 2  # Add a couple extra steps
        simulated_times = [start_time + timedelta(seconds=i * MOCK_REC_CONFIG["storage_interval"]) for i in
                           range(num_steps)]
        # Example with interval 0.1: [t=0, t=0.1, t=0.2, ..., t=10.9, t=11.0, t=11.1] -> num_steps = 112

        call_index = 0

        def sleep_side_effect_with_time_jump(*args):
            nonlocal call_index, freezer
            # Check termination condition FIRST based on the *current* call_index
            # If call_index is 112 (len=112), raise exception
            if call_index >= len(simulated_times):
                raise StopTestLoopException("Stop Loop")

            # Move time to the start of the *next* iteration before sleep returns
            # This ensures the check at the beginning of the next loop uses the advanced time
            # If call_index is 0..111, move time to simulated_times[0..111]
            if call_index < len(simulated_times):
                freezer.move_to(simulated_times[call_index])

            call_index += 1  # Increment index (0 -> 1, ..., 111 -> 112)
            return None  # Allow sleep to complete (duration doesn't matter due to freeze_time)

        mock_sleep.side_effect = sleep_side_effect_with_time_jump

        with freeze_time(start_time) as freezer:
            with pytest.raises(StopTestLoopException, match="Stop Loop"):
                self.worx_rec.main_loop()

        # Assertions
        expected_status = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"
        publish_calls = [
            c for c in self.mock_mqtt_instance.publish_message.call_args_list
            if c == call(self.mock_mqtt_instance.topic_status, expected_status)
        ]

        # Check how many times the status should have been sent
        expected_sends = 0
        _last_send_time_sim = -10.0  # Simulate initial state
        # Iterate through the times representing the START of each loop iteration
        # The loop runs len(simulated_times) + 1 times
        loop_start_times = [start_time] + simulated_times  # Add the very first start time
        for i, t_step in enumerate(loop_start_times):
            # Stop simulating after the point where the exception would be raised
            if i > len(simulated_times):
                break
            current_time_sim = (t_step - start_time).total_seconds()
            if current_time_sim - _last_send_time_sim >= 10.0:
                expected_sends += 1
                _last_send_time_sim = current_time_sim

        assert len(publish_calls) == expected_sends  # Should be 2 in this specific setup

        self.mock_recorder_instance.add_gps_data.assert_not_called()
        self.mock_detector_instance.add_position.assert_not_called()

        # --- ADJUSTED CALL COUNT ASSERTIONS ---
        # Loop runs len(simulated_times) + 1 times before exception in sleep
        expected_loop_iterations = len(simulated_times) + 1
        assert self.mock_gps_instance.get_gps_data.call_count == expected_loop_iterations
        # Sleep is called at the end, exception happens during the last call
        assert mock_sleep.call_count == expected_loop_iterations
        assert self.mock_gps_instance.check_assist_now.call_count == expected_loop_iterations
        # --- END ADJUSTED CALL COUNT ASSERTIONS ---

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep', side_effect=StopTestLoopException("Stop Loop"))
    def test_main_loop_assist_now_check(self, mock_sleep, setup_instance):
        """Testet, dass check_assist_now in der Hauptschleife aufgerufen wird."""
        self.worx_rec.is_recording = False
        with pytest.raises(StopTestLoopException, match="Stop Loop"):
            self.worx_rec.main_loop()
        # Called once before the first sleep raises the exception
        self.mock_gps_instance.check_assist_now.assert_called_once()
