import pytest
import requests
from unittest.mock import patch, mock_open, MagicMock
import Assist_nw


# Mock environment variables before importing the module if needed,
# or patch os.getenv within tests.
@patch.dict('os.environ',
            {'ASSIST_NOW_TOKEN': 'test_token', 'ASSIST_NOW_ENABLED': 'True', 'ASSIST_NOW_PATH': '/dev/fake_serial'})
def setup_module(module):
    # Reload the module to pick up patched environment variables if necessary
    import importlib
    importlib.reload(Assist_nw)


@patch('Assist_nw.requests.get')
def test_download_assist_now_data_success(mock_get):
    """Tests successful download of AssistNow data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'ubx_data_content'
    mock_response.raise_for_status.return_value = None  # No exception on success
    mock_get.return_value = mock_response

    data = Assist_nw.download_assist_now_data()

    assert data == b'ubx_data_content'
    mock_get.assert_called_once_with(
        Assist_nw.assist_now_offline_url,
        headers={"useragent": "Thingstream Client"},
        params={
            "token": "test_token",
            "gnss": "gps",
            "alm": "gps",
            "days": 7,
            "resolution": 1
        }
    )
    mock_response.raise_for_status.assert_called_once()


@patch('Assist_nw.requests.get')
def test_download_assist_now_data_failure(mock_get):
    """Tests download failure."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Download failed")
    mock_get.return_value = mock_response

    data = Assist_nw.download_assist_now_data()

    assert data is None
    mock_get.assert_called_once()
    mock_response.raise_for_status.assert_called_once()


@patch('builtins.open', new_callable=mock_open)
def test_send_assist_now_data_success(mock_file):
    """Tests successful sending of data to the serial port."""
    test_data = b'some_ubx_data'
    Assist_nw.send_assist_now_data(test_data)

    # Check if open was called correctly
    mock_file.assert_called_once_with(Assist_nw.assist_now_path, "wb")
    # Check if write was called with the correct data
    mock_file().write.assert_called_once_with(test_data)


@patch('builtins.open', side_effect=IOError("Permission denied"))
def test_send_assist_now_data_failure(mock_open_error, capsys):
    """Tests failure during sending data."""
    test_data = b'some_ubx_data'
    Assist_nw.send_assist_now_data(test_data)

    captured = capsys.readouterr()
    assert "Fehler beim Senden der AssistNow Offline-Daten: Permission denied" in captured.out
    mock_open_error.assert_called_once_with(Assist_nw.assist_now_path, "wb")


# Example of testing the main block logic (requires more setup/mocking)
@patch('Assist_nw.download_assist_now_data')
@patch('Assist_nw.send_assist_now_data')
@patch.dict('os.environ', {'ASSIST_NOW_ENABLED': 'True'})
def test_main_block_enabled(mock_send, mock_download):
    """Test main execution path when enabled."""
    import importlib
    importlib.reload(Assist_nw)  # Reload to get patched env var

    mock_download.return_value = b'downloaded_data'

    # Need to simulate running the script's main block
    # This is often tricky and might be better tested via integration tests
    # or by refactoring the main logic into a testable function.
    # For demonstration:
    # with patch('__main__.__name__', '__main__'): # This doesn't work reliably
    #     exec(open("Assist_nw.py").read()) # Avoid exec if possible

    # Instead, test the conditional logic directly if refactored:
    def run_main_logic():
        if Assist_nw.assist_now_enabled:
            data = Assist_nw.download_assist_now_data()
            if data is not None:
                Assist_nw.send_assist_now_data(data)
            else:
                print("AssistNow Offline-Daten konnten nicht heruntergeladen werden.")
        else:
            print("AssistNow Offline ist deaktiviert.")

    run_main_logic()
    mock_download.assert_called_once()
    mock_send.assert_called_once_with(b'downloaded_data')


@patch('Assist_nw.download_assist_now_data')
@patch('Assist_nw.send_assist_now_data')
@patch.dict('os.environ', {'ASSIST_NOW_ENABLED': 'False'})
def test_main_block_disabled(mock_send, mock_download, capsys):
    """Test main execution path when disabled."""
    import importlib
    importlib.reload(Assist_nw)  # Reload to get patched env var

    def run_main_logic():
        if Assist_nw.assist_now_enabled:
            data = Assist_nw.download_assist_now_data()
            if data is not None:
                Assist_nw.send_assist_now_data(data)
            else:
                print("AssistNow Offline-Daten konnten nicht heruntergeladen werden.")
        else:
            print("AssistNow Offline ist deaktiviert.")

    run_main_logic()
    mock_download.assert_not_called()
    mock_send.assert_not_called()
    captured = capsys.readouterr()
    assert "AssistNow Offline ist deaktiviert." in captured.out
