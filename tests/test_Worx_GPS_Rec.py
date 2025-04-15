# tests/test_Worx_GPS_Rec.py (Full Version - Explicit Fixtures + Parametrize)
import pytest
from unittest.mock import patch, MagicMock, call, ANY
from freezegun import freeze_time
import time
from datetime import datetime, timedelta
import logging

# Importiere die zu testende Klasse und die verwendeten Konfigurationen/Klassen
from Worx_GPS_Rec import WorxGpsRec
from config import REC_CONFIG as REAL_REC_CONFIG

# Mock-Konfigurationen
MOCK_REC_CONFIG = REAL_REC_CONFIG.copy()
MOCK_REC_CONFIG["test_mode"] = False
MOCK_REC_CONFIG["storage_interval"] = 0.1


# --- Explicit Fixtures for Mocks ---

@pytest.fixture
def mock_mqtt_handler():
    """Fixture for mocking MqttHandler."""
    with patch('Worx_GPS_Rec.MqttHandler', autospec=True) as MockClass:
        instance = MockClass.return_value
        instance.topic_control = "mock/worx/control"
        instance.topic_status = "mock/worx/status"
        instance.topic_gps = "mock/worx/gps"
        # Add other necessary default configurations here if needed
        yield instance  # Yield the mock instance


@pytest.fixture
def mock_gps_handler():
    """Fixture for mocking GpsHandler."""
    with patch('Worx_GPS_Rec.GpsHandler', autospec=True) as MockClass:
        instance = MockClass.return_value
        # Default behavior
        instance.get_gps_data.return_value = {
            'lat': 46.0, 'lon': 7.0, 'timestamp': time.time(), 'satellites': 5, 'mode': 'real'
        }
        instance.is_inside_boundaries.return_value = True
        instance.last_known_position = instance.get_gps_data.return_value
        # Add other necessary default configurations here if needed
        yield instance  # Yield the mock instance


@pytest.fixture
def mock_data_recorder():
    """Fixture for mocking DataRecorder."""
    with patch('Worx_GPS_Rec.DataRecorder', autospec=True) as MockClass:
        instance = MockClass.return_value
        # Add other necessary default configurations here if needed
        yield instance  # Yield the mock instance


@pytest.fixture
def mock_problem_detector():
    """Fixture for mocking ProblemDetector."""
    with patch('Worx_GPS_Rec.ProblemDetector', autospec=True) as MockClass:
        instance = MockClass.return_value
        # Add other necessary default configurations here if needed
        yield instance  # Yield the mock instance


@pytest.fixture
def mock_subprocess_call():
    """Fixture for mocking subprocess.call."""
    with patch('Worx_GPS_Rec.subprocess.call', autospec=True) as mock_call:
        yield mock_call  # Yield the mock function itself


# --- Testklasse ---
# NO @patch decorators on the class anymore
class TestWorxGpsRec:  # Renamed back to original class name

    @pytest.fixture
    # NO autouse=True
    # Accepts the EXPLICIT mock fixtures defined above
    def setup_instance(self,
                       mock_mqtt_handler,  # Request the explicit fixture
                       mock_gps_handler,  # Request the explicit fixture
                       mock_data_recorder,  # Request the explicit fixture
                       mock_problem_detector,  # Request the explicit fixture
                       mock_subprocess_call,  # Request the explicit fixture
                       monkeypatch):
        """Sets mock instances on self and creates WorxGpsRec instance."""

        # Assign the mock instances from the fixtures to self
        self.mock_mqtt_instance = mock_mqtt_handler
        self.mock_gps_instance = mock_gps_handler
        self.mock_recorder_instance = mock_data_recorder
        self.mock_detector_instance = mock_problem_detector
        self.mock_subprocess_call = mock_subprocess_call

        # Patch REC_CONFIG im Zielmodul
        monkeypatch.setattr("Worx_GPS_Rec.REC_CONFIG", MOCK_REC_CONFIG, raising=False)

        # Instanz der zu testenden Klasse erstellen
        # __init__ will now use the mocked classes provided by the fixtures' patches
        self.worx_rec = WorxGpsRec()
        yield  # Allow the test to run

    # --- Test für den 'start'-Befehl (ohne @parametrize) ---
    # This test might be redundant now with the parametrized one, but keep it for now
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

    # --- Full @parametrize Test ---
    @pytest.mark.parametrize("payload, expected_method_call, method_args", [
        ("start", "start_recording", []),
        ("stop", "stop_recording", []),
        ("problem", "send_problem_message", []),
        ("fakegps_on", "self.mock_gps_instance.change_gps_mode", ["fake_route"]),
        ("fakegps_off", "self.mock_gps_instance.change_gps_mode", ["real"]),
        ("start_route", "self.mock_gps_instance.change_gps_mode", ["fake_route"]),
        ("stop_route", "self.mock_gps_instance.change_gps_mode", ["fake_random"]),
        ("random_points", "self.mock_gps_instance.change_gps_mode", ["fake_random"]),
        ("shutdown", "self.mock_subprocess_call", [["sudo", "shutdown", "-h", "now"]]),  # Check mock directly
    ])
    # Test method now explicitly requests the setup_instance fixture AND parametrize args
    def test_on_mqtt_message_commands_parametrized(self, setup_instance, payload, expected_method_call, method_args,
                                                   caplog):
        """Testet die Verarbeitung verschiedener Befehle via MQTT (Parametrized)."""
        caplog.set_level(logging.DEBUG)
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = payload

        # --- Add logic for 'stop' case ---
        if payload == "stop":
            # Ensure recording is True for stop to be called in the actual code
            self.worx_rec.is_recording = True
        # --- End logic for 'stop' case ---

        # Check if the target is a mock attribute or an instance method
        if expected_method_call.startswith("self.mock_"):
            target_path = expected_method_call.split('.')
            # Check if it's the direct subprocess mock
            if target_path[1] == "mock_subprocess_call":
                self.worx_rec.on_mqtt_message(mock_msg)
                self.mock_subprocess_call.assert_called_once_with(*method_args)
            else:  # Assume it's a method on a mock instance (like gps_handler)
                target_obj = getattr(self, target_path[1])  # e.g., self.mock_gps_instance
                method_name = target_path[2]
                with patch.object(target_obj, method_name) as mocked_method:
                    self.worx_rec.on_mqtt_message(mock_msg)
                    if method_args:
                        mocked_method.assert_called_once_with(*method_args)
                    else:
                        mocked_method.assert_called_once()
        # Otherwise, assume it's a method on the WorxGpsRec instance
        else:
            with patch.object(self.worx_rec, expected_method_call) as mocked_method:
                self.worx_rec.on_mqtt_message(mock_msg)
                if method_args:
                    mocked_method.assert_called_once_with(*method_args)
                else:
                    mocked_method.assert_called_once()

        assert f"Nachricht empfangen - Topic: '{self.mock_mqtt_instance.topic_control}', Payload: '{payload}'" in caplog.text

    # --- All other original test methods ---
    # They now need to request 'setup_instance' fixture

    def test_worx_gps_rec_init(self, setup_instance, mock_mqtt_handler, mock_gps_handler, mock_data_recorder,
                               mock_problem_detector, mock_subprocess_call):
        """Testet die Initialisierung von WorxGpsRec."""
        # Check that the mocks were called during __init__ (via the fixtures)
        # The fixtures use patch, so we check the original mock classes
        # Note: This check might be less reliable now, focus on instance attributes
        # MockMqttHandlerClass = WorxGpsRec.MqttHandler # Get the potentially mocked class
        # MockMqttHandlerClass.assert_called_once_with(False) # Check class call

        # Check instance attributes set in setup_instance
        assert self.worx_rec.mqtt_handler is self.mock_mqtt_instance
        assert self.worx_rec.gps_handler is self.mock_gps_instance
        assert self.worx_rec.data_recorder is self.mock_recorder_instance
        assert self.worx_rec.problem_detector is self.mock_detector_instance
        assert not self.worx_rec.is_recording
        # Check calls made during __init__ on the mock instances
        self.mock_mqtt_instance.set_message_callback.assert_called_once_with(self.worx_rec.on_mqtt_message)
        self.mock_mqtt_instance.connect.assert_called_once()

    def test_on_mqtt_message_stop_not_recording(self, setup_instance):
        """Testet, dass 'stop' ignoriert wird, wenn nicht aufgenommen wird."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = "stop"
        self.worx_rec.is_recording = False  # Ensure state
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

    def test_start_recording(self, setup_instance):
        """Testet die start_recording Methode."""
        self.worx_rec.is_recording = False  # Ensure state
        self.worx_rec.start_recording()
        assert self.worx_rec.is_recording is True
        self.mock_recorder_instance.clear_buffer.assert_called_once()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "recording started"
        )

    def test_stop_recording(self, setup_instance):
        """Testet die stop_recording Methode."""
        self.worx_rec.is_recording = True  # Ensure state
        self.worx_rec.stop_recording()
        assert self.worx_rec.is_recording is False
        self.mock_recorder_instance.send_buffer_data.assert_called_once()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "recording stopped"
        )

    def test_send_problem_message_gps_ok(self, setup_instance):
        """Testet send_problem_message bei verfügbaren GPS-Daten."""
        # Ensure last_known_position is set by the fixture
        assert self.mock_gps_instance.last_known_position is not None
        gps_data = self.mock_gps_instance.last_known_position
        expected_payload = f"problem,{gps_data['lat']},{gps_data['lon']}"
        self.worx_rec.send_problem_message()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, expected_payload
        )

    def test_send_problem_message_gps_fail(self, setup_instance):
        """Testet send_problem_message, wenn keine GPS-Daten verfügbar sind."""
        self.mock_gps_instance.last_known_position = None  # Override fixture default
        self.worx_rec.send_problem_message()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "error_gps"
        )

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_recording_logic(self, mock_sleep, setup_instance):  # Add setup_instance
        """Testet die Logik innerhalb der main_loop bei aktiver Aufnahme."""
        self.worx_rec.is_recording = True
        gps_data_in = {'lat': 46.1, 'lon': 7.1, 'timestamp': time.time(), 'satellites': 6, 'mode': 'real'}
        self.mock_gps_instance.get_gps_data.return_value = gps_data_in
        self.mock_gps_instance.is_inside_boundaries.return_value = True
        # Simulate loop running twice then stopping
        self.mock_gps_instance.get_gps_data.side_effect = [gps_data_in, gps_data_in, Exception("Stop Loop")]
        with pytest.raises(Exception, match="Stop Loop"):
            self.worx_rec.main_loop()

        # Assertions
        assert self.mock_gps_instance.get_gps_data.call_count == 3  # Called 3 times before exception
        # is_inside_boundaries called for the first two valid points
        assert self.mock_gps_instance.is_inside_boundaries.call_count == 2
        self.mock_gps_instance.is_inside_boundaries.assert_called_with(gps_data_in['lat'],
                                                                       gps_data_in['lon'])  # Check last call args
        # add_gps_data and add_position called for the first two valid points
        assert self.mock_recorder_instance.add_gps_data.call_count == 2
        self.mock_recorder_instance.add_gps_data.assert_called_with(gps_data_in)
        assert self.mock_detector_instance.add_position.call_count == 2
        self.mock_detector_instance.add_position.assert_called_with(gps_data_in)

        # Status message sending depends on the 10-second interval, check if it was called at least once
        expected_status = f"{gps_data_in['lat']},{gps_data_in['lon']},{gps_data_in['timestamp']},{gps_data_in['satellites']}"
        assert call(self.mock_mqtt_instance.topic_status,
                    expected_status) in self.mock_mqtt_instance.publish_message.call_args_list

        # check_assist_now called in each iteration before exception
        assert self.mock_gps_instance.check_assist_now.call_count == 2
        # sleep called in each iteration before exception
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(MOCK_REC_CONFIG["storage_interval"])

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_recording_outside_boundaries(self, mock_sleep, setup_instance):  # Add setup_instance
        """Testet, dass Daten außerhalb der Grenzen nicht verarbeitet werden."""
        self.worx_rec.is_recording = True
        gps_data_out = {'lat': 1.0, 'lon': 1.0, 'timestamp': time.time(), 'satellites': 6, 'mode': 'real'}
        self.mock_gps_instance.get_gps_data.return_value = gps_data_out
        self.mock_gps_instance.is_inside_boundaries.return_value = False  # Simulate outside
        # Simulate loop running twice then stopping
        self.mock_gps_instance.get_gps_data.side_effect = [gps_data_out, gps_data_out, Exception("Stop Loop")]
        with pytest.raises(Exception, match="Stop Loop"):
            self.worx_rec.main_loop()

        # Assertions
        assert self.mock_gps_instance.get_gps_data.call_count == 3
        assert self.mock_gps_instance.is_inside_boundaries.call_count == 2
        self.mock_gps_instance.is_inside_boundaries.assert_called_with(gps_data_out['lat'], gps_data_out['lon'])
        # Data should NOT be added
        self.mock_recorder_instance.add_gps_data.assert_not_called()
        self.mock_detector_instance.add_position.assert_not_called()

        # Status message should still be sent
        expected_status = f"{gps_data_out['lat']},{gps_data_out['lon']},{gps_data_out['timestamp']},{gps_data_out['satellites']}"
        assert call(self.mock_mqtt_instance.topic_status,
                    expected_status) in self.mock_mqtt_instance.publish_message.call_args_list

        assert self.mock_gps_instance.check_assist_now.call_count == 2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(MOCK_REC_CONFIG["storage_interval"])

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_status_sending_logic(self, mock_sleep, setup_instance):  # Add setup_instance
        """Testet, dass Statusmeldungen auch gesendet werden, wenn nicht aufgenommen wird."""
        self.worx_rec.is_recording = False
        gps_data = {'lat': 46.2, 'lon': 7.2, 'timestamp': time.time(), 'satellites': 7, 'mode': 'real'}
        self.mock_gps_instance.get_gps_data.return_value = gps_data

        start_time = datetime.fromtimestamp(time.time())
        # Simulate time passing over the 10-second interval
        simulated_times = [start_time, start_time + timedelta(seconds=5), start_time + timedelta(seconds=11)]
        call_index = 0

        def sleep_side_effect(*args):
            nonlocal call_index, freezer
            call_index += 1
            if call_index < len(simulated_times):
                freezer.move_to(simulated_times[call_index])
            else:
                raise Exception("Stop Loop")

        mock_sleep.side_effect = sleep_side_effect

        with freeze_time(start_time) as freezer:
            with pytest.raises(Exception, match="Stop Loop"):
                self.worx_rec.main_loop()

        # Assertions
        expected_status = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"
        publish_calls = [
            c for c in self.mock_mqtt_instance.publish_message.call_args_list
            if c == call(self.mock_mqtt_instance.topic_status, expected_status)
        ]
        # Should be sent at the start (t=0) and after 11 seconds
        assert len(publish_calls) == 2

        # No recording, so these should not be called
        self.mock_recorder_instance.add_gps_data.assert_not_called()
        self.mock_detector_instance.add_position.assert_not_called()

        assert self.mock_gps_instance.get_gps_data.call_count == 3
        assert mock_sleep.call_count == 3
        assert self.mock_gps_instance.check_assist_now.call_count == 3

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep', side_effect=Exception("Stop Loop"))
    def test_main_loop_assist_now_check(self, mock_sleep, setup_instance):  # Add setup_instance
        """Testet, dass check_assist_now in der Hauptschleife aufgerufen wird."""
        self.worx_rec.is_recording = False
        with pytest.raises(Exception, match="Stop Loop"):
            self.worx_rec.main_loop()
        # Should be called once before the loop stops
        self.mock_gps_instance.check_assist_now.assert_called_once()
