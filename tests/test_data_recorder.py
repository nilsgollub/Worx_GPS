import pytest
from unittest.mock import MagicMock, call, patch
import io


# Mock the dependency before importing the class
@pytest.fixture
def mock_mqtt_handler():
    handler = MagicMock()
    handler.topic_gps = "test/worx/gps"
    handler.publish_message = MagicMock()
    return handler


def test_data_recorder_init(mock_mqtt_handler):
    """Tests DataRecorder initialization."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    assert recorder.mqtt_handler == mock_mqtt_handler
    assert recorder.gps_data_buffer == []


def test_data_recorder_init_no_handler():
    """Tests that initialization fails without a handler."""
    from data_recorder import DataRecorder
    with pytest.raises(ValueError, match="MqttHandler instance is required."):
        DataRecorder(None)


def test_add_gps_data(mock_mqtt_handler):
    """Tests adding valid GPS data."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)
    assert recorder.gps_data_buffer == [data1, data2]


def test_add_gps_data_none_and_invalid(mock_mqtt_handler, caplog):
    """Tests adding None and invalid data types."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(None)
    recorder.add_gps_data("invalid string")  # Add invalid type

    assert recorder.gps_data_buffer == [data1]  # Only valid data added
    assert "Ignoriere ungültige GPS-Daten: invalid string" in caplog.text


def test_clear_buffer(mock_mqtt_handler):
    """Tests clearing the buffer."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)
    assert len(recorder.gps_data_buffer) == 1
    recorder.clear_buffer()
    assert recorder.gps_data_buffer == []


def test_send_buffer_data_non_empty(mock_mqtt_handler):
    """Tests sending data from a non-empty buffer."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}
    data3 = {'lat': 1.2, 'lon': 2.2}  # Missing keys test
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)
    recorder.add_gps_data(data3)

    recorder.send_buffer_data()

    expected_csv = "1.0,2.0,100,5\n1.1,2.1,101,6\n1.2,2.2,,\n"  # Note empty values for missing keys
    expected_marker = "-1"

    # Check that publish was called twice: once for data, once for marker
    assert mock_mqtt_handler.publish_message.call_count == 2
    # Check the calls explicitly
    calls = [
        call(mock_mqtt_handler.topic_gps, expected_csv),
        call(mock_mqtt_handler.topic_gps, expected_marker)
    ]
    mock_mqtt_handler.publish_message.assert_has_calls(calls)


def test_send_buffer_data_empty(mock_mqtt_handler):
    """Tests sending when the buffer is empty."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.clear_buffer()  # Ensure buffer is empty

    recorder.send_buffer_data()

    expected_marker = "-1"

    # Check that publish was called only once for the marker
    mock_mqtt_handler.publish_message.assert_called_once_with(
        mock_mqtt_handler.topic_gps, expected_marker
    )


def test_send_buffer_data_no_topic(mock_mqtt_handler, caplog):
    """Tests sending when the handler is missing the topic_gps attribute."""
    from data_recorder import DataRecorder
    # Remove the attribute for this test
    del mock_mqtt_handler.topic_gps
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.add_gps_data({'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5})

    recorder.send_buffer_data()

    # Check that publish was not called
    mock_mqtt_handler.publish_message.assert_not_called()
    # Check for error log
    assert "MQTT handler hat kein 'topic_gps' Attribut" in caplog.text


@patch('io.StringIO.write', side_effect=IOError("String IO Error"))
def test_send_buffer_data_format_error(mock_stringio_write, mock_mqtt_handler, caplog):
    """Tests handling errors during CSV formatting."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)

    recorder.send_buffer_data()

    # Check that publish was still called for the end marker
    mock_mqtt_handler.publish_message.assert_called_once_with(
        mock_mqtt_handler.topic_gps, "-1"
    )
    # Check for error log during formatting
    assert "Fehler beim Formatieren des Datenpunkts" in caplog.text
    assert "String IO Error" in caplog.text


def test_send_buffer_data_publish_error(mock_mqtt_handler, caplog):
    """Tests handling errors during MQTT publish."""
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)

    # Simulate publish error
    mock_mqtt_handler.publish_message.side_effect = [Exception("MQTT Broker down"),
                                                     None]  # Error on first call (data), success on second (marker)

    recorder.send_buffer_data()

    # Check publish was attempted twice
    assert mock_mqtt_handler.publish_message.call_count == 2
    # Check for error log
    assert "Fehler beim Senden der Daten oder des End-Markers via MQTT: MQTT Broker down" in caplog.text
