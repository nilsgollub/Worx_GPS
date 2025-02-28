import unittest
from utils import read_gps_data_from_csv_string


class TestUtils(unittest.TestCase):
    def test_read_gps_data_from_csv_string(self):
        # Testdaten
        csv_string = "46.811819,7.132838,1672531200.0,10\n46.811919,7.132938,1672531201.0,10"
        # Aufrufen der Funktion
        result = read_gps_data_from_csv_string(csv_string)
        # Überprüfen ob die Daten korrekt ausgelesen wurden
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["lat"], 46.811819)
        self.assertEqual(result[0]["lon"], 7.132838)
        self.assertEqual(result[0]["timestamp"], 1672531200.0)
        self.assertEqual(result[0]["satellites"], 10)
        self.assertEqual(result[1]["lat"], 46.811919)
        self.assertEqual(result[1]["lon"], 7.132938)
        self.assertEqual(result[1]["timestamp"], 1672531201.0)
        self.assertEqual(result[1]["satellites"], 10)

    def test_read_gps_data_from_csv_string_wrong(self):
        # Testdaten
        csv_string = "46.811819,7.132838,abc,10\n46.811919,7.132938,1672531201.0,10"
        # Aufrufen der Funktion
        result = read_gps_data_from_csv_string(csv_string)
        # Überprüfen ob die Daten korrekt ausgelesen wurden
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 46.811919)
        self.assertEqual(result[0]["lon"], 7.132938)
        self.assertEqual(result[0]["timestamp"], 1672531201.0)
        self.assertEqual(result[0]["satellites"], 10)

    def test_read_gps_data_from_csv_string_end_marker(self):
        # Testdaten
        csv_string = "-1,7.132838,1672531200.0,10\n46.811919,7.132938,1672531201.0,10"
        # Aufrufen der Funktion
        result = read_gps_data_from_csv_string(csv_string)
        # Überprüfen ob die Daten korrekt ausgelesen wurden
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 46.811919)
        self.assertEqual(result[0]["lon"], 7.132938)
        self.assertEqual(result[0]["timestamp"], 1672531201.0)
        self.assertEqual(result[0]["satellites"], 10)
