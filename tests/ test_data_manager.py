import unittest
from unittest.mock import patch, MagicMock
from data_manager import DataManager
import os
import json
import time


class TestDataManager(unittest.TestCase):
    def setUp(self):
        # Vor jedem Test
        self.data_manager = DataManager()

    def tearDown(self):
        # nach jedem Test
        # Problemzonen-Datei löschen
        if os.path.exists(self.data_manager.problem_json):
            os.remove(self.data_manager.problem_json)
        # Alle Test Mähdateien löschen
        for filename in os.listdir("."):
            if filename.startswith("maehvorgang_") and filename.endswith(".json"):
                os.remove(filename)

    def test_save_and_read_problemzonen_data(self):
        # Daten zum Speichern
        data = [{"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200}]
        # Speichern
        self.data_manager.save_problemzonen_data(data)
        # Lesen
        read_data = self.data_manager.read_problemzonen_data()
        # Überprüfen ob die Daten korrekt gespeichert wurden
        self.assertEqual(len(data), len(read_data))
        self.assertEqual(data[0]["lat"], read_data[0]["lat"])
        self.assertEqual(data[0]["lon"], read_data[0]["lon"])

    def test_get_next_mow_filename_empty(self):
        # Erwarteter Dateiname für einen leeren Ordner
        expected_filename = "maehvorgang_1.json"
        # Aufrufen der Funktion
        result = self.data_manager.get_next_mow_filename()
        # Überprüfen ob der Korrekte Dateiname zurückgegeben wird.
        self.assertEqual(result, expected_filename)

    def test_get_next_mow_filename_existing(self):
        # Testdatei erstellen
        with open("maehvorgang_1.json", "w") as f:
            json.dump([], f)
        with open("maehvorgang_5.json", "w") as f:
            json.dump([], f)
        # Erwarteter Dateiname
        expected_filename = "maehvorgang_6.json"
        # Aufrufen der Funktion
        result = self.data_manager.get_next_mow_filename()
        # Überprüfen ob der Korrekte Dateiname zurückgegeben wird.
        self.assertEqual(result, expected_filename)

    def test_remove_old_problemzonen(self):
        # Testdaten mit unterschiedlichen Zeitstempeln
        data = [
            {"lat": 1, "lon": 1, "timestamp": 1609459200},  # älter als 2 Monate
            {"lat": 2, "lon": 2, "timestamp": 1700000000},  # innerhalb von 2 Monaten
        ]
        self.data_manager.problemzonen_data.extend(data)
        # Aufrufen der Funktion
        self.data_manager.remove_old_problemzonen()
        # Überprüfen ob die korrekten Daten gelöscht wurden
        self.assertEqual(len(self.data_manager.problemzonen_data), 1)
        self.assertEqual(self.data_manager.problemzonen_data[0]["lat"], 2)
        self.assertEqual(self.data_manager.problemzonen_data[0]["lon"], 2)

    def test_load_all_mow_data_empty(self):
        # Funktion aufrufen
        result = self.data_manager.load_all_mow_data()
        # Leere Liste erwarten
        self.assertEqual(result, [])

    def test_load_all_mow_data(self):
        # Erstellen der Testdaten
        test_data = [{"lat": 1, "lon": 1, "timestamp": 1609459200}]
        # Erstellen der Testdateien
        with open("maehvorgang_1.json", "w") as f:
            json.dump(test_data, f)
        with open("maehvorgang_2.json", "w") as f:
            json.dump(test_data, f)
        # Aufrufen der Funktion
        result = self.data_manager.load_all_mow_data()
        # korrekte Daten und Anzahl erwarten
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0]["lat"], 1)
        self.assertEqual(result[0][0]["lon"], 1)
        self.assertEqual(result[1][0]["lat"], 1)
        self.assertEqual(result[1][0]["lon"], 1)

    def test_load_last_mow_data_empty(self):
        # Funktion aufrufen
        result = self.data_manager.load_last_mow_data()
        # Leere Liste erwarten
        self.assertEqual(result, [])

    def test_load_last_mow_data(self):
        # Erstellen der Testdaten
        test_data = [{"lat": 1, "lon": 1, "timestamp": 1609459200}]
        # Erstellen der Testdateien
        with open("maehvorgang_1.json", "w") as f:
            json.dump(test_data, f)
        with open("maehvorgang_2.json", "w") as f:
            json.dump(test_data, f)
        # Aufrufen der Funktion
        result = self.data_manager.load_last_mow_data()
        # korrekte Daten und Anzahl erwarten
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 1)
        self.assertEqual(result[0]["lon"], 1)
