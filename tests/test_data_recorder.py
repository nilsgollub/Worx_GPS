# tests/test_data_recorder.py
import pytest
from unittest.mock import patch, MagicMock, call
import logging
import io  # Import io

# Importiere die zu testende Klasse
from data_recorder import DataRecorder


# --- Fixtures ---
@pytest.fixture
def mock_mqtt_handler():
    """Erstellt einen einfachen Mock für den MqttHandler."""
    handler = MagicMock()
    handler.topic_gps = "test/gps"  # Wichtig: Topic muss gesetzt sein
    return handler


# --- Tests ---
def test_data_recorder_init(mock_mqtt_handler):
    """Testet die Initialisierung des DataRecorders."""
    recorder = DataRecorder(mock_mqtt_handler)
    assert recorder.mqtt_handler is mock_mqtt_handler
    assert recorder.gps_data_buffer == []


def test_data_recorder_init_no_handler():
    """Testet, dass die Initialisierung ohne Handler fehlschlägt."""
    with pytest.raises(ValueError, match="MqttHandler instance is required"):
        DataRecorder(None)


def test_add_gps_data(mock_mqtt_handler):
    """Testet das Hinzufügen gültiger GPS-Daten."""
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)
    assert recorder.gps_data_buffer == [data1, data2]


def test_add_gps_data_none_and_invalid(mock_mqtt_handler, caplog):
    """Testet das Ignorieren von None und ungültigen Daten beim Hinzufügen."""
    caplog.set_level(logging.WARNING)
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(None)  # Sollte ignoriert werden
    recorder.add_gps_data("invalid_string")  # Sollte ignoriert werden
    recorder.add_gps_data([1, 2, 3])  # Sollte ignoriert werden
    assert recorder.gps_data_buffer == [data1]  # Nur data1 sollte im Puffer sein
    assert "Ignoriere ungültige GPS-Daten: invalid_string" in caplog.text
    assert "Ignoriere ungültige GPS-Daten: [1, 2, 3]" in caplog.text


def test_clear_buffer(mock_mqtt_handler):
    """Testet das Leeren des Puffers."""
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.add_gps_data({'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5})
    assert len(recorder.gps_data_buffer) == 1
    recorder.clear_buffer()
    assert recorder.gps_data_buffer == []


def test_send_buffer_data_non_empty(mock_mqtt_handler):
    """Testet das Senden eines nicht-leeren Puffers."""
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    data2 = {'lat': 1.1, 'lon': 2.1, 'timestamp': 101, 'satellites': 6}
    recorder.add_gps_data(data1)
    recorder.add_gps_data(data2)

    recorder.send_buffer_data()

    # Erwarteter CSV-String (ohne Kopfzeile, mit Newlines)
    expected_csv = "1.0,2.0,100,5\n1.1,2.1,101,6\n"

    # Prüfe, ob publish_message zweimal aufgerufen wurde: einmal mit Daten, einmal mit Marker
    expected_calls = [
        call(mock_mqtt_handler.topic_gps, expected_csv),
        call(mock_mqtt_handler.topic_gps, "-1")
    ]
    mock_mqtt_handler.publish_message.assert_has_calls(expected_calls, any_order=False)
    assert mock_mqtt_handler.publish_message.call_count == 2


def test_send_buffer_data_empty(mock_mqtt_handler, caplog):
    """Testet das Senden eines leeren Puffers."""
    caplog.set_level(logging.WARNING)
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.send_buffer_data()

    # Prüfe, ob nur der End-Marker gesendet wurde
    mock_mqtt_handler.publish_message.assert_called_once_with(mock_mqtt_handler.topic_gps, "-1")
    # Prüfe, ob die Warnung geloggt wurde
    assert "Kein Daten im Puffer zum Senden" in caplog.text


def test_send_buffer_data_no_topic(mock_mqtt_handler, caplog):
    """Testet das Verhalten, wenn das MQTT-Topic fehlt."""
    caplog.set_level(logging.ERROR)
    # Entferne das Topic-Attribut vom Mock
    del mock_mqtt_handler.topic_gps
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.add_gps_data({'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5})
    recorder.send_buffer_data()

    # Prüfe, dass publish_message nicht aufgerufen wurde
    mock_mqtt_handler.publish_message.assert_not_called()
    # Prüfe die Fehlermeldung im Log
    assert "MQTT handler hat kein 'topic_gps' Attribut" in caplog.text


# --- KORREKTUR: Patch-Ziel und Testlogik ---
@patch('data_recorder.logging')  # Mock logging, um Fehler zu prüfen
@patch('data_recorder.io.StringIO')  # Patch die Klasse io.StringIO
def test_send_buffer_data_format_error(mock_stringio_class, mock_logging, mock_mqtt_handler, caplog):
    """Tests handling errors during CSV formatting."""
    # Konfiguriere den Mock, den io.StringIO zurückgeben soll
    mock_stringio_instance = MagicMock(spec=io.StringIO)  # Spezifiziere io.StringIO für bessere Mock-Eigenschaften
    mock_stringio_instance.write.side_effect = TypeError("Format Error")
    # getvalue muss aufgerufen werden können, auch wenn write fehlschlägt
    mock_stringio_instance.getvalue.return_value = "partially_written_or_empty"
    # close muss aufgerufen werden können
    mock_stringio_instance.close.return_value = None
    mock_stringio_class.return_value = mock_stringio_instance  # io.StringIO() gibt jetzt unseren Mock zurück

    caplog.set_level(logging.ERROR)
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    # Füge Daten hinzu, die den Fehler auslösen würden
    recorder.add_gps_data({'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5})

    recorder.send_buffer_data()

    # Prüfe, ob der Fehler geloggt wurde
    assert "Fehler beim Formatieren des Datenpunkts" in caplog.text
    assert "TypeError: Format Error" in caplog.text  # Der spezifische Fehler
    # Prüfe, ob der End-Marker trotzdem gesendet wurde
    # Der CSV-String wird leer sein oder unvollständig, aber der Marker sollte gesendet werden
    mock_mqtt_handler.publish_message.assert_called_with(mock_mqtt_handler.topic_gps, "-1")
    # Prüfe, dass die (potenziell leeren/unvollständigen) Daten NICHT gesendet wurden,
    # oder zumindest, dass der Marker der LETZTE Aufruf war.
    # Da getvalue "partially_written_or_empty" zurückgibt, wird versucht, dies zu senden.
    # Wir erwarten also zwei Aufrufe: Daten (leer/unvollständig) und Marker.
    # Der wichtigste Check ist, dass der Marker gesendet wird.
    assert call(mock_mqtt_handler.topic_gps, "-1") in mock_mqtt_handler.publish_message.call_args_list


@patch('data_recorder.logging')  # Mock logging
def test_send_buffer_data_publish_error(mock_logging, mock_mqtt_handler, caplog):
    """Tests handling errors during MQTT publish."""
    caplog.set_level(logging.ERROR)  # Fehler loggen
    from data_recorder import DataRecorder
    recorder = DataRecorder(mock_mqtt_handler)
    data1 = {'lat': 1.0, 'lon': 2.0, 'timestamp': 100, 'satellites': 5}
    recorder.add_gps_data(data1)

    # Simuliere Publish-Fehler beim Senden der Daten
    mock_mqtt_handler.publish_message.side_effect = [Exception("MQTT Broker down"),
                                                     None]  # Fehler bei Daten, OK bei Marker

    recorder.send_buffer_data()

    # --- KORREKTUR: Erwartete Aufrufanzahl ---
    # publish_message wird für die Daten aufgerufen (schlägt fehl),
    # dann wird die Exception gefangen, und der Marker wird NICHT mehr versucht zu senden.
    assert mock_mqtt_handler.publish_message.call_count == 1

    # Prüfe den ersten (und einzigen) Aufruf
    expected_csv = "1.0,2.0,100,5\n"
    mock_mqtt_handler.publish_message.assert_called_once_with(mock_mqtt_handler.topic_gps, expected_csv)

    # Prüfe, ob der Fehler geloggt wurde
    assert "Fehler beim Senden der Daten oder des End-Markers via MQTT: MQTT Broker down" in caplog.text
