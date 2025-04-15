# tests/test_config.py
import os
import pytest
from unittest.mock import patch
import importlib

# Beispiel-Umgebungsvariablen für Tests
MOCK_ENV = {
    "MQTT_HOST": "real.mqtt.com",
    "MQTT_PORT": "1883",
    "MQTT_USER": "real_user",
    "MQTT_PASSWORD": "real_password",
    "MQTT_HOST_LOKAL": "localhost",
    "MQTT_PORT_LOKAL": "1884",  # Anderer Port für Test
    "MQTT_USER_LOCAL": "local_user",
    "MQTT_PASSWORD_LOCAL": "local_password",
    "MQTT_TOPIC_GPS": "worx/gps",
    "MQTT_TOPIC_STATUS": "worx/status",
    "MQTT_TOPIC_CONTROL": "worx/control",
    "GPS_SERIAL_PORT": "/dev/ttyTest",
    "GPS_BAUDRATE": "19200",
    "TEST_MODE": "True",  # Wichtig für test_rec_config_loading
    "PROBLEM_JSON": "test_problems.json",
    "MAX_PROBLEMZONEN": "50",
    "PROBLEM_THRESHOLD_TIME": "45",
    "ASSIST_NOW_ENABLED": "True",
    "ASSIST_NOW_TOKEN": "test_token_123"
    # ASSIST_NOW_OFFLINE_URL wird nicht aus Env geladen, hat Standardwert
}


# Testet das Laden der MQTT-Konfiguration
@patch.dict(os.environ, MOCK_ENV, clear=True)
def test_mqtt_config_loading():
    """Tests if MQTT_CONFIG is loaded correctly."""
    # Importiere config *nachdem* die Umgebungsvariablen gepatcht wurden
    import config
    # Erzwinge das Neuladen des Moduls, um die gepatchten Variablen zu nutzen
    importlib.reload(config)

    assert config.MQTT_CONFIG["host"] == "real.mqtt.com"
    assert config.MQTT_CONFIG["port"] == 1883  # Check type conversion
    assert config.MQTT_CONFIG["user"] == "real_user"
    assert config.MQTT_CONFIG["password"] == "real_password"
    assert config.MQTT_CONFIG["host_lokal"] == "localhost"
    assert config.MQTT_CONFIG["port_lokal"] == 1884  # Check type conversion
    assert config.MQTT_CONFIG["user_local"] == "local_user"
    assert config.MQTT_CONFIG["password_local"] == "local_password"
    assert config.MQTT_CONFIG["topic_gps"] == "worx/gps"
    assert config.MQTT_CONFIG["topic_status"] == "worx/status"
    assert config.MQTT_CONFIG["topic_control"] == "worx/control"


# Testet das Laden der Recorder-Konfiguration
@patch.dict(os.environ, MOCK_ENV, clear=True)
def test_rec_config_loading():
    """Tests if REC_CONFIG is loaded correctly."""
    import config
    importlib.reload(config)

    assert config.REC_CONFIG["serial_port"] == "/dev/ttyTest"
    assert config.REC_CONFIG["baudrate"] == 19200  # Check type conversion
    # --- KORREKTUR: Erwarte True, da TEST_MODE="True" ---
    assert config.REC_CONFIG["test_mode"] is True
    # --- Ende Korrektur ---
    assert isinstance(config.REC_CONFIG["storage_interval"], int)  # Check default type


# Testet, ob test_mode korrekt auf False gesetzt wird, wenn nicht "true"
@patch.dict(os.environ, {"TEST_MODE": "False"}, clear=True)
def test_rec_config_test_mode_false():
    """Tests if test_mode is False when TEST_MODE is 'False'."""
    import config
    importlib.reload(config)
    assert config.REC_CONFIG["test_mode"] is False


# Testet den Standardwert für Baudrate
@patch.dict(os.environ, {"GPS_BAUDRATE": ""}, clear=True)  # Leerer String simulieren
def test_rec_config_default_baudrate():
    """Tests the default baudrate value."""
    import config
    importlib.reload(config)
    assert config.REC_CONFIG["baudrate"] == 9600


# Testet das Laden der AssistNow-Konfiguration
@patch.dict(os.environ, MOCK_ENV, clear=True)
def test_assist_now_config_loading():
    """Tests if ASSIST_NOW_CONFIG is loaded correctly."""
    import config
    importlib.reload(config)

    assert config.ASSIST_NOW_CONFIG["assist_now_enabled"] is True
    assert config.ASSIST_NOW_CONFIG["assist_now_offline_url"] is not None  # Hat Standardwert
    assert config.ASSIST_NOW_CONFIG["assist_now_token"] == "test_token_123"


# Testet, ob assist_now_enabled korrekt auf False gesetzt wird
@patch.dict(os.environ, {"ASSIST_NOW_ENABLED": "no"}, clear=True)
def test_assist_now_config_disabled():
    """Tests if assist_now_enabled is False when not 'true'."""
    import config
    importlib.reload(config)
    assert config.ASSIST_NOW_CONFIG["assist_now_enabled"] is False


# Testet statische Konfigurationen (GEO, HEATMAP, PROBLEM)
def test_static_configs():
    """Tests if static parts of the config are present."""
    import config
    importlib.reload(config)  # Sicherstellen, dass es geladen ist

    assert "lat_bounds" in config.GEO_CONFIG
    assert "lon_bounds" in config.GEO_CONFIG
    assert "map_center" in config.GEO_CONFIG
    assert "zoom_start" in config.GEO_CONFIG

    assert "tile" in config.HEATMAP_CONFIG
    assert "heatmap_aktuell" in config.HEATMAP_CONFIG
    assert "output" in config.HEATMAP_CONFIG["heatmap_aktuell"]

    assert "problem_json" in config.PROBLEM_CONFIG
    assert "max_problemzonen" in config.PROBLEM_CONFIG
    assert "problem_threshold_time" in config.PROBLEM_CONFIG

# Optional: Test der Validierungsfunktion (wenn sie Fehler auslösen würde)
# @patch.dict(os.environ, {"MQTT_HOST": ""}, clear=True) # Fehlenden Wert simulieren
# def test_validate_config_missing_critical(capsys):
#     """Tests if validate_config prints warnings for missing values."""
#     import config
#     #
