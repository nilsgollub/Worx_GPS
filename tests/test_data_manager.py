# tests/test_data_manager.py
import unittest
import os
import json
import time
from unittest.mock import patch, mock_open, MagicMock, call
from collections import deque
from datetime import datetime, timedelta
from data_manager import DataManager
from config import PROBLEM_CONFIG # Importiere Konfiguration

# Mock-Konfiguration für Tests
MOCK_PROBLEM_CONFIG = {
    "problem_json": "test_problemzonen.json", # Eigener Dateiname für Tests
    "max_problemzonen": 5 # Kleinere maxlen für Tests
}

@patch.dict('data_manager.PROBLEM_CONFIG', MOCK_PROBLEM_CONFIG, clear=True)
class TestDataManager(unittest.TestCase):
    """
    Testet die DataManager Klasse.
    """

    def setUp(self):
        """
        Setzt die Testumgebung für jeden Test auf.
        """
        self.test_problem_file = MOCK_PROBLEM_CONFIG["problem_json"]
        # Stelle sicher, dass die Testdatei vor jedem Test nicht existiert
        if os.path.exists(self.test_problem_file):
            os.remove(self.test_problem_file)

        # Mocke os.path.exists, um das Laden zu steuern
        with patch('data_manager.os.path.exists') as mock_exists:
             mock_exists.return_value = False # Standardmässig existiert die Datei nicht
             self.data_manager = DataManager()

        # Überprüfe Initialisierungswerte
        self.assertEqual(self.data_manager.problem_json, self.test_problem_file)
        self.assertEqual(self.data_manager.max_problemzonen, MOCK_PROBLEM_CONFIG["max_problemzonen"])
        self.assertIsInstance(self.data_manager.problemzonen_data, deque)
        self.assertEqual(self.data_manager.problemzonen_data.maxlen, MOCK_PROBLEM_CONFIG["max_problemzonen"])
        self.assertEqual(len(self.data_manager.problemzonen_data), 0) # Sollte leer sein, da Datei nicht existierte

    def tearDown(self):
        """
        Räumt nach jedem Test auf.
        """
        # Lösche die Testdatei, falls sie erstellt wurde
        if os.path.exists(self.test_problem_file):
            os.remove(self.test_problem_file)

    def test_save_gps_data(self):
        """Testet das Speichern von GPS-Daten."""
        test_filename = "test_gps_data.json"
        test_data = [{"lat": 46.1, "lon": 7.1, "timestamp": 1000.0}]

        # Mocke open, um den Schreibvorgang abzufangen
        m = mock_open()
        with patch("data_manager.open", m):
            self.data_manager.save_gps_data(test_data, test_filename)

            # Überprüfe, ob open mit den richtigen Argumenten aufgerufen wurde
            m.assert_called_once_with(test_filename, "w")
            # Überprüfe, ob json.dump mit den richtigen Daten aufgerufen wurde
            handle = m() # Hole das Dateihandle-Mock
            handle.write.assert_called_once_with(json.dumps(test_data))

        # Aufräumen (obwohl die Datei nicht wirklich erstellt wurde)
        if os.path.exists(test_filename):
             os.remove(test_filename)


    def test_save_and_load_problemzonen_data(self):
        """Testet das Speichern und anschliessende Laden von Problemzonen."""
        # 1. Daten speichern
        data_to_save = [
            {"lat": 46.1, "lon": 7.1, "timestamp": time.time() - 10},
            {"lat": 46.2, "lon": 7.2, "timestamp": time.time()},
        ]
        # Erstelle eine Deque zum Speichern
        problem_deque = deque(data_to_save, maxlen=self.data_manager.max_problemzonen)

        # Mocke open für den Schreibvorgang
        m_write = mock_open()
        with patch("data_manager.open", m_write):
            self.data_manager.save_problemzonen_data(problem_deque)

            m_write.assert_called_once_with(self.test_problem_file, "w")
            handle_write = m_write()
            # Überprüfe, ob die Deque als Liste gespeichert wurde
            handle_write.write.assert_called_once_with(json.dumps(list(problem_deque)))

        # 2. Neuen DataManager initialisieren, der die Daten laden soll
        # Mocke os.path.exists, damit die Datei gefunden wird
        # Mocke open für den Lesevorgang
        m_read = mock_open(read_data=json.dumps(data_to_save))
        with patch('data_manager.os.path.exists') as mock_exists:
            mock_exists.return_value = True
            with patch("data_manager.open", m_read):
                new_data_manager = DataManager()

                # Überprüfe, ob die Datei gelesen wurde
                m_read.assert_called_once_with(self.test_problem_file, "r")
                # Überprüfe, ob die Daten korrekt in die Deque geladen wurden
                self.assertEqual(len(new_data_manager.problemzonen_data), len(data_to_save))
                # Vergleiche als Listen, da die Reihenfolge in Deques wichtig ist
                self.assertEqual(list(new_data_manager.problemzonen_data), data_to_save)
                # Überprüfe maxlen
                self.assertEqual(new_data_manager.problemzonen_data.maxlen, MOCK_PROBLEM_CONFIG["max_problemzonen"])


    def test_load_problemzonen_data_file_not_exist(self):
        """Testet das Laden, wenn die Problemzonen-Datei nicht existiert."""
        # setUp stellt sicher, dass die Datei nicht existiert und mockt exists=False
        # DataManager wird in setUp initialisiert
        self.assertEqual(len(self.data_manager.problemzonen_data), 0)

    def test_load_problemzonen_data_json_error(self):
        """Testet das Laden, wenn die JSON-Datei korrupt ist."""
        # Erstelle eine ungültige JSON-Datei
        with open(self.test_problem_file, "w") as f:
            f.write("[{'lat': 46.1, 'lon': 7.1, ]") # Ungültiges JSON

        # Mocke os.path.exists, damit die Datei gefunden wird
        with patch('data_manager.os.path.exists') as mock_exists:
             mock_exists.return_value = True
             # Mocke print, um Fehlermeldung zu unterdrücken
             with patch('builtins.print'):
                 new_data_manager = DataManager()
                 # Der Puffer sollte trotz Fehler leer sein
                 self.assertEqual(len(new_data_manager.problemzonen_data), 0)

    def test_read_problemzonen_data(self):
        """Testet das Zurückgeben der aktuellen Problemzonen."""
        test_data = [{"lat": 46.1, "lon": 7.1, "timestamp": time.time()}]
        self.data_manager.problemzonen_data = deque(test_data, maxlen=self.data_manager.max_problemzonen)
        read_data = self.data_manager.read_problemzonen_data()
        # read_problemzonen_data sollte die Deque zurückgeben
        self.assertIsInstance(read_data, deque)
        self.assertEqual(list(read_data), test_data)

    def test_remove_old_problemzonen(self):
        """Testet das Entfernen alter Problemzonen."""
        now = datetime.now()
        current_ts = now.timestamp()
        old_ts = (now - timedelta(days=70)).timestamp() # Älter als 60 Tage
        recent_ts = (now - timedelta(days=10)).timestamp() # Jünger als 60 Tage

        initial_data = [
            {"lat": 46.1, "lon": 7.1, "timestamp": old_ts},
            {"lat": 46.2, "lon": 7.2, "timestamp": recent_ts},
            {"lat": 46.3, "lon": 7.3, "timestamp": current_ts},
        ]
        self.data_manager.problemzonen_data = deque(initial_data, maxlen=self.data_manager.max_problemzonen)

        self.data_manager.remove_old_problemzonen()

        # Erwartet: Nur die neueren Einträge sollten übrig bleiben
        expected_data = [
            {"lat": 46.2, "lon": 7.2, "timestamp": recent_ts},
            {"lat": 46.3, "lon": 7.3, "timestamp": current_ts},
        ]
        self.assertEqual(list(self.data_manager.problemzonen_data), expected_data)

    def test_remove_old_problemzonen_empty(self):
        """Testet remove_old_problemzonen mit leerer Liste."""
        self.assertEqual(len(self.data_manager.problemzonen_data), 0)
        self.data_manager.remove_old_problemzonen()
        self.assertEqual(len(self.data_manager.problemzonen_data), 0)

    @patch('data_manager.os.listdir')
    def test_get_next_mow_filename_no_files(self, mock_listdir):
        """Testet get_next_mow_filename, wenn keine Mäh-Dateien existieren."""
        mock_listdir.return_value = ["other_file.txt", "config.py"] # Keine Mäh-Dateien
        next_filename = self.data_manager.get_next_mow_filename()
        self.assertEqual(next_filename, "maehvorgang_1.json")
        mock_listdir.assert_called_once_with(".") # Standardmässig aktueller Ordner

    @patch('data_manager.os.listdir')
    def test_get_next_mow_filename_with_files(self, mock_listdir):
        """Testet get_next_mow_filename, wenn bereits Mäh-Dateien existieren."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_3.json", "maehvorgang_2.json", "other.txt"]
        next_filename = self.data_manager.get_next_mow_filename(folder="some/folder")
        self.assertEqual(next_filename, "maehvorgang_4.json") # Höchste Nummer war 3 -> nächste ist 4
        mock_listdir.assert_called_once_with("some/folder")

    @patch('data_manager.os.listdir')
    def test_get_next_mow_filename_invalid_files(self, mock_listdir):
        """Testet get_next_mow_filename mit ungültigen Dateinamen."""
        mock_listdir.return_value = ["maehvorgang_1.json", "maehvorgang_abc.json", "maehvorgang_2.txt"]
        with patch('builtins.print'): # Unterdrücke Fehlermeldung
            next_filename = self.data_manager.get_next_mow_filename()
        self.assertEqual(next_filename, "maehvorgang_2.json") # Höchste gültige Nummer war 1 -> nächste ist 2

    @patch('data_manager.glob.glob')
    @patch('data_manager.open', new_callable=mock_open)
    @patch('data_manager.json.load')
    def test_load_all_mow_data(self, mock_json_load, mock_open_func, mock_glob):
        """Testet das Laden aller Mähvorgangsdaten."""
        test_folder = "mow_data"
        files = [os.path.join(test_folder, "maehvorgang_1.json"), os.path.join(test_folder, "maehvorgang_2.json")]
        mock_glob.return_value = files

        # Simuliere die Daten, die json.load zurückgeben soll
        data1 = [{"lat": 1.0}]
        data2 = [{"lat": 2.0}]
        mock_json_load.side_effect = [data1, data2]

        all_data = self.data_manager.load_all_mow_data(folder=test_folder)

        # Überprüfe glob Aufruf
        mock_glob.assert_called_once_with(os.path.join(test_folder, "maehvorgang_*.json"))

        # Überprüfe open und json.load Aufrufe
        expected_open_calls = [call(files[0], "r"), call(files[1], "r")]
        mock_open_func.assert_has_calls(expected_open_calls)
        self.assertEqual(mock_json_load.call_count, 2)

        # Überprüfe das Ergebnis
        self.assertEqual(all_data, [data1, data2])

    @patch('data_manager.os.listdir')
    @patch('data_manager.os.path.getctime')
    @patch('data_manager.os.path.join', side_effect=lambda *args: "/".join(args)) # Einfaches Mock für Pfad-Join
    @patch('data_manager.open', new_callable=mock_open)
    @patch('data_manager.json.load')
    def test_load_last_mow_data(self, mock_json_load, mock_open_func, mock_join, mock_getctime, mock_listdir):
        """Testet das Laden des letzten Mähvorgangs."""
        test_folder = "mower_logs"
        files_in_dir = ["maehvorgang_1.json", "maehvorgang_3.json", "maehvorgang_2.json", "other.txt"]
        mock_listdir.return_value = files_in_dir

        # Mocke ctime, um maehvorgang_3.json zur neuesten zu machen
        def ctime_side_effect(path):
            if path.endswith("maehvorgang_1.json"): return 100
            if path.endswith("maehvorgang_2.json"): return 300
            if path.endswith("maehvorgang_3.json"): return 500 # Neueste
            return 0
        mock_getctime.side_effect = ctime_side_effect

        # Simuliere die Daten, die json.load zurückgeben soll (nur für die neueste Datei)
        last_data = [{"lat": 3.0}]
        mock_json_load.return_value = last_data

        loaded_data = self.data_manager.load_last_mow_data(folder=test_folder)

        # Überprüfe listdir Aufruf
        mock_listdir.assert_called_once_with(test_folder)
        # Überprüfe getctime Aufrufe (sollte für alle Mäh-Dateien aufgerufen werden)
        self.assertEqual(mock_getctime.call_count, 3)
        # Überprüfe open und json.load (nur für die neueste Datei)
        mock_open_func.assert_called_once_with(f"{test_folder}/maehvorgang_3.json", "r")
        mock_json_load.assert_called_once()

        # Überprüfe das Ergebnis
        self.assertEqual(loaded_data, last_data)

    @patch('data_manager.os.listdir')
    def test_load_last_mow_data_no_files(self, mock_listdir):
        """Testet load_last_mow_data, wenn keine Mäh-Dateien existieren."""
        mock_listdir.return_value = []
        loaded_data = self.data_manager.load_last_mow_data()
        self.assertEqual(loaded_data, [])


if __name__ == '__main__':
    unittest.main()

