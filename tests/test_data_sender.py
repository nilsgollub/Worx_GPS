# tests/test_data_sender.py
import pytest
from unittest.mock import patch, mock_open, MagicMock, call
import json

# Importiere die zu testende Klasse und die verwendete Konfiguration
from data_sender import DataSender
from config import MQTT_CONFIG as REAL_MQTT_CONFIG

# Mock-Konfiguration für Tests
MQTT_CONFIG_MOCK = REAL_MQTT_CONFIG.copy()
MQTT_CONFIG_MOCK["host"] = "mock_broker"
MQTT_CONFIG_MOCK["port"] = 1883
MQTT_CONFIG_MOCK["topic_gps"] = "mock/gps"


# --- Testklasse ---
# Patch paho.mqtt.client im data_sender Modul
@patch('data_sender.mqtt.Client')
class TestDataSender:

    @pytest.fixture(autouse=True)
    # --- KORREKTUR: MockPahoClient aus Signatur entfernt ---
    def setup_mocks_and_instance(self, MockPahoClient):
        """Setzt Mocks auf und erstellt eine Instanz von DataSender für jeden Test."""
        # Mock-Instanz für den MQTT-Client holen
        self.mock_client_instance = MockPahoClient.return_value
        # DataSender-Instanz erstellen (verwendet den Mock-Client)
        # Wir patchen hier nicht MQTT_CONFIG, da DataSender Broker/Port als Argumente nimmt
        self.sender = DataSender(MQTT_CONFIG_MOCK["host"], MQTT_CONFIG_MOCK["port"])
        # Stelle sicher, dass der Client im Sender der Mock ist
        assert self.sender.mqtt_client is self.mock_client_instance
        yield  # Lässt den Test laufen

    # Die Tests benötigen MockPahoClient nicht mehr als Argument
    def test_data_sender_init(self):
        """Tests the initialization of DataSender."""
        # Prüfe, ob der Client korrekt initialisiert und verbunden wurde
        # MockPahoClient wird von der Klasse bereitgestellt, muss hier nicht übergeben werden
        # Die Instanz wird in setup_mocks_and_instance erstellt
        assert self.sender.mqtt_broker == MQTT_CONFIG_MOCK["host"]
        assert self.sender.mqtt_port == MQTT_CONFIG_MOCK["port"]
        assert self.sender.mqtt_topic_gps == "worx/gps"  # Topic ist hardcoded in DataSender
        # Prüfe, ob die Client-Methoden aufgerufen wurden
        self.mock_client_instance.connect.assert_called_once_with(MQTT_CONFIG_MOCK["host"], MQTT_CONFIG_MOCK["port"],
                                                                  60)
        self.mock_client_instance.loop_start.assert_called_once()

    @patch("builtins.open", new_callable=mock_open,
           read_data="lat,lon,timestamp,satellites,state\n1.0,2.0,100,5,fix\n1.1,2.1,101,6,nofix")
    def test_read_csv_success(self, mock_file):
        """Tests successful reading of a CSV file."""
        expected_data = [
            {"latitude": 1.0, "longitude": 2.0, "timestamp": 100.0, "satellites": 5, "state": "fix"},
            {"latitude": 1.1, "longitude": 2.1, "timestamp": 101.0, "satellites": 6, "state": "nofix"},
        ]
        result = self.sender.read_csv("dummy.csv")
        mock_file.assert_called_once_with("dummy.csv", 'r')
        assert result == expected_data

    @patch("builtins.open", new_callable=mock_open, read_data="")  # Leere Datei
    def test_read_csv_empty_file(self, mock_file, capsys):
        """Tests reading an empty CSV file."""
        result = self.sender.read_csv("empty.csv")
        mock_file.assert_called_once_with("empty.csv", 'r')
        assert result == []
        captured = capsys.readouterr()
        assert "Keine Daten zum senden gefunden" in captured.out

    @patch("builtins.open", new_callable=mock_open, read_data="lat,lon,timestamp,satellites,state\n")  # Nur Header
    def test_read_csv_header_only(self, mock_file, capsys):
        """Tests reading a CSV file with only a header."""
        result = self.sender.read_csv("header.csv")
        mock_file.assert_called_once_with("header.csv", 'r')
        assert result == []
        captured = capsys.readouterr()
        assert "Keine Daten zum senden gefunden" in captured.out

    @patch("builtins.open", new_callable=mock_open,
           read_data="lat,lon,timestamp,satellites,state\n1.0,invalid,100,5,fix")
    def test_read_csv_invalid_numeric(self, mock_file, capsys):
        """Tests reading a CSV file with invalid numeric data."""
        result = self.sender.read_csv("invalid.csv")
        mock_file.assert_called_once_with("invalid.csv", 'r')
        # Die fehlerhafte Zeile wird übersprungen
        assert result == []
        captured = capsys.readouterr()
        assert "Fehler beim konvertieren der Werte in Zeile" in captured.out

    @patch("builtins.open", new_callable=mock_open,
           read_data="lat,lon,timestamp,satellites,state\n1.0,2.0,100")  # Fehlende Spalten
    def test_read_csv_missing_columns(self, mock_file):
        """Tests reading a CSV file with missing columns."""
        result = self.sender.read_csv("missing.csv")
        mock_file.assert_called_once_with("missing.csv", 'r')
        # Die Zeile wird übersprungen, da len(values) < 5
        assert result == []

    @patch('data_sender.DataSender.read_csv')
    @patch('json.dumps')
    def test_send_data_success(self, mock_json_dumps, mock_read_csv):
        """Tests successful sending of data."""
        mock_read_csv.return_value = [{"lat": 1}]
        mock_json_dumps.return_value = '[{"lat": 1}]'

        self.sender.send_data("dummy.csv")

        mock_read_csv.assert_called_once_with("dummy.csv")
        mock_json_dumps.assert_called_once_with([{"lat": 1}])
        self.mock_client_instance.publish.assert_called_once_with(
            self.sender.mqtt_topic_gps, '[{"lat": 1}]'
        )

    @patch('data_sender.DataSender.read_csv', side_effect=FileNotFoundError("Cannot open"))
    def test_send_data_read_error(self, mock_read_csv, capsys):
        """Tests handling error during CSV reading."""
        self.sender.send_data("nonexistent.csv")
        mock_read_csv.assert_called_once_with("nonexistent.csv")
        self.mock_client_instance.publish.assert_not_called()
        captured = capsys.readouterr()
        assert "Fehler beim Senden der Daten: Cannot open" in captured.out

    @patch('data_sender.DataSender.read_csv', return_value=[{"lat": 1}])
    @patch('json.dumps', side_effect=TypeError("Cannot serialize"))
    def test_send_data_json_error(self, mock_json_dumps, mock_read_csv, capsys):
        """Tests handling error during JSON serialization."""
        self.sender.send_data("dummy.csv")
        mock_read_csv.assert_called_once_with("dummy.csv")
        mock_json_dumps.assert_called_once_with([{"lat": 1}])
        self.mock_client_instance.publish.assert_not_called()
        captured = capsys.readouterr()
        assert "Fehler beim Senden der Daten: Cannot serialize" in captured.out

    @patch('data_sender.DataSender.read_csv', return_value=[{"lat": 1}])
    @patch('json.dumps', return_value='[]')
    def test_send_data_publish_error(self, mock_json_dumps, mock_read_csv, capsys):
        """Tests handling error during MQTT publish."""
        self.mock_client_instance.publish.side_effect = Exception("Broker unavailable")

        self.sender.send_data("dummy.csv")

        mock_read_csv.assert_called_once_with("dummy.csv")
        mock_json_dumps.assert_called_once_with([{"lat": 1}])
        self.mock_client_instance.publish.assert_called_once_with(self.sender.mqtt_topic_gps, '[]')
        captured = capsys.readouterr()
        assert "Fehler beim Senden der Daten: Broker unavailable" in captured.out

    def test_close(self):
        """Tests closing the MQTT connection."""
        self.sender.close()
        self.mock_client_instance.loop_stop.assert_called_once()
        self.mock_client_instance.disconnect.assert_called_once()
