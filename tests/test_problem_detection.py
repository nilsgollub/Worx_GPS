import pytest
from unittest.mock import MagicMock, patch
from collections import deque
import time
from freezegun import freeze_time


# Mock the dependency
@pytest.fixture
def mock_mqtt_handler():
    handler = MagicMock()
    handler.topic_control = "worx/control_test"
    handler.publish_message = MagicMock()
    return handler


@pytest.fixture
def problem_detector(mock_mqtt_handler):
    from problem_detection import ProblemDetector
    # Use a shorter threshold for easier testing
    return ProblemDetector(mock_mqtt_handler, threshold_time=5)


def test_problem_detector_init(mock_mqtt_handler):
    """Tests ProblemDetector initialization."""
    from problem_detection import ProblemDetector
    threshold = 15
    detector = ProblemDetector(mock_mqtt_handler, threshold_time=threshold)
    assert detector.mqtt_handler == mock_mqtt_handler
    assert detector.threshold_time == threshold
    assert isinstance(detector.position_history, deque)
    assert detector.position_history.maxlen == 10
    assert detector.last_problem_time == 0


def test_add_position(problem_detector):
    """Tests adding a valid position."""
    with patch.object(problem_detector, 'check_for_problem') as mock_check:
        gps_data = {"lat": 1.0, "lon": 2.0, "timestamp": 100.0}
        problem_detector.add_position(gps_data)
        assert len(problem_detector.position_history) == 1
        assert problem_detector.position_history[0] == (1.0, 2.0, 100.0)
        mock_check.assert_called_once()


def test_add_position_none(problem_detector):
    """Tests adding None as position."""
    with patch.object(problem_detector, 'check_for_problem') as mock_check:
        problem_detector.add_position(None)
        assert len(problem_detector.position_history) == 0
        mock_check.assert_not_called()  # Should not check if no data added


@freeze_time("2023-10-27 10:00:00")
def test_check_for_problem_no_problem_short_history(problem_detector):
    """Tests check when history is too short."""
    with patch.object(problem_detector, 'report_problem') as mock_report:
        problem_detector.position_history.extend([
            (1.0, 1.0, time.time() - 4),
            (1.0, 1.0, time.time() - 2),
            (1.0, 1.0, time.time()),
        ])  # Only 3 positions
        problem_detector.check_for_problem()
        mock_report.assert_not_called()


@freeze_time("2023-10-27 10:00:00")
def test_check_for_problem_no_problem_moving(problem_detector):
    """Tests check when the device is moving."""
    with patch.object(problem_detector, 'report_problem') as mock_report:
        problem_detector.position_history.extend([
            (1.0, 1.0, time.time() - 6),  # More than threshold_time=5
            (1.1, 1.0, time.time() - 4),
            (1.2, 1.0, time.time() - 2),
            (1.3, 1.0, time.time() - 1),
            (1.4, 1.0, time.time()),  # Position changed
        ])
        problem_detector.check_for_problem()
        mock_report.assert_not_called()


@freeze_time("2023-10-27 10:00:00")
def test_check_for_problem_no_problem_short_time(problem_detector):
    """Tests check when device is stationary but for less than threshold time."""
    with patch.object(problem_detector, 'report_problem') as mock_report:
        problem_detector.position_history.extend([
            (1.0, 1.0, time.time() - 4),  # Less than threshold_time=5
            (1.0, 1.0, time.time() - 3),
            (1.0, 1.0, time.time() - 2),
            (1.0, 1.0, time.time() - 1),
            (1.0, 1.0, time.time()),  # Same position
        ])
        problem_detector.check_for_problem()
        mock_report.assert_not_called()


@freeze_time("2023-10-27 10:00:00")
def test_check_for_problem_detected(problem_detector):
    """Tests check when a problem is detected (stationary for long enough)."""
    with patch.object(problem_detector, 'report_problem') as mock_report:
        start_time = time.time()
        problem_detector.position_history.extend([
            (1.0, 1.0, start_time - 6),  # More than threshold_time=5
            (1.0, 1.0, start_time - 4),
            (1.0, 1.0, start_time - 2),
            (1.0, 1.0, start_time - 1),
            (1.0, 1.0, start_time),  # Same position
        ])
        problem_detector.check_for_problem()
        # Problem should be reported with the last position
        mock_report.assert_called_once_with((1.0, 1.0, start_time))


@freeze_time("2023-10-27 10:00:00")
def test_check_for_problem_cooldown(problem_detector):
    """Tests the 60-second cooldown between problem reports."""
    with patch.object(problem_detector, 'report_problem') as mock_report:
        start_time = time.time()
        # First problem
        problem_detector.position_history.extend([
            (1.0, 1.0, start_time - 6),
            (1.0, 1.0, start_time - 4),
            (1.0, 1.0, start_time - 2),
            (1.0, 1.0, start_time - 1),
            (1.0, 1.0, start_time),
        ])
        problem_detector.check_for_problem()
        mock_report.assert_called_once_with((1.0, 1.0, start_time))
        assert problem_detector.last_problem_time == start_time  # Check cooldown timer started

        # Simulate time passing (less than 60s) and another check
        mock_report.reset_mock()
        with freeze_time("2023-10-27 10:00:30"):  # Only 30 seconds later
            # Add a new point to trigger check again (or call directly)
            new_time = time.time()
            problem_detector.add_position({"lat": 1.0, "lon": 1.0, "timestamp": new_time})
            # Check should run, but report should be skipped due to cooldown
            mock_report.assert_not_called()

        # Simulate time passing (more than 60s) and another check
        mock_report.reset_mock()
        with freeze_time("2023-10-27 10:01:01"):  # 61 seconds after first report
            new_time = time.time()
            # Add another point, still stationary
            problem_detector.add_position({"lat": 1.0, "lon": 1.0, "timestamp": new_time})
            # Check should run, and report should happen now
            mock_report.assert_called_once_with((1.0, 1.0, new_time))
            assert problem_detector.last_problem_time == new_time  # Cooldown timer reset


def test_report_problem(problem_detector, mock_mqtt_handler):
    """Tests the report_problem method."""
    problem_position = (1.23, 4.56, 12345.67)  # Example position tuple
    problem_detector.report_problem(problem_position)

    # Check that the correct message was published to the control topic
    mock_mqtt_handler.publish_message.assert_called_once_with(
        mock_mqtt_handler.topic_control, "problem"
    )
