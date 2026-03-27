# tests/test_data_manager.py
import pytest
from unittest.mock import patch, mock_open, MagicMock, call
import json
import os
from datetime import datetime, timedelta
from collections import deque
import logging  # Importiere logging für caplog

# Importiere die zu testende Klasse und Konfigurationen
from data_manager import DataManager
from config import PROBLEM_CONFIG


# --- Testklasse ---
class TestDataManagerMethods:

    @pytest.fixture(autouse=True)
    def setup_mocks_and_instance(self, monkeypatch):
        """Sets up mocks and the DataManager instance for each test."""
        # Mock-Konfiguration anwenden
        mock_problem_config = PROBLEM_CONFIG.copy()
        mock_problem_config["problem_json"] = "test_problemzonen.json"
        mock_problem_config["max_problemzonen"] = 5  # Kleineres Limit für Tests
        monkeypatch.setattr("data_manager.PROBLEM_CONFIG", mock_problem_config)

        # Mock os.path.exists für load_problemzonen_data
        with patch('data_manager.os.path.exists', return_value=False) as self.mock_exists:
            # Mock open für load_problemzonen_data (wird im Test ggf. überschrieben)
            with patch('builtins.open', mock_open()) as self.mock_open_fixture:
                # Mock logging, um Ausgaben zu unterdrücken/prüfen
                with patch('data_manager.logging') as self.mock_logging:
                    # Initialisiere DataManager *nach* dem Patchen
                    self.dm = DataManager()
                    yield  # Test läuft hier

        # Cleanup: Lösche die Testdatei, falls sie erstellt wurde
        if os.path.exists("test_problemzonen.json"):
            try:
                os.remove("test_problemzonen.json")
            except OSError as e:
                print(f"Warnung: Konnte Testdatei test_problemzonen.json nicht löschen: {e}")

    def test_data_manager_init(self):
        """Tests the initialization of DataManager."""
        assert self.dm.problem_json == "test_problemzonen.json"
        assert self.dm.max_problemzonen == 5
        assert isinstance(self.dm.problemzonen_data, deque)
        assert len(self.dm.problemzonen_data) == 0
        # Prüfe, ob load_problemzonen_data aufgerufen wurde (indirekt durch __init__)
        self.mock_exists.assert_called_with("test_problemzonen.json")
        self.mock_logging.info.assert_any_call("DataManager initialisiert.")

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_gps_data_success(self, mock_json_dump, mock_file):
        """Tests successful saving of GPS data."""
        test_data = [{"lat": 1, "lon": 2}]
        filename = "test_gps.json"
        self.dm.save_gps_data(test_data, filename)
        mock_file.assert_called_once_with(filename, "w")
        mock_json_dump.assert_called_once_with(test_data, mock_file())
        self.mock_logging.info.assert_called_with(f"GPS-Daten erfolgreich in {filename} gespeichert.")

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_save_gps_data_failure(self, mock_file):
        """Tests failure during saving GPS data."""
        test_data = [{"lat": 1, "lon": 2}]
        filename = "test_gps_fail.json"
        self.dm.save_gps_data(test_data, filename)
        mock_file.assert_called_once_with(filename, "w")
        self.mock_logging.error.assert_called_with(f"Fehler beim Speichern der GPS-Daten in {filename}: Disk full")

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_problemzonen_data_success(self, mock_json_dump, mock_file):
        """Tests successful saving of problem zone data."""
        test_data = deque([{"lat": 3, "lon": 4, "timestamp": 123}])
        self.dm.save_problemzonen_data(test_data)
        mock_file.assert_called_once_with(self.dm.problem_json, "w")
        # Prüfe, ob deque korrekt in Liste umgewandelt wurde
        mock_json_dump.assert_called_once_with([{"lat": 3, "lon": 4, "timestamp": 123}], mock_file())
        self.mock_logging.info.assert_called_with(
            f"Problemzonen-Daten erfolgreich in {self.dm.problem_json} gespeichert.")

    @patch('data_manager.os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": 5, "lon": 6}]')
    @patch('json.load')
    def test_load_problemzonen_data_exists(self, mock_json_load, mock_file, mock_exists):
        """Tests loading existing problem zone data."""
        mock_json_load.return_value = [{"lat": 5, "lon": 6}]
        # Erstelle eine neue Instanz, damit __init__ die Mocks verwendet
        # Wichtig: Verwende die gleichen Mocks wie im Setup, um Konflikte zu vermeiden
        with patch('data_manager.logging', self.mock_logging):  # Verwende den gemockten Logger
            dm = DataManager()

        mock_exists.assert_called_with(dm.problem_json)
        mock_file.assert_called_once_with(dm.problem_json, "r")
        mock_json_load.assert_called_once()
        assert len(dm.problemzonen_data) == 1
        assert dm.problemzonen_data[0] == {"lat": 5, "lon": 6}
        self.mock_logging.info.assert_any_call(f"1 Problemzonen aus {dm.problem_json} geladen.")

    @patch('data_manager.os.path.exists', return_value=False)
    def test_load_problemzonen_data_not_exists(self, mock_exists):
        """Tests loading when problem zone file does not exist."""
        # Erstelle eine neue Instanz
        with patch('data_manager.logging', self.mock_logging):
            dm = DataManager()
        mock_exists.assert_called_with(dm.problem_json)
        assert len(dm.problemzonen_data) == 0
        self.mock_logging.info.assert_any_call(
            f"Problemzonen-Datei {dm.problem_json} nicht gefunden. Starte mit leerer Liste.")

    @patch('data_manager.os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_load_problemzonen_data_read_error(self, mock_file, mock_exists):
        """Tests handling read errors when loading problem zones."""
        # Erstelle eine neue Instanz
        with patch('data_manager.logging', self.mock_logging):
            dm = DataManager()
        mock_exists.assert_called_with(dm.problem_json)
        mock_file.assert_called_once_with(dm.problem_json, "r")
        assert len(dm.problemzonen_data) == 0
        self.mock_logging.error.assert_any_call(
            f"Fehler beim Lesen der Problemzonen-Daten aus {dm.problem_json}: Permission denied")

    def test_read_problemzonen_data(self):
        """Tests returning the current problem zone data."""
        test_item = {"lat": 7, "lon": 8}
        self.dm.problemzonen_data.append(test_item)
        result = self.dm.read_problemzonen_data()
        assert result is self.dm.problemzonen_data
        assert len(result) == 1
        assert result[0] == test_item

    def test_remove_old_problemzonen(self):
        """Tests removing problem zones older than 2 months."""
        now = datetime.now()
        old_timestamp = (now - timedelta(days=70)).timestamp()
        new_timestamp = (now - timedelta(days=10)).timestamp()
        invalid_item = {"lat": 9, "lon": 10}  # Ohne Timestamp
        type_error_item = {"lat": 11, "lon": 12, "timestamp": "not_a_float"}  # String statt float

        self.dm.problemzonen_data.extend([
            {"lat": 1, "lon": 2, "timestamp": old_timestamp},
            {"lat": 3, "lon": 4, "timestamp": new_timestamp},
            {"lat": 5, "lon": 6, "timestamp": old_timestamp},
            invalid_item,
            type_error_item
        ])
        initial_count = len(self.dm.problemzonen_data)
        assert initial_count == 5

        self.dm.remove_old_problemzonen()

        assert len(self.dm.problemzonen_data) == 1  # Nur der neue Eintrag bleibt
        assert self.dm.problemzonen_data[0]["lat"] == 3
        # Prüfe Logging für entfernte Elemente
        removed_count = initial_count - len(self.dm.problemzonen_data)
        self.mock_logging.info.assert_any_call(f"{removed_count} alte Problemzonen entfernt.")

        # --- KORREKTUR: Erwarte die korrekte Warnung für beide ungültigen Items ---
        # Das Item ohne Timestamp ('invalid_item') führt zu dieser Warnung:
        self.mock_logging.warning.assert_any_call(
            f"Problemzone ohne gültigen Timestamp gefunden und entfernt: {invalid_item}")
        # Das Item mit String-Timestamp ('type_error_item') führt *auch* zu dieser Warnung,
        # da isinstance(..., (int, float)) fehlschlägt. Der TypeError wird nicht erreicht.
        self.mock_logging.warning.assert_any_call(
            f"Problemzone ohne gültigen Timestamp gefunden und entfernt: {type_error_item}")
        # --- ENDE KORREKTUR ---

    @patch('data_manager.os.listdir', return_value=[])
    def test_get_next_mow_filename_no_files(self, mock_listdir):
        """Tests getting the first filename when no files exist."""
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_1.json"
        mock_listdir.assert_called_once_with("test_folder")

    @patch('data_manager.os.listdir', return_value=["maehvorgang_1.json", "maehvorgang_3.json", "other_file.txt"])
    def test_get_next_mow_filename_files_exist(self, mock_listdir):
        """Tests getting the next filename when files exist."""
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_4.json"  # Höchste war 3, nächste ist 4
        mock_listdir.assert_called_once_with("test_folder")

    @patch('data_manager.os.listdir', return_value=["maehvorgang_abc.json", "maehvorgang_1.json", "maehvorgang_.json"])
    def test_get_next_mow_filename_invalid_files(self, mock_listdir):
        """Tests getting the next filename ignoring invalid filenames."""
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_2.json"  # Höchste gültige war 1, nächste ist 2
        mock_listdir.assert_called_once_with("test_folder")
        # Prüfe, ob Warnungen geloggt wurden
        self.mock_logging.warning.assert_any_call(
            "Ungültiger Dateiname ignoriert (Fehler beim Parsen): maehvorgang_abc.json")
        self.mock_logging.warning.assert_any_call(
            "Ungültiger Dateiname ignoriert (Fehler beim Parsen): maehvorgang_.json")

    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": 1}]')
    @patch('json.load')
    def test_load_all_mow_data(self, mock_json_load, mock_file, mock_glob):
        """Tests loading all mowing data."""
        mock_glob.return_value = ["folder/maehvorgang_1.json", "folder/maehvorgang_2.json"]
        mock_json_load.side_effect = [[{"lat": 1}], [{"lat": 2}]]  # Return different data for each call
        result = self.dm.load_all_mow_data(folder="folder")

        mock_glob.assert_called_once_with(os.path.join("folder", "maehvorgang_*.json"))

        assert mock_file.call_count == 2
        mock_file.assert_any_call("folder/maehvorgang_1.json", "r")
        mock_file.assert_any_call("folder/maehvorgang_2.json", "r")
        assert mock_json_load.call_count == 2
        assert result == [[{"lat": 1}], [{"lat": 2}]]
        self.mock_logging.info.assert_any_call("Lade Daten aus 2 Mähvorgangsdateien in 'folder'...")

    @patch('glob.glob', return_value=[])
    def test_load_all_mow_data_no_files(self, mock_glob):
        """Tests loading all mowing data when no files are found."""
        result = self.dm.load_all_mow_data(folder="empty_folder")
        mock_glob.assert_called_once_with(os.path.join("empty_folder", "maehvorgang_*.json"))
        assert result == []
        self.mock_logging.info.assert_any_call("Keine Mähvorgangsdateien in 'empty_folder' gefunden.")

    @patch('data_manager.os.listdir', return_value=["maehvorgang_1.json", "maehvorgang_2.json"])
    @patch('data_manager.os.path.getctime')
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": "latest"}]')
    @patch('json.load')
    def test_load_last_mow_data(self, mock_json_load, mock_file, mock_getctime, mock_listdir):
        """Tests loading the last mowing data file."""

        # Simuliere, dass Datei 2 neuer ist
        def ctime_side_effect(path):
            if path.endswith("maehvorgang_1.json"):
                return 100
            elif path.endswith("maehvorgang_2.json"):
                return 200
            return 0

        mock_getctime.side_effect = ctime_side_effect
        mock_json_load.return_value = [{"lat": "latest"}]

        result = self.dm.load_last_mow_data(folder="mow_folder")

        mock_listdir.assert_called_once_with("mow_folder")
        # getctime wird für jede Datei aufgerufen
        assert mock_getctime.call_count == 2
        # open wird nur für die neueste Datei aufgerufen
        mock_file.assert_called_once_with(os.path.join("mow_folder", "maehvorgang_2.json"), "r")
        mock_json_load.assert_called_once()
        assert result == [{"lat": "latest"}]
        self.mock_logging.info.assert_any_call(
            f"Lade letzten Mähvorgang: {os.path.join('mow_folder', 'maehvorgang_2.json')}")

    @patch('data_manager.os.listdir', return_value=[])
    def test_load_last_mow_data_no_files(self, mock_listdir):
        """Tests loading last mow data when no files exist."""
        result = self.dm.load_last_mow_data(folder="empty_mow_folder")
        mock_listdir.assert_called_once_with("empty_mow_folder")
        assert result == []
        self.mock_logging.info.assert_any_call("Keine Mähvorgangsdateien in 'empty_mow_folder' gefunden.")
