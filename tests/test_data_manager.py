import unittest
import os
import json
import time  # Korrektur: Import hinzugefügt
from unittest.mock import patch, MagicMock
from data_manager import DataManager
from config import PROBLEM_CONFIG


class TestDataManager(unittest.TestCase):

    def setUp(self):
        self.data_manager = DataManager()
        # Erstellen einer temporären JSON-Datei für Testzwecke
        self.temp_json_file = "temp_problemzonen.json"
        self.data_manager.problem_json = self.temp_json_file
        with open(self.temp_json_file, 'w') as jsonfile:
            json.dump([{"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200}], jsonfile)

    def tearDown(self):
        # Aufräumen nach den Tests
        if os.path.exists(self.temp_json_file):
            os.remove(self.temp_json_file)

    def test_save_and_read_problemzonen_data(self):
        data = [{"lat": 46.811919, "lon": 7.132938, "timestamp": 1672531201}]
        self.data_manager.save_problemzonen_data(data)
        read_data = self.data_manager.read_problemzonen_data()
        self.assertEqual(len(data), len(read_data))

    def test_remove_old_problemzonen(self):
        # Die alten Daten löschen.
        self.data_manager.problemzonen_data = []
        self.data_manager.problemzonen_data.append({"lat": 46.811919, "lon": 7.132938, "timestamp": 1672531201})
        self.data_manager.problemzonen_data.append({"lat": 46.811919, "lon": 7.132938, "timestamp": time.time()})
        self.data_manager.remove_old_problemzonen()
        self.assertEqual(len(self.data_manager.problemzonen_data), 1)
