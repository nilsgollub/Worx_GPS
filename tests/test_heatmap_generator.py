import unittest
from unittest.mock import patch, MagicMock
from heatmap_generator import HeatmapGenerator
import os
import platform
import io
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from config import GEO_CONFIG


class TestHeatmapGenerator(unittest.TestCase):
    browser_available = False  # Klassenvariable

    @classmethod
    def setUpClass(cls):
        # Testen ob ein Browser verfügbar ist
        try:
            service = ChromeService(executable_path=ChromeDriverManager().install())
            webdriver.Chrome(service=service)
            cls.browser_available = True
        except WebDriverException as e:
            print(f"Browser konnte nicht gestartet werden: {e}")
            cls.browser_available = False

    def setUp(self):
        self.heatmap_generator = HeatmapGenerator()
        GEO_CONFIG["crop_enabled"] = False

    def tearDown(self):
        # Aufräumen nach den Tests
        if os.path.exists("test_heatmap.html"):
            os.remove("test_heatmap.html")
        # if os.path.exists("test_heatmap.png"):
        #     os.remove("test_heatmap.png")

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

    @unittest.skipIf(not browser_available, "kein Browser verfügbar")
    def test_save_html_as_png(self):
        # Erstellen einer temporären HTML-Datei
        with open("test_heatmap.html", "w") as f:
            f.write("<html></html>")
        # Aufrufen der Funktion
        self.heatmap_generator.save_html_as_png("test_heatmap.html", "test_heatmap.png")
        # Überprüfen ob die Datei vorhanden ist
        self.assertTrue(os.path.exists("test_heatmap.png"))
