# tests/test_data_recorder.py
import pytest
from unittest.mock import patch, MagicMock, call
import logging
import io  # Importiere io

# Importiere die zu testende Klasse
from data_recorder import DataRecorder


# --- Fixture für einen Mock MQTT Handler ---
@pytest.fixture
def mock_mqtt_handler():
    """Erstellt einen Mock für den MqttHandler."""
    handler = MagicMock()
    handler.topic_gps = "mock/worx/gps"  # Setze das erwartete Topic-Attribut
    # Füge eine Mock-Implementierung für is_connected hinzu (wird intern von publish_message geprüft)
    handler.is_connected.return_value = True
    return handler


# --- Tests für DataRecorder ---

def test_data_recorder_init(mock_mqtt_handler):
    """Testet die Initialisierung des DataRecorders."""
    recorder = DataRecorder(mock_mqtt_handler)
    assert recorder.mqtt_handler is mock_mqtt_handler
    assert recorder.gps_data_buffer == []
    # Optional: Prüfe, ob Logging aufgerufen wurde (wenn gemockt)


def test_data_recorder_init_no_handler():
    """Testet, dass ein Fehler ausgelöst wird, wenn kein Handler übergeben wird."""
    with pytest.raises(ValueError, match="MqttHandler instance is required."):
        DataRecorder(None)


def test_add_gps_data(mock_mqtt_handler):
    """Testet das Hinzufügen gültiger GPS-Daten."""
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)
    assert recorder.gps_data_buffer == [data1, data2]


@patch('data_recorder.logging')  # Mock logging, um Warnungen zu prüfen
def test_add_gps_data_none_and_invalid(mock_logging, mock_mqtt_handler):
    """Testet das Ignorieren von None und ungültigen Daten beim Hinzufügen."""
    recorder = DataRecorder(mock_mqtt_handler)
    data_valid = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data_invalid = "kein dictionary"

    recorder.add_gps_data(data_valid)
    recorder.add_gps_data(None)
    recorder.add_gps_data(data_invalid)

    assert recorder.gps_data_buffer == [data_valid]  # Nur gültige Daten im Puffer
    # Prüfe, ob die Warnung für ungültige Daten geloggt wurde
    mock_logging.warning.assert_called_once_with(f"DataRecorder: Ignoriere ungültige GPS-Daten: {data_invalid}")


def test_clear_buffer(mock_mqtt_handler):
    """Testet das Leeren des Puffers."""
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)
    assert len(recorder.gps_data_buffer) == 1
    recorder.clear_buffer()
    assert recorder.gps_data_buffer == []


def test_send_buffer_data_non_empty(mock_mqtt_handler):
    """Testet das Senden eines nicht-leeren Puffers."""
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}
    # Daten mit fehlenden Keys testen
    data3 = {'lat': 1.2, 'lon': 2.2}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)
    recorder.add_gps_data(data3)

    recorder.send_buffer_data()

    # Erwarteter CSV-String (ohne Header, mit leeren Werten für fehlende Keys)
    expected_csv = "1.0,2.0,100,5\n1.1,2.1,101,6\n1.2,2.2,,\n"
    expected_end_marker = "-1"

    # Prüfe, ob publish_message zweimal aufgerufen wurde (Daten + Marker)
    assert mock_mqtt_handler.publish_message.call_count == 2
    # Prüfe die Aufrufe im Detail
    mock_mqtt_handler.publish_message.assert_has_calls([
        call(mock_mqtt_handler.topic_gps, expected_csv),
        call(mock_mqtt_handler.topic_gps, expected_end_marker)
    ])


def test_send_buffer_data_empty(mock_mqtt_handler):
    """Testet das Senden eines leeren Puffers (nur End-Marker)."""
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.send_buffer_data()

    # Nur der End-Marker sollte gesendet werden
    assert mock_mqtt_handler.publish_message.call_count == 1
    mock_mqtt_handler.publish_message.assert_called_once_with(mock_mqtt_handler.topic_gps, "-1")


@patch('data_recorder.logging')  # Mock logging, um Fehler zu prüfen
def test_send_buffer_data_no_topic(mock_logging, mock_mqtt_handler):
    """Testet das Verhalten, wenn das MQTT-Topic fehlt."""
    # Entferne das Topic-Attribut vom Mock-Handler
    del mock_mqtt_handler.topic_gps
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)

    recorder.send_buffer_data()

    # Es sollte nichts gesendet werden
    mock_mqtt_handler.publish_message.assert_not_called()
    # Prüfe, ob der Fehler geloggt wurde
    mock_logging.error.assert_called_with("DataRecorder: MQTT handler hat kein 'topic_gps' Attribut oder es ist leer.")


@patch('data_recorder.logging')
@patch('io.StringIO')  # Patch io.StringIO direkt
def test_send_buffer_data_format_error(mock_stringio_class, mock_logging, mock_mqtt_handler, caplog):
    """Tests handling errors during CSV formatting."""
    # --- KORREKTUR: Entferne spec=io.StringIO ---
    mock_stringio_instance = MagicMock()  # Ohne spec
    # --- ENDE KORREKTUR ---

    # Simuliere einen Fehler beim Schreiben in den StringIO-Puffer
    mock_stringio_instance.write.side_effect = [None, IOError("Simulierter Schreibfehler"),
                                                None]  # Fehler beim 2. Punkt
    mock_stringio_class.return_value = mock_stringio_instance  # Stelle sicher, dass io.StringIO() unsere Mock-Instanz zurückgibt

    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}  # Dieser Punkt verursacht den Fehler
    data3 = {'lat': 1.2, 'lon': 2.2, 'timestamp': 102, 'satellites': 7}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)
    recorder.add_gps_data(data3)

    # Simuliere, dass getvalue() trotz des Fehlers etwas zurückgibt (die gültigen Teile)
    mock_stringio_instance.getvalue.return_value = "1.0,2.0,100,5\n1.2,2.2,102,7\n"

    recorder.send_buffer_data()

    # Prüfe, ob der Fehler beim Formatieren geloggt wurde
    mock_logging.error.assert_called_with(
        f"DataRecorder: Fehler beim Formatieren des Datenpunkts {data2}: Simulierter Schreibfehler. Überspringe Zeile."
    )

    # Prüfe, ob die (teilweise) formatierten Daten und der Marker gesendet wurden
    expected_csv = "1.0,2.0,100,5\n1.2,2.2,102,7\n"
    expected_end_marker = "-1"
    assert mock_mqtt_handler.publish_message.call_count == 2
    mock_mqtt_handler.publish_message.assert_has_calls([
        call(mock_mqtt_handler.topic_gps, expected_csv),
        call(mock_mqtt_handler.topic_gps, expected_end_marker)
    ])


@patch('data_recorder.logging.error')  # Patch nur die error-Funktion
def test_send_buffer_data_publish_error(mock_log_error, mock_mqtt_handler):  # mock_log_error statt caplog
    """Tests handling errors during MQTT publish."""
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)

    # Simuliere Publish-Fehler beim Senden der Daten
    mock_mqtt_handler.publish_message.side_effect = Exception("MQTT Broker down")  # Fehler bei Daten

    recorder.send_buffer_data()

    # publish_message wird für die Daten aufgerufen (schlägt fehl).
    # Die Exception wird gefangen, der Marker wird NICHT mehr versucht zu senden.
    assert mock_mqtt_handler.publish_message.call_count == 1  # Nur der Versuch, die Daten zu senden

    # Prüfe den ersten (und einzigen) Aufruf
    expected_csv = "1.0,2.0,100,5\n"
    mock_mqtt_handler.publish_message.assert_called_once_with(mock_mqtt_handler.topic_gps, expected_csv)

    # Prüfe, ob logging.error aufgerufen wurde
    mock_log_error.assert_called_once_with(
        "DataRecorder: Fehler beim Senden der Daten oder des End-Markers via MQTT: MQTT Broker down"
    )
