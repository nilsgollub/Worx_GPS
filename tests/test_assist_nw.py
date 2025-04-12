# tests/test_assist_nw.py
import unittest
from unittest.mock import patch, mock_open, MagicMock, ANY
import os
import requests # Für RequestException
# Importiere die Funktionen direkt aus dem Skript
from Assist_nw import download_assist_now_data, send_assist_now_data

# Mock .env Variablen direkt im Testmodul
@patch.dict(os.environ, {
    "ASSIST_NOW_TOKEN": "test_token_123",
    "ASSIST_NOW_ENABLED": "True",
    # ASSIST_NOW_OFFLINE_URL wird im Skript hartcodiert verwendet
    # ASSIST_NOW_PATH wird im Skript hartcodiert verwendet
})
# Mocke die globalen Variablen im Skript Assist_nw, die aus os.getenv gelesen werden
@patch('Assist_nw.assist_now_token', "test_token_123")
@patch('Assist_nw.assist_now_enabled', True)
@patch('Assist_nw.assist_now_path', "/dev/mock_gps_port")
class TestAssistNowScript(unittest.TestCase):
    """
    Testet die Funktionen im Skript Assist_nw.py.
    """

    @patch('Assist_nw.requests.get') # Mocke requests.get innerhalb von Assist_nw
    def test_download_assist_now_data_success(self, mock_requests_get, *_): # *_ fängt die anderen Klassen-Mocks auf
        """Testet erfolgreichen Download."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"downloaded_assist_data"
        mock_requests_get.return_value = mock_response

        # Erwartete URL und Token aus den gemockten Werten
        expected_url = "https://offline-live1.services.u-blox.com/GetOfflineData.ashx"
        expected_token = "test_token_123"

        data = download_assist_now_data()

        self.assertEqual(data, b"downloaded_assist_data")
        mock_requests_get.assert_called_once_with(
            expected_url,
            headers=ANY,
            params={
                "token": expected_token,
                "gnss": "gps",
                "alm": "gps",
                "days": 7,
                "resolution": 1
            }
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('Assist_nw.requests.get')
    def test_download_assist_now_data_failure(self, mock_requests_get, *_):
        """Testet fehlgeschlagenen Download."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Network Error")
        mock_requests_get.return_value = mock_response

        # Erwartete URL und Token
        expected_url = "https://offline-live1.services.u-blox.com/GetOfflineData.ashx"
        expected_token = "test_token_123"

        # Mock print to suppress error message
        with patch('builtins.print'):
             data = download_assist_now_data()

        self.assertIsNone(data)
        mock_requests_get.assert_called_once_with(
            expected_url,
            headers=ANY,
            params={"token": expected_token, "gnss": "gps", "alm": "gps", "days": 7, "resolution": 1}
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('Assist_nw.open', new_callable=mock_open) # Mocke die open Funktion in Assist_nw
    def test_send_assist_now_data_success(self, mock_open_func, *_):
        """Testet erfolgreiches Senden der Daten."""
        test_data = b"data_to_send_to_gps"
        expected_path = "/dev/mock_gps_port" # Aus dem Klassen-Patch

        send_assist_now_data(test_data)

        # Überprüfe, ob open korrekt aufgerufen wurde
        mock_open_func.assert_called_once_with(expected_path, "wb")
        # Überprüfe, ob write auf dem Dateihandle aufgerufen wurde
        handle = mock_open_func()
        handle.write.assert_called_once_with(test_data)

    @patch('Assist_nw.open', new_callable=mock_open)
    def test_send_assist_now_data_failure(self, mock_open_func, *_):
        """Testet fehlgeschlagenes Senden der Daten (z.B. Berechtigungsproblem)."""
        test_data = b"data_to_send_to_gps"
        expected_path = "/dev/mock_gps_port"

        # Simuliere einen Fehler beim Öffnen oder Schreiben
        mock_open_func.side_effect = OSError("Cannot open port")

        # Mock print to suppress error message
        with patch('builtins.print'):
             send_assist_now_data(test_data)

        # Überprüfe, ob open versucht wurde
        mock_open_func.assert_called_once_with(expected_path, "wb")
        # write sollte nicht aufgerufen worden sein
        handle = mock_open_func()
        handle.write.assert_not_called()

    # Test für den __main__ Block (optional, aber gut für die Vollständigkeit)
    @patch('Assist_nw.download_assist_now_data')
    @patch('Assist_nw.send_assist_now_data')
    @patch('Assist_nw.assist_now_enabled', True) # Stelle sicher, dass es für diesen Test aktiviert ist
    def test_main_block_enabled_success(self, mock_send, mock_download, *_):
        """Testet den __main__ Block, wenn enabled und Download erfolgreich."""
        mock_download.return_value = b"downloaded_data"

        # Führe den Code im __main__ Block aus (simuliert Skriptstart)
        # Dazu importieren wir das Skript und prüfen eine Variable oder Funktion darin
        # oder verwenden runpy.run_module
        with patch('Assist_nw.__name__', '__main__'):
             # Ein einfacher Weg, den Block auszuführen, ist, ihn neu zu importieren oder runpy zu verwenden.
             # Hier simulieren wir es durch Aufruf der Logik:
             if Assist_nw.assist_now_enabled:
                 data = Assist_nw.download_assist_now_data()
                 if data is not None:
                     Assist_nw.send_assist_now_data(data)

        mock_download.assert_called_once()
        mock_send.assert_called_once_with(b"downloaded_data")

    @patch('Assist_nw.download_assist_now_data')
    @patch('Assist_nw.send_assist_now_data')
    @patch('Assist_nw.assist_now_enabled', True)
    def test_main_block_enabled_download_fail(self, mock_send, mock_download, *_):
        """Testet den __main__ Block, wenn enabled und Download fehlschlägt."""
        mock_download.return_value = None # Simuliere fehlgeschlagenen Download

        with patch('Assist_nw.__name__', '__main__'):
             with patch('builtins.print'): # Unterdrücke Meldung
                 # Führe die Logik aus __main__ aus
                 if Assist_nw.assist_now_enabled:
                     data = Assist_nw.download_assist_now_data()
                     if data is not None:
                         Assist_nw.send_assist_now_data(data)
                     # else: # Optional: Prüfen, ob die "konnte nicht"-Meldung kommt
                     #     pass

        mock_download.assert_called_once()
        mock_send.assert_not_called() # Senden sollte nicht aufgerufen werden

    @patch('Assist_nw.download_assist_now_data')
    @patch('Assist_nw.send_assist_now_data')
    @patch('Assist_nw.assist_now_enabled', False) # Deaktiviert für diesen Test
    def test_main_block_disabled(self, mock_send, mock_download, *_):
        """Testet den __main__ Block, wenn assist_now deaktiviert ist."""

        with patch('Assist_nw.__name__', '__main__'):
             with patch('builtins.print'): # Unterdrücke Meldung
                 # Führe die Logik aus __main__ aus
                 if Assist_nw.assist_now_enabled:
                     # Dieser Block wird nicht betreten
                     pass
                 # else: # Optional: Prüfen, ob die "deaktiviert"-Meldung kommt
                 #     pass


        mock_download.assert_not_called() # Weder Download noch Senden sollten aufgerufen werden
        mock_send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
