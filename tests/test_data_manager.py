# tests/test_data_manager.py
import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from collections import deque
from datetime import datetime, timedelta
import logging  # Import logging

# Importiere die zu testende Klasse und die verwendete Konfiguration
# from data_manager import DataManager # Importiere innerhalb der Tests wegen Patches
from config import PROBLEM_CONFIG as REAL_PROBLEM_CONFIG

# Mock-Konfiguration für Tests
PROBLEM_CONFIG_MOCK = REAL_PROBLEM_CONFIG.copy()
PROBLEM_CONFIG_MOCK["problem_json"] = "test_problems.json"
PROBLEM_CONFIG_MOCK["max_problemzonen"] = 5  # Kleineres Limit für Tests


# --- Testklasse für Initialisierung ---
# Patch PROBLEM_CONFIG direkt im data_manager Modul
@patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK)
@patch('data_manager.DataManager.load_problemzonen_data')  # Mocke das Laden beim Init
def test_data_manager_init(mock_load_data):
    """Tests the initialization of DataManager."""
    from data_manager import DataManager  # Importiere hier
    dm = DataManager()
    assert dm.problem_json == "test_problems.json"
    assert dm.max_problemzonen == 5
    assert isinstance(dm.problemzonen_data, deque)
    assert dm.problemzonen_data.maxlen == 5
    mock_load_data.assert_called_once()  # Prüfe, ob Laden aufgerufen wurde


# --- Testklasse für Methoden ---
class TestDataManagerMethods:

    @pytest.fixture(autouse=True)
    def setup_method(self, monkeypatch):
        """Setzt eine DataManager-Instanz für jeden Test zurück."""
        # Patch PROBLEM_CONFIG für jede Methode neu
        monkeypatch.setattr("data_manager.PROBLEM_CONFIG", PROBLEM_CONFIG_MOCK)
        # Mocke load_problemzonen_data im __init__, damit Tests nicht von existierenden Dateien abhängen
        with patch('data_manager.DataManager.load_problemzonen_data') as mock_load:
            from data_manager import DataManager  # Importiere hier
            self.dm = DataManager()
        # Stelle sicher, dass das deque für jeden Test leer startet
        self.dm.problemzonen_data.clear()
        # Lösche die Testdatei, falls vorhanden
        if os.path.exists(PROBLEM_CONFIG_MOCK["problem_json"]):
            os.remove(PROBLEM_CONFIG_MOCK["problem_json"])
        yield  # Lässt den Test laufen
        # Aufräumen nach dem Test
        if os.path.exists(PROBLEM_CONFIG_MOCK["problem_json"]):
            os.remove(PROBLEM_CONFIG_MOCK["problem_json"])

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_gps_data_success(self, mock_json_dump, mock_file):
        """Tests successful saving of GPS data."""
        test_data = [{"lat": 1.0, "lon": 2.0}]
        self.dm.save_gps_data(test_data, "gps_test.json")
        mock_file.assert_called_once_with("gps_test.json", "w")
        mock_json_dump.assert_called_once_with(test_data, mock_file())

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_save_gps_data_failure(self, mock_open_error, caplog):  # Use caplog
        """Tests failure during saving GPS data."""
        caplog.set_level(logging.ERROR)
        self.dm.save_gps_data([{"lat": 1.0}], "gps_fail.json")
        # --- KORREKTUR: Assertion angepasst ---
        assert "Fehler beim Speichern der GPS-Daten in gps_fail.json: Disk full" in caplog.text

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_problemzonen_data_success(self, mock_json_dump, mock_file):
        """Tests successful saving of problem zones data."""
        test_data = deque([{"lat": 1.1, "ts": 100}], maxlen=5)
        self.dm.save_problemzonen_data(test_data)
        mock_file.assert_called_once_with(self.dm.problem_json, "w")
        mock_json_dump.assert_called_once_with(list(test_data), mock_file())  # deque wird zur Liste

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": 1.1, "ts": 100}, {"lat": 2.2, "ts": 200}]')
    @patch('json.load')
    def test_load_problemzonen_data_exists(self, mock_json_load, mock_file, mock_exists):
        """Tests loading existing problem zones file."""
        from data_manager import DataManager
        # --- KORREKTUR: Instanziiere innerhalb des Patches ---
        with patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK):
            mock_json_load.return_value = [{"lat": 1.1, "ts": 100}, {"lat": 2.2, "ts": 200}]
            # Instanziiere HIER (ruft __init__ und damit load_problemzonen_data auf)
            dm_load_test = DataManager()

            # Assertions nach Initialisierung
            mock_exists.assert_called_once_with(dm_load_test.problem_json)
            mock_file.assert_called_once_with(dm_load_test.problem_json, "r")
            mock_json_load.assert_called_once_with(mock_file())
            assert len(dm_load_test.problemzonen_data) == 2
            assert list(dm_load_test.problemzonen_data) == [{"lat": 1.1, "ts": 100}, {"lat": 2.2, "ts": 200}]

    @patch('os.path.exists', return_value=False)
    def test_load_problemzonen_data_not_exists(self, mock_exists):
        """Tests loading when problem zones file does not exist."""
        from data_manager import DataManager
        # --- KORREKTUR: Instanziiere innerhalb des Patches ---
        with patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK):
            # Instanziiere HIER
            dm_load_test = DataManager()
            assert len(dm_load_test.problemzonen_data) == 0
            mock_exists.assert_called_once_with(dm_load_test.problem_json)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=IOError("Read error"))
    def test_load_problemzonen_data_read_error(self, mock_open_error, mock_exists, caplog):  # caplog statt capsys
        """Tests handling read error during loading."""
        # --- KORREKTUR: caplog.set_level und Instanziierung ---
        caplog.set_level(logging.ERROR)  # Vorher setzen
        from data_manager import DataManager
        with patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK):
            # Instanziiere HIER
            dm_load_test = DataManager()
            assert len(dm_load_test.problemzonen_data) == 0
            # Check the log output
            assert f"Fehler beim Lesen der Problemzonen-Daten aus {dm_load_test.problem_json}: Read error" in caplog.text

    def test_read_problemzonen_data(self):
        """Tests returning the current problem zones."""
        self.dm.problemzonen_data.append({"lat": 1.0})
        assert self.dm.read_problemzonen_data() == self.dm.problemzonen_data

    def test_remove_old_problemzonen(self):
        """Tests removing old problem zones."""
        now = datetime.now()
        old_time = (now - timedelta(days=70)).timestamp()
        recent_time = (now - timedelta(days=10)).timestamp()
        self.dm.problemzonen_data.extend([
            {"lat": 1.0, "timestamp": old_time},
            {"lat": 2.0, "timestamp": recent_time},
            {"lat": 3.0, "timestamp": old_time},
            {"lat": 4.0}  # Ohne Timestamp
        ])
        self.dm.remove_old_problemzonen()
        # Erwartet: Nur der recente Punkt bleibt übrig
        assert len(self.dm.problemzonen_data) == 1
        assert list(self.dm.problemzonen_data) == [{"lat": 2.0, "timestamp": recent_time}]

    @patch('os.listdir', return_value=[])
    def test_get_next_mow_filename_no_files(self, mock_listdir):
        """Tests getting filename when no files exist."""
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_1.json"
        mock_listdir.assert_called_once_with("test_folder")

    @patch('os.listdir')
    def test_get_next_mow_filename_files_exist(self, mock_listdir):
        """Tests getting filename when files exist."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_3.json", "other_file.txt"]
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_4.json"  # Highest was 3, next is 4

    @patch('os.listdir')
    def test_get_next_mow_filename_invalid_files(self, mock_listdir, caplog):  # Use caplog
        """Tests getting filename with invalid filenames present."""
        caplog.set_level(logging.WARNING)  # Capture warnings
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_invalid.json", "maehvorgang_5.json"]
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_6.json"  # Highest valid was 5, next is 6
        # --- KORREKTUR: Assertion angepasst ---
        assert "Ungültiger Dateiname ignoriert (Fehler beim Parsen): maehvorgang_invalid.json" in caplog.text

    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": 1}]')
    @patch('json.load')
    def test_load_all_mow_data(self, mock_json_load, mock_file, mock_glob):
        """Tests loading all mowing data."""
        mock_glob.return_value = ["folder/maehvorgang_1.json", "folder/maehvorgang_2.json"]
        mock_json_load.side_effect = [[{"lat": 1}], [{"lat": 2}]]  # Return different data for each call
        result = self.dm.load_all_mow_data(folder="folder")
        assert mock_glob.called_once_with(os.path.join("folder", "maehvorgang_*.json"))
        assert mock_file.call_count == 2
        assert mock_json_load.call_count == 2
        assert result == [[{"lat": 1}], [{"lat": 2}]]

    @patch('glob.glob', return_value=[])
    def test_load_all_mow_data_no_files(self, mock_glob):
        """Tests loading when no mowing data files are found."""
        result = self.dm.load_all_mow_data(folder="empty_folder")
        assert result == []
        mock_glob.assert_called_once_with(os.path.join("empty_folder", "maehvorgang_*.json"))

    @patch('os.listdir')
    @patch('os.path.getctime')
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": "latest"}]')
    @patch('json.load')
    def test_load_last_mow_data(self, mock_json_load, mock_file, mock_getctime, mock_listdir):
        """Tests loading the last mowing data file."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_2.json"]

        # Simulate getctime returning different values
        def getctime_side_effect(path):
            if path.endswith("maehvorgang_1.json"):
                return 100
            elif path.endswith("maehvorgang_2.json"):
                return 200  # Newer
            return 0

        mock_getctime.side_effect = getctime_side_effect
        mock_json_load.return_value = [{"lat": "latest"}]

        result = self.dm.load_last_mow_data(folder="test_folder")

        mock_listdir.assert_called_once_with("test_folder")
        assert mock_getctime.call_count == 2
        # Check open was called with the latest file
        mock_file.assert_called_once_with(os.path.join("test_folder", "maehvorgang_2.json"), "r")
        mock_json_load.assert_called_once_with(mock_file())
        assert result == [{"lat": "latest"}]

    @patch('os.listdir', return_value=[])
    def test_load_last_mow_data_no_files(self, mock_listdir):
        """Tests loading last data when no files exist."""
        result = self.dm.load_last_mow_data(folder="test_folder")
        assert result == []
        mock_listdir.assert_called_once_with("test_folder")
