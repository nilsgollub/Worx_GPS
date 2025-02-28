import unittest
from unittest.mock import patch, MagicMock
from heatmap_generator import HeatmapGenerator
import os
import platform


class TestHeatmapGenerator(unittest.TestCase):
    def setUp(self):
        self.heatmap_generator = HeatmapGenerator()

    def tearDown(self):
        # Aufräumen nach den Tests
        if os.path.exists("test_heatmap.html"):
            os.remove("test_heatmap.html")
        if os.path.exists("test_heatmap.png"):
            os.remove("test_heatmap.png")
        if os.path.exists("temp.html"):
            os.remove("temp.html")

    def test_create_heatmap(self):
        # Testdaten
        test_data = [[{"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200, "satellites": 10}]]
        # Aufrufen der Funktion
        self.heatmap_generator.create_heatmap(test_data, "test_heatmap.html", False)
        # Überprüfen ob die Datei vorhanden ist
        self.assertTrue(os.path.exists("test_heatmap.html"))

    def test_create_heatmap_path(self):
        # Testdaten
        test_data = [[{"lat": 46.811819, "lon": 7.132838, "timestamp": 1672531200, "satellites": 10},
                      {"lat": 46.811919, "lon": 7.132938, "timestamp": 1672531201, "satellites": 10}]]
        # Aufrufen der Funktion
        self.heatmap_generator.create_heatmap(test_data, "test_heatmap.html", True)
        # Überprüfen ob die Datei vorhanden ist
        self.assertTrue(os.path.exists("test_heatmap.html"))

    @unittest.skipIf(platform.system() == "Linux", "PNG erstellen nicht auf Linux möglich")
    @patch('heatmap_generator.Image.open')
    def test_save_html_as_png(self, mock_open):
        # Erstellen einer temporären HTML-Datei
        with open("test_heatmap.html", "w") as f:
            f.write("<html></html>")
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        # Aufrufen der Funktion
        self.heatmap_generator.save_html_as_png("test_heatmap.html", "test_heatmap.png")
        # Überprüfen ob die Funktion aufgerufen wurde
        mock_open.assert_called_once_with("temp.html")
        # Überprüfen ob die Datei vorhanden ist
        self.assertTrue(os.path.exists("test_heatmap.png"))
