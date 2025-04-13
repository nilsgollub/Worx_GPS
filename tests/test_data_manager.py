import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock, call
from collections import deque
from datetime import datetime, timedelta
import time
from freezegun import freeze_time  # For time-based tests

# Mock config before importing DataManager
PROBLEM_CONFIG_MOCK = {
    "problem_json": "test_problems.json",
    "max_problemzonen": 5
}


@patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK)
@patch('data_manager.DataManager.load_problemzonen_data')  # Mock loading during init
def test_data_manager_init(mock_load):
    """Tests DataManager initialization."""
    from data_manager import DataManager
    dm = DataManager()
    assert dm.problem_json == "test_problems.json"
    assert dm.max_problemzonen == 5
    assert isinstance(dm.problemzonen_data, deque)
    assert dm.problemzonen_data.maxlen == 5
    mock_load.assert_called_once()  # Check that load was called


# Need to patch PROBLEM_CONFIG for all tests using DataManager
@patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK)
class TestDataManagerMethods:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        # Ensure load is mocked for each test method within the class
        with patch('data_manager.DataManager.load_problemzonen_data') as self.mock_load:
            from data_manager import DataManager
            self.dm = DataManager()
            # Reset deque for each test
            self.dm.problemzonen_data = deque(maxlen=PROBLEM_CONFIG_MOCK["max_problemzonen"])
            yield  # Allows the test to run

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_gps_data_success(self, mock_json_dump, mock_file):
        """Tests successful saving of GPS data."""
        test_data = [{"lat": 1.0, "lon": 2.0}]
        filename = "gps_test.json"
        self.dm.save_gps_data(test_data, filename)
        mock_file.assert_called_once_with(filename, "w")
        mock_json_dump.assert_called_once_with(test_data, mock_file())

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_save_gps_data_failure(self, mock_open_error, capsys):
        """Tests failure during saving GPS data."""
        self.dm.save_gps_data([{"lat": 1.0}], "gps_fail.json")
        captured = capsys.readouterr()
        assert "Fehler beim Speichern der GPS-Daten: Disk full" in captured.out

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_problemzonen_data_success(self, mock_json_dump, mock_file):
        """Tests successful saving of problem zones (deque to list)."""
        test_deque = deque([{"lat": 1.0, "ts": 123}, {"lat": 2.0, "ts": 456}], maxlen=5)
        self.dm.save_problemzonen_data(test_deque)
        mock_file.assert_called_once_with(self.dm.problem_json, "w")
        # Check that the deque was converted to a list for dumping
        mock_json_dump.assert_called_once_with([{"lat": 1.0, "ts": 123}, {"lat": 2.0, "ts": 456}], mock_file())

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": 1.1, "ts": 100}, {"lat": 2.2, "ts": 200}]')
    @patch('json.load')
    def test_load_problemzonen_data_exists(self, mock_json_load, mock_file, mock_exists):
        """Tests loading existing problem zones file."""
        # We mocked load_problemzonen_data in init, so call it manually here
        # Unpatch the init mock for this specific test instance if needed, or test differently.
        # Let's call the *real* method by bypassing the init mock for this test scope
        from data_manager import DataManager
        with patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK):  # Ensure config is patched
            dm_load_test = DataManager()  # This will call the real load

            mock_exists.assert_called_once_with(dm_load_test.problem_json)
            mock_file.assert_called_once_with(dm_load_test.problem_json, "r")
            mock_json_load.assert_called_once_with(mock_file())
            # Check if data was loaded into the deque (assuming json.load returns the list)
            mock_json_load.return_value = [{"lat": 1.1, "ts": 100}, {"lat": 2.2, "ts": 200}]
            dm_load_test.load_problemzonen_data()  # Call again to process return value
            assert len(dm_load_test.problemzonen_data) == 2
            assert list(dm_load_test.problemzonen_data) == [{"lat": 1.1, "ts": 100}, {"lat": 2.2, "ts": 200}]

    @patch('os.path.exists', return_value=False)
    def test_load_problemzonen_data_not_exists(self, mock_exists):
        """Tests loading when problem zones file does not exist."""
        from data_manager import DataManager
        with patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK):
            dm_load_test = DataManager()  # Calls real load
            assert len(dm_load_test.problemzonen_data) == 0
            mock_exists.assert_called_once_with(dm_load_test.problem_json)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=IOError("Read error"))
    def test_load_problemzonen_data_read_error(self, mock_open_error, mock_exists, capsys):
        """Tests handling read error during loading."""
        from data_manager import DataManager
        with patch('data_manager.PROBLEM_CONFIG', PROBLEM_CONFIG_MOCK):
            dm_load_test = DataManager()  # Calls real load
            assert len(dm_load_test.problemzonen_data) == 0
            captured = capsys.readouterr()
            assert "Fehler beim Lesen der Problemzonen-Daten: Read error" in captured.out

    def test_read_problemzonen_data(self):
        """Tests returning the current problem zones."""
        self.dm.problemzonen_data.append({"lat": 5.0})
        assert self.dm.read_problemzonen_data() == self.dm.problemzonen_data
        assert list(self.dm.read_problemzonen_data()) == [{"lat": 5.0}]

    @freeze_time("2023-10-27 12:00:00")  # Freeze time for consistent testing
    def test_remove_old_problemzonen(self):
        """Tests removing problem zones older than 2 months."""
        now = datetime.now()
        two_months_ago = now - timedelta(days=60)
        three_months_ago = now - timedelta(days=90)

        self.dm.problemzonen_data.extend([
            {"lat": 1.0, "timestamp": three_months_ago.timestamp()},  # Old
            {"lat": 2.0, "timestamp": (two_months_ago + timedelta(days=1)).timestamp()},  # Keep
            {"lat": 3.0, "timestamp": (two_months_ago - timedelta(seconds=1)).timestamp()},  # Old
            {"lat": 4.0, "timestamp": now.timestamp()}  # Keep
        ])
        assert len(self.dm.problemzonen_data) == 4

        self.dm.remove_old_problemzonen()

        assert len(self.dm.problemzonen_data) == 2
        remaining_lats = [item["lat"] for item in self.dm.problemzonen_data]
        assert 1.0 not in remaining_lats
        assert 3.0 not in remaining_lats
        assert 2.0 in remaining_lats
        assert 4.0 in remaining_lats

    @patch('os.listdir')
    def test_get_next_mow_filename_no_files(self, mock_listdir):
        """Tests getting filename when no previous files exist."""
        mock_listdir.return_value = []
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_1.json"
        mock_listdir.assert_called_once_with("test_folder")

    @patch('os.listdir')
    def test_get_next_mow_filename_files_exist(self, mock_listdir):
        """Tests getting filename when previous files exist."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_3.json", "otherfile.txt", "maehvorgang_2.json"]
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_4.json"  # Highest was 3, next is 4
        mock_listdir.assert_called_once_with("test_folder")

    @patch('os.listdir')
    def test_get_next_mow_filename_invalid_files(self, mock_listdir, capsys):
        """Tests getting filename with invalid filenames present."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_invalid.json", "maehvorgang_5.json"]
        filename = self.dm.get_next_mow_filename(folder="test_folder")
        assert filename == "maehvorgang_6.json"  # Highest valid was 5, next is 6
        captured = capsys.readouterr()
        assert "Ungültiger Dateiname: maehvorgang_invalid.json" in captured.out

    @patch('glob.glob')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_load_all_mow_data(self, mock_json_load, mock_file, mock_glob):
        """Tests loading data from all mow files."""
        mock_glob.return_value = ["folder/maehvorgang_1.json", "folder/maehvorgang_2.json"]
        # Define what json.load should return for each file call
        mock_json_load.side_effect = [[{"lat": 1}], [{"lat": 2}]]
        # Define what open().read() should return (not strictly needed if json.load is mocked well)
        mock_file.side_effect = [
            mock_open(read_data='[{"lat": 1}]').return_value,
            mock_open(read_data='[{"lat": 2}]').return_value
        ]

        all_data = self.dm.load_all_mow_data(folder="folder")

        mock_glob.assert_called_once_with(os.path.join("folder", "maehvorgang_*.json"))
        assert mock_file.call_count == 2
        calls = [call(os.path.join("folder", "maehvorgang_1.json"), "r"),
                 call(os.path.join("folder", "maehvorgang_2.json"), "r")]
        mock_file.assert_has_calls(calls, any_order=True)  # Order might vary
        assert mock_json_load.call_count == 2
        assert all_data == [[{"lat": 1}], [{"lat": 2}]]

    @patch('glob.glob', return_value=[])
    def test_load_all_mow_data_no_files(self, mock_glob):
        """Tests loading all data when no files are found."""
        all_data = self.dm.load_all_mow_data(folder="empty_folder")
        assert all_data == []
        mock_glob.assert_called_once_with(os.path.join("empty_folder", "maehvorgang_*.json"))

    @patch('os.listdir')
    @patch('os.path.getctime')
    @patch('os.path.join', side_effect=lambda *args: "/".join(args))  # Simple mock for join
    @patch('builtins.open', new_callable=mock_open, read_data='[{"lat": "last"}]')
    @patch('json.load', return_value=[{"lat": "last"}])
    def test_load_last_mow_data(self, mock_json_load, mock_file, mock_join, mock_getctime, mock_listdir):
        """Tests loading data from the last mow file."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_3.json", "maehvorgang_2.json"]

        # Simulate ctimes to make file 3 the latest
        def ctime_side_effect(path):
            if path == "folder/maehvorgang_1.json": return 100
            if path == "folder/maehvorgang_2.json": return 300
            if path == "folder/maehvorgang_3.json": return 500
            return 0

        mock_getctime.side_effect = ctime_side_effect

        last_data = self.dm.load_last_mow_data(folder="folder")

        mock_listdir.assert_called_once_with("folder")
        # Check getctime was called for each file path
        assert mock_getctime.call_count == 3
        # Check open and load were called for the latest file
        mock_file.assert_called_once_with("folder/maehvorgang_3.json", "r")
        mock_json_load.assert_called_once()
        assert last_data == [{"lat": "last"}]

    @patch('os.listdir', return_value=[])
    def test_load_last_mow_data_no_files(self, mock_listdir):
        """Tests loading last data when no files exist."""
        last_data = self.dm.load_last_mow_data(folder="empty")
        assert last_data == []
        mock_listdir.assert_called_once_with("empty")
