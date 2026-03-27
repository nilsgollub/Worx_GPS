# tests/test_data_recorder.py
import pytest
from unittest.mock import patch, MagicMock, call, mock_open
import logging
import io  # Importiere io

# Importiere die zu testende Klasse
from data_recorder import DataRecorder
import os

# --- Fixture für einen Mock MQTT Handler ---
@pytest.fixture
def mock_mqtt_handler():
    """Stellt ein Mock-Objekt für den MqttHandler bereit."""
    mock = MagicMock()
    mock.topic_gps = "mock/worx/gps"
    return mock

def test_data_recorder_init(mock_mqtt_handler):
    """Testet die Initialisierung des DataRecorders."""
    recorder = DataRecorder(mock_mqtt_handler)
    assert recorder.mqtt_handler == mock_mqtt_handler
    assert recorder.buffer_file == "offline_gps_buffer.csv"

def test_data_recorder_init_no_mqtt():
    """Testet, dass ein Fehler geworfen wird, wenn kein MQTT-Handler übergeben wird."""
    with pytest.raises(ValueError, match="MqttHandler instance is required."):
        DataRecorder(None)

@patch('builtins.open', new_callable=mock_open)
def test_add_gps_data(mock_file, mock_mqtt_handler):
    """Testet das Hinzufügen von gültigen GPS-Daten."""
    recorder = DataRecorder(mock_mqtt_handler)
    data = {'lat': 46.1, 'lon': 7.1, 'timestamp': 100, 'satellites': 5, 'hdop': 1.2}
    
    with patch.object(recorder, '_get_wifi_signal_strength', return_value=-50):
        recorder.add_gps_data(data)
    
    mock_file.assert_called_once_with("offline_gps_buffer.csv", "a")
    mock_file().write.assert_called_once_with("46.1,7.1,100,5,-50,1.2\n")

@patch('data_recorder.logging')
def test_add_gps_data_none_and_invalid(mock_logging, mock_mqtt_handler):
    """Testet das Verhalten bei ungültigen Eingaben."""
    recorder = DataRecorder(mock_mqtt_handler)
    
    # None als Eingabe
    recorder.add_gps_data(None)
    mock_logging.warning.assert_not_called()  # Keine Warnung bei None
    
    # Ungültiger Datentyp (z.B. String statt Dict)
    recorder.add_gps_data("invalid data")
    mock_logging.warning.assert_called_once_with("DataRecorder: Ignoriere ungültige GPS-Daten: invalid data")

@patch('os.path.exists')
@patch('os.remove')
def test_clear_buffer(mock_remove, mock_exists, mock_mqtt_handler):
    """Testet das Leeren des Puffers (Datei löschen)."""
    mock_exists.return_value = True
    recorder = DataRecorder(mock_mqtt_handler)
    
    recorder.clear_buffer()
    
    mock_exists.assert_called_once_with("offline_gps_buffer.csv")
    mock_remove.assert_called_once_with("offline_gps_buffer.csv")

@patch('os.path.exists')
@patch('os.path.getsize')
@patch('builtins.open', new_callable=mock_open, read_data="46.1,7.1,100,5,-50,1.2\n")
@patch('data_recorder.DataRecorder.clear_buffer')
def test_send_buffer_data_non_empty(mock_clear_buffer, mock_file, mock_getsize, mock_exists, mock_mqtt_handler):
    """Testet das Senden eines nicht-leeren Puffers."""
    mock_exists.return_value = True
    mock_getsize.return_value = 100
    
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.send_buffer_data()

    # Prüfe, ob publish_message zweimal aufgerufen wurde (Daten + Marker)
    assert mock_mqtt_handler.publish_message.call_count == 2
    mock_mqtt_handler.publish_message.assert_has_calls([
        call(mock_mqtt_handler.topic_gps, "46.1,7.1,100,5,-50,1.2\n"),
        call(mock_mqtt_handler.topic_gps, "-1")
    ])
    
    # Puffer muss danach geleert werden
    mock_clear_buffer.assert_called_once()

@patch('os.path.exists')
@patch('os.path.getsize')
def test_send_buffer_data_empty(mock_getsize, mock_exists, mock_mqtt_handler):
    """Testet das Senden eines leeren Puffers (nur End-Marker)."""
    mock_exists.return_value = False  # Datei existiert nicht
    
    recorder = DataRecorder(mock_mqtt_handler)
    recorder.send_buffer_data()

    # Nur der End-Marker sollte gesendet werden
    assert mock_mqtt_handler.publish_message.call_count == 1
    mock_mqtt_handler.publish_message.assert_called_once_with(mock_mqtt_handler.topic_gps, "-1")

@patch('data_recorder.logging')
def test_send_buffer_data_no_topic(mock_logging, mock_mqtt_handler):
    """Testet das Verhalten, wenn das MQTT-Topic fehlt."""
    del mock_mqtt_handler.topic_gps
    recorder = DataRecorder(mock_mqtt_handler)
    
    recorder.send_buffer_data()

    mock_mqtt_handler.publish_message.assert_not_called()
    mock_logging.error.assert_called_with("DataRecorder: MQTT handler hat kein 'topic_gps' Attribut oder es ist leer.")

@patch('os.path.exists')
@patch('os.path.getsize')
@patch('builtins.open', new_callable=mock_open, read_data="46.1,7.1,100,5,-50,1.2\n")
@patch('data_recorder.DataRecorder.clear_buffer')
@patch('data_recorder.logging.error')
def test_send_buffer_data_publish_error(mock_log_error, mock_clear_buffer, mock_file, mock_getsize, mock_exists, mock_mqtt_handler):
    """Tests handling errors during MQTT publish."""
    mock_exists.return_value = True
    mock_getsize.return_value = 100
    
    recorder = DataRecorder(mock_mqtt_handler)
    
    # Simuliere Publish-Fehler beim Senden der Daten
    mock_mqtt_handler.publish_message.side_effect = Exception("MQTT Broker down")
    
    recorder.send_buffer_data()

    assert mock_mqtt_handler.publish_message.call_count == 1  # Nur der Versuch, die Daten zu senden
    mock_mqtt_handler.publish_message.assert_called_once_with(mock_mqtt_handler.topic_gps, "46.1,7.1,100,5,-50,1.2\n")

    # Fehler geloggt?
    mock_log_error.assert_called_once()
    assert "Fehler beim Senden der Daten: MQTT Broker down" in mock_log_error.call_args[0][0]
    
    # Der Puffer MUSS auch bei Fehlern geleert werden
    mock_clear_buffer.assert_called_once()
