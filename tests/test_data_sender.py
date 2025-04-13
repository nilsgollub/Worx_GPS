import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import json
import paho.mqtt.client as mqtt  # Import for mocking

# Mock config before import
MQTT_CONFIG_MOCK = {"host": "sender.mqtt.com", "port": 1885}  # Example


# Note: data_sender.py defines the DataSender class twice.
# These tests will target the first definition encountered by Python.
# The duplicate definition should be removed in the source file.

@patch('data_sender.mqtt.Client')
@patch('data_sender.MQTT_CONFIG', MQTT_CONFIG_MOCK)  # Mock config if DataSender uses it directly
class TestDataSender:

    @pytest.fixture(autouse=True)
    def setup_mocks_and_instance(self, MockMqttClient):
        # Mock the MQTT client instance
        self.mock_client_instance = MockMqttClient.return_value
        self.mock_client_instance.connect = MagicMock()
        self.mock_client_instance.loop_start = MagicMock()
        self.mock_client_instance.publish = MagicMock()
        self.mock_client_instance.loop_stop = MagicMock()
        self.mock_client_instance.disconnect = MagicMock()

        # Create DataSender instance
        from data_sender import DataSender
        # Pass broker/port explicitly as per __init__ signature
        self.sender = DataSender(mqtt_broker="test.broker", mqtt_port=1234)
        yield

    def test_data_sender_init(self, MockMqttClient):
        """Tests DataSender initialization."""
        # Re-init to check constructor calls
        from data_sender import DataSender
        broker, port = "init.broker", 9999
        sender = DataSender(broker, port)

        # Check client initialization
        MockMqttClient.assert_called_with(mqtt.CallbackAPIVersion.VERSION2)
        # Check attributes
        assert sender.mqtt_broker == broker
        assert sender.mqtt_port == port
        assert sender.mqtt_client == self.mock_client_instance
        assert sender.mqtt_topic_gps == "worx/gps"  # Hardcoded in class
        # Check methods called
        self.mock_client_instance.connect.assert_called_once_with(broker, port, 60)
        self.mock_client_instance.loop_start.assert_called_once()

    def test_read_csv_success(self):
        """Tests reading a valid CSV file."""
        csv_content = "lat,lon,timestamp,satellites,state\n" \
                      "46.1,7.1,100.1,5.0,mowing\n" \
                      "46.2,7.2,100.2,6,charging\n" \
                      "46.3,7.3,100.3,7.9,error\n"
        m_open = mock_open(read_data=csv_content)
        with patch('builtins.open', m_open):
            result = self.sender.read_csv("dummy.csv")

        expected = [
            {"latitude": 46.1, "longitude": 7.1, "timestamp": 100.1, "satellites": 5, "state": "mowing"},
            {"latitude": 46.2, "longitude": 7.2, "timestamp": 100.2, "satellites": 6, "state": "charging"},
            {"latitude": 46.3, "longitude": 7.3, "timestamp": 100.3, "satellites": 7, "state": "error"},
            # Note satellite truncation to int
        ]
        assert result == expected
        m_open.assert_called_once_with("dummy.csv", 'r')

    def test_read_csv_empty_file(self, capsys):
        """Tests reading an empty CSV file."""
        csv_content = ""  # Empty
        m_open = mock_open(read_data=csv_content)
        with patch('builtins.open', m_open):
            result = self.sender.read_csv("empty.csv")
        assert result == []
        captured = capsys.readouterr()
        assert "Keine Daten zum senden gefunden" in captured.out

    def test_read_csv_header_only(self, capsys):
        """Tests reading a CSV file with only a header."""
        csv_content = "lat,lon,timestamp,satellites,state\n"  # Header only
        m_open = mock_open(read_data=csv_content)
        with patch('builtins.open', m_open):
            result = self.sender.read_csv("header.csv")
        assert result == []
        captured = capsys.readouterr()
        assert "Keine Daten zum senden gefunden" in captured.out

    def test_read_csv_invalid_numeric(self, capsys):
        """Tests reading CSV with invalid numeric data."""
        csv_content = "lat,lon,timestamp,satellites,state\n" \
                      "46.1,abc,100.1,5,mowing\n" \
                      "46.2,7.2,100.2,xyz,charging\n"
        m_open = mock_open(read_data=csv_content)
        with patch('builtins.open', m_open):
            result = self.sender.read_csv("invalid.csv")

        # Only valid lines (if any) should be returned. Here, none are valid.
        assert result == []
        captured = capsys.readouterr()
        assert "Fehler beim konvertieren der Werte in Zeile" in captured.out
        # Check both errors are logged
        assert "46.1,abc,100.1,5,mowing" in captured.out
        assert "46.2,7.2,100.2,xyz,charging" in captured.out

    def test_read_csv_missing_columns(self):
        """Tests reading CSV with missing columns."""
        csv_content = "lat,lon,timestamp,satellites,state\n" \
                      "46.1,7.1,100.1\n"  # Missing columns
        m_open = mock_open(read_data=csv_content)
        with patch('builtins.open', m_open):
            result = self.sender.read_csv("missing.csv")
        # The code checks `len(values) >= 5`, so this line should be skipped
        assert result == []

    @patch('data_sender.DataSender.read_csv')
    @patch('json.dumps')
    def test_send_data_success(self, mock_json_dumps, mock_read_csv):
        """Tests successful data sending."""
        csv_file = "mydata.csv"
        mock_data = [{"lat": 1}]
        mock_json_string = '[{"lat": 1}]'
        mock_read_csv.return_value = mock_data
        mock_json_dumps.return_value = mock_json_string

        self.sender.send_data(csv_file)

        mock_read_csv.assert_called_once_with(csv_file)
        mock_json_dumps.assert_called_once_with(mock_data)
        self.mock_client_instance.publish.assert_called_once_with(
            self.sender.mqtt_topic_gps, mock_json_string
        )

    @patch('data_sender.DataSender.read_csv', side_effect=FileNotFoundError("Cannot open"))
    def test_send_data_read_error(self, mock_read_csv, capsys):
        """Tests handling error during CSV reading in send_data."""
        self.sender.send_data("nonexistent.csv")

        self.mock_client_instance.publish.assert_not_called()
        captured = capsys.readouterr()
        assert "Fehler beim Senden der Daten: Cannot open" in captured.out

    @patch('data_sender.DataSender.read_csv', return_value=[{"lat": 1}])
    @patch('json.dumps', side_effect=TypeError("Cannot serialize"))
    def test_send_data_json_error(self, mock_json_dumps, mock_read_csv, capsys):
        """Tests handling error during JSON serialization."""
        self.sender.send_data("data.csv")

        self.mock_client_instance.publish.assert_not_called()
        captured = capsys.readouterr()
        assert "Fehler beim Senden der Daten: Cannot serialize" in captured.out

    @patch('data_sender.DataSender.read_csv', return_value=[{"lat": 1}])
    @patch('json.dumps', return_value='[]')
    def test_send_data_publish_error(self, mock_json_dumps, mock_read_csv, capsys):
        """Tests handling error during MQTT publish."""
        self.mock_client_instance.publish.side_effect = Exception("Broker unavailable")

        self.sender.send_data("data.csv")

        self.mock_client_instance.publish.assert_called_once()  # Publish was attempted
        captured = capsys.readouterr()
        assert "Fehler beim Senden der Daten: Broker unavailable" in captured.out

    def test_close(self):
        """Tests the close method."""
        self.sender.close()
        self.mock_client_instance.loop_stop.assert_called_once()
        self.mock_client_instance.disconnect.assert_called_once()
