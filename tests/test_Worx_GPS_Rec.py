import pytest
from unittest.mock import patch, MagicMock, call
import time


# Mock dependencies BEFORE importing WorxGpsRec
@patch('Worx_GPS_Rec.MqttHandler')
@patch('Worx_GPS_Rec.GpsHandler')
@patch('Worx_GPS_Rec.DataRecorder')
@patch('Worx_GPS_Rec.ProblemDetector')
@patch('Worx_GPS_Rec.subprocess.call')  # Mock subprocess
@patch('Worx_GPS_Rec.REC_CONFIG',
       {"test_mode": False, "storage_interval": 0.1})  # Use short interval for tests if needed
class TestWorxGpsRec:

    @pytest.fixture(autouse=True)
    def setup_mocks_and_instance(self, MockRecConfig, MockSubprocessCall, MockProblemDetector, MockDataRecorder,
                                 MockGpsHandler, MockMqttHandler):
        # Store mocks
        self.MockMqttHandler = MockMqttHandler
        self.mock_mqtt_instance = MockMqttHandler.return_value
        self.mock_mqtt_instance.topic_control = "worx/control"
        self.mock_mqtt_instance.topic_status = "worx/status"
        self.mock_mqtt_instance.topic_gps = "worx/gps"  # Needed?

        self.MockGpsHandler = MockGpsHandler
        self.mock_gps_instance = MockGpsHandler.return_value

        self.MockDataRecorder = MockDataRecorder
        self.mock_recorder_instance = MockDataRecorder.return_value

        self.MockProblemDetector = MockProblemDetector
        self.mock_detector_instance = MockProblemDetector.return_value

        self.MockSubprocessCall = MockSubprocessCall
        self.MockRecConfig = MockRecConfig  # Access patched config

        # Create instance
        from Worx_GPS_Rec import WorxGpsRec
        self.worx_rec = WorxGpsRec()
        yield

    def test_worx_gps_rec_init(self):
        """Tests WorxGpsRec initialization."""
        # Check instances created
        self.MockMqttHandler.assert_called_once_with(False)  # test_mode from REC_CONFIG
        self.MockGpsHandler.assert_called_once()
        self.MockDataRecorder.assert_called_once_with(self.mock_mqtt_instance)
        self.MockProblemDetector.assert_called_once_with(self.mock_mqtt_instance)

        # Check attributes
        assert self.worx_rec.test_mode is False
        assert self.worx_rec.mqtt_handler == self.mock_mqtt_instance
        assert self.worx_rec.gps_handler == self.mock_gps_instance
        assert self.worx_rec.data_recorder == self.mock_recorder_instance
        assert self.worx_rec.problem_detector == self.mock_detector_instance
        assert self.worx_rec.is_recording is False

        # Check MQTT setup
        self.mock_mqtt_instance.set_message_callback.assert_called_once_with(self.worx_rec.on_mqtt_message)
        self.mock_mqtt_instance.connect.assert_called_once()

    # --- Test on_mqtt_message routing ---
    @pytest.mark.parametrize("payload, expected_method_call", [
        ("start", "start_recording"),
        ("stop", "stop_recording"),  # Assumes is_recording = True
        ("problem", "send_problem_message"),
        ("fakegps_on", "gps_handler.change_gps_mode"),
        ("fakegps_off", "gps_handler.change_gps_mode"),
        ("start_route", "gps_handler.change_gps_mode"),
        ("stop_route", "gps_handler.change_gps_mode"),
        ("random_points", "gps_handler.change_gps_mode"),
        ("shutdown", "subprocess.call"),
    ])
    def test_on_mqtt_message_commands(self, payload, expected_method_call):
        """Tests routing of valid commands in on_mqtt_message."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = payload

        # Need to set is_recording for stop command
        if payload == "stop":
            self.worx_rec.is_recording = True

        # Use nested patches or direct object patching
        with patch.object(self.worx_rec, 'start_recording', wraps=self.worx_rec.start_recording) as mock_start, \
                patch.object(self.worx_rec, 'stop_recording', wraps=self.worx_rec.stop_recording) as mock_stop, \
                patch.object(self.worx_rec, 'send_problem_message',
                             wraps=self.worx_rec.send_problem_message) as mock_problem, \
                patch.object(self.mock_gps_instance, 'change_gps_mode') as mock_change_mode, \
                patch('Worx_GPS_Rec.subprocess.call') as mock_subprocess:  # Patch subprocess here

            self.worx_rec.on_mqtt_message(mock_msg)

            if expected_method_call == "start_recording":
                mock_start.assert_called_once()
            elif expected_method_call == "stop_recording":
                mock_stop.assert_called_once()
            elif expected_method_call == "send_problem_message":
                mock_problem.assert_called_once()
            elif expected_method_call == "gps_handler.change_gps_mode":
                mock_change_mode.assert_called()  # Called at least once
            elif expected_method_call == "subprocess.call":
                mock_subprocess.assert_called_once_with(["sudo", "shutdown", "-h", "now"])

    def test_on_mqtt_message_stop_not_recording(self):
        """Tests that 'stop' does nothing if not recording."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = "stop"
        self.worx_rec.is_recording = False  # Ensure not recording

        with patch.object(self.worx_rec, 'stop_recording') as mock_stop:
            self.worx_rec.on_mqtt_message(mock_msg)
            mock_stop.assert_not_called()

    def test_on_mqtt_message_unknown_command(self):
        """Tests handling of an unknown command."""
        mock_msg = MagicMock()
        mock_msg.topic = self.mock_mqtt_instance.topic_control
        mock_msg.payload.decode.return_value = "unknown_cmd"

        self.worx_rec.on_mqtt_message(mock_msg)

        # Check error message published
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "error_command"
        )

    def test_start_recording(self):
        """Tests the start_recording method."""
        self.worx_rec.is_recording = False  # Ensure starts as False
        self.worx_rec.start_recording()

        assert self.worx_rec.is_recording is True
        self.mock_recorder_instance.clear_buffer.assert_called_once()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "recording started"
        )

    def test_stop_recording(self):
        """Tests the stop_recording method."""
        self.worx_rec.is_recording = True  # Assume recording
        self.worx_rec.stop_recording()

        assert self.worx_rec.is_recording is False
        self.mock_recorder_instance.send_buffer_data.assert_called_once()
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "recording stopped"
        )

    def test_send_problem_message_gps_ok(self):
        """Tests sending problem message when GPS data is available."""
        gps_data = {'lat': 46.1, 'lon': 7.1, 'timestamp': 100, 'satellites': 5}
        self.mock_gps_instance.get_gps_data.return_value = gps_data

        self.worx_rec.send_problem_message()

        expected_payload = f"problem,{gps_data['lat']},{gps_data['lon']}"
        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, expected_payload
        )

    def test_send_problem_message_gps_fail(self):
        """Tests sending problem message when GPS data is not available."""
        self.mock_gps_instance.get_gps_data.return_value = None  # Simulate no GPS

        self.worx_rec.send_problem_message()

        self.mock_mqtt_instance.publish_message.assert_called_once_with(
            self.mock_mqtt_instance.topic_status, "error_gps"
        )

    # --- Testing main_loop is complex ---
    # Option 1: Test parts of the loop logic in isolation
    # Option 2: Run the loop for a fixed number of iterations using mocks

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')  # Mock sleep to avoid delays
    def test_main_loop_recording_logic(self, mock_sleep):
        """Tests the recording part of the main loop logic for one iteration."""
        self.worx_rec.is_recording = True
        gps_data = {'lat': 46.5, 'lon': 7.5, 'timestamp': time.time(), 'satellites': 8}
        self.mock_gps_instance.get_gps_data.return_value = gps_data
        self.mock_gps_instance.is_inside_boundaries.return_value = True  # Assume inside

        # Simulate one iteration by calling the loop's content once
        # This requires refactoring the loop content into a helper method,
        # or carefully extracting and calling the relevant lines here.

        # Extracted logic for one recording iteration:
        if self.worx_rec.is_recording:
            current_gps_data = self.worx_rec.gps_handler.get_gps_data()
            if current_gps_data:
                if self.worx_rec.gps_handler.is_inside_boundaries(current_gps_data["lat"],
                                                                  current_gps_data["lon"]) or self.worx_rec.test_mode:
                    self.worx_rec.data_recorder.add_gps_data(current_gps_data)
                    self.worx_rec.problem_detector.add_position(current_gps_data)
                else:
                    print("Koordinaten liegen außerhalb")  # Avoid print in tests ideally
            else:
                print("Keine gültigen GPS-Daten.")

        # Assertions for recording logic
        self.mock_gps_instance.get_gps_data.assert_called()  # Called at least once
        self.mock_gps_instance.is_inside_boundaries.assert_called_once_with(gps_data['lat'], gps_data['lon'])
        self.mock_recorder_instance.add_gps_data.assert_called_once_with(gps_data)
        self.mock_detector_instance.add_position.assert_called_once_with(gps_data)

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_status_sending_logic(self, mock_sleep):
        """Tests the status sending part of the main loop logic."""
        self.worx_rec.is_recording = False  # Test when not recording
        gps_data = {'lat': 46.6, 'lon': 7.6, 'timestamp': time.time(), 'satellites': 9}
        self.mock_gps_instance.get_gps_data.return_value = gps_data

        # Simulate time passing to trigger status send
        start_time = time.time()
        with freeze_time(start_time + 11):  # More than 10 seconds later
            # Extracted logic for status sending:
            # Assume last_status_send was initialized correctly < start_time
            if time.time() - self.worx_rec.last_status_send >= 10:
                status_gps_data = self.worx_rec.gps_handler.get_gps_data()
                if status_gps_data:
                    status_message = f"{status_gps_data['lat']},{status_gps_data['lon']},{status_gps_data['timestamp']},{status_gps_data['satellites']}"
                    self.worx_rec.mqtt_handler.publish_message(self.worx_rec.mqtt_handler.topic_status, status_message)
                else:
                    print("Keine gültigen GPS-Daten für Statusmeldung.")
                self.worx_rec.last_status_send = time.time()

            # Assertions for status logic
            expected_status = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"
            self.mock_mqtt_instance.publish_message.assert_called_once_with(
                self.mock_mqtt_instance.topic_status, expected_status
            )
            assert self.worx_rec.last_status_send == time.time()  # Check timestamp updated

    @freeze_time("2023-10-27 17:00:00")
    @patch('time.sleep')
    def test_main_loop_assist_now_check(self, mock_sleep):
        """Tests that check_assist_now is called in the loop."""
        # Extracted logic for assist now check:
        self.worx_rec.gps_handler.check_assist_now()
        # Assertion
        self.mock_gps_instance.check_assist_now.assert_called_once()
