# tests/test_heatmap_generator.py
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import folium  # Import folium for spec
from selenium.common.exceptions import WebDriverException  # Import specific exception

# Importiere die zu testende Klasse und die verwendeten Konfigurationen
from heatmap_generator import HeatmapGenerator
from config import HEATMAP_CONFIG as REAL_HEATMAP_CONFIG
from config import GEO_CONFIG as REAL_GEO_CONFIG

# Mock-Konfigurationen für Tests
GEO_CONFIG_MOCK = REAL_GEO_CONFIG.copy()
GEO_CONFIG_MOCK["map_center"] = (45.0, 10.0)
GEO_CONFIG_MOCK["zoom_start"] = 12

HEATMAP_CONFIG_MOCK = REAL_HEATMAP_CONFIG.copy()
HEATMAP_CONFIG_MOCK["tile"] = 'Stamen Terrain'  # Use a different tile for testing


# --- Testklasse ---
# Patch die Konfigurationen und externe Abhängigkeiten im heatmap_generator Modul
@patch('heatmap_generator.GEO_CONFIG', GEO_CONFIG_MOCK)
@patch('heatmap_generator.HEATMAP_CONFIG', HEATMAP_CONFIG_MOCK)
@patch('heatmap_generator.folium.Map')
@patch('heatmap_generator.folium.plugins.HeatMap')
@patch('heatmap_generator.folium.PolyLine')
@patch('heatmap_generator.webdriver.Chrome')  # Patch webdriver.Chrome
@patch('heatmap_generator.ChromeDriverManager')  # Patch ChromeDriverManager
class TestHeatmapGenerator:

    @pytest.fixture(autouse=True)
    # --- KORREKTUR: Mocks aus Signatur entfernt ---
    def setup_mocks(self, MockDriverManager, MockWebDriver, MockPolyLine, MockHeatMap, MockFoliumMap):
        """Setzt Mocks für externe Abhängigkeiten auf."""
        self.MockFoliumMap = MockFoliumMap
        self.mock_map_instance = MockFoliumMap.return_value
        self.MockHeatMap = MockHeatMap
        self.mock_heatmap_instance = MockHeatMap.return_value
        self.MockPolyLine = MockPolyLine
        self.mock_polyline_instance = MockPolyLine.return_value
        self.MockWebDriver = MockWebDriver
        self.mock_driver_instance = MockWebDriver.return_value
        self.MockDriverManager = MockDriverManager
        self.mock_driver_manager_instance = MockDriverManager.return_value
        # Mock install() method
        self.mock_driver_manager_instance.install.return_value = "/path/to/mock/chromedriver"

        # Instanz des Generators erstellen
        self.generator = HeatmapGenerator()
        yield  # Lässt den Test laufen

    # Die Tests benötigen die Mocks nicht mehr als Argumente
    def test_heatmap_generator_init(self):
        """Tests the initialization of HeatmapGenerator."""
        assert self.generator.map_center == GEO_CONFIG_MOCK["map_center"]
        assert self.generator.tile == HEATMAP_CONFIG_MOCK["tile"]  # Should use patched config
        assert self.generator.zoom_start == GEO_CONFIG_MOCK["zoom_start"]
        # crop settings are optional in config, check if they exist before asserting
        if "crop_coordinates" in REAL_GEO_CONFIG:
            assert self.generator.crop_coordinates == REAL_GEO_CONFIG["crop_coordinates"]
        if "crop_enabled" in REAL_GEO_CONFIG:
            assert self.generator.crop_enabled == REAL_GEO_CONFIG["crop_enabled"]

    def test_create_heatmap_no_path(self):
        """Tests creating a heatmap without drawing the path."""
        test_data = [
            {'latitude': 45.0, 'longitude': 10.0},
            {'latitude': 45.1, 'longitude': 10.1}
        ]
        html_file = "test_no_path.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=False)

        # Prüfe, ob folium.Map korrekt aufgerufen wurde
        self.MockFoliumMap.assert_called_once_with(
            location=GEO_CONFIG_MOCK["map_center"],
            zoom_start=GEO_CONFIG_MOCK["zoom_start"],
            tiles="OpenStreetMap"  # Hardcoded in create_heatmap
        )

        # Prüfe, ob HeatMap korrekt aufgerufen wurde
        expected_heatmap_data = [[45.0, 10.0], [45.1, 10.1]]
        self.MockHeatMap.assert_called_once_with(expected_heatmap_data)
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)

        # Prüfe, dass PolyLine NICHT aufgerufen wurde
        self.MockPolyLine.assert_not_called()

        # Prüfe, ob die Karte gespeichert wurde
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_with_path(self):
        """Tests creating a heatmap with drawing the path."""
        test_data = [
            {'latitude': 45.0, 'longitude': 10.0},
            {'latitude': 45.1, 'longitude': 10.1},
            {'latitude': 45.2, 'longitude': 10.2}
        ]
        html_file = "test_with_path.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=True)

        self.MockFoliumMap.assert_called_once()  # Details wie oben geprüft
        self.MockHeatMap.assert_called_once()  # Details wie oben geprüft
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)

        # Prüfe, ob PolyLine aufgerufen wurde
        expected_path_data = [[45.0, 10.0], [45.1, 10.1], [45.2, 10.2]]
        self.MockPolyLine.assert_called_once_with(
            expected_path_data, color="blue", weight=2.5, opacity=1
        )
        self.mock_polyline_instance.add_to.assert_called_once_with(self.mock_map_instance)

        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_invalid_data(self, capsys):
        """Tests creating a heatmap with invalid data points."""
        test_data = [
            {'latitude': 45.0, 'longitude': 10.0},
            {'latitude': 'invalid', 'longitude': 10.1},  # Invalid latitude
            {'longitude': 10.2},  # Missing latitude key
            {'latitude': 45.2, 'longitude': 10.3}
        ]
        html_file = "test_invalid.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=False)

        self.MockFoliumMap.assert_called_once()

        # Prüfe, dass HeatMap nur mit den gültigen Punkten aufgerufen wurde
        expected_heatmap_data = [[45.0, 10.0], [45.2, 10.3]]
        self.MockHeatMap.assert_called_once_with(expected_heatmap_data)
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)

        self.MockPolyLine.assert_not_called()
        self.mock_map_instance.save.assert_called_once_with(html_file)

        # Prüfe die Fehlermeldungen
        captured = capsys.readouterr()
        assert "Fehler: Ungültige Werte in Zeile: {'latitude': 'invalid', 'longitude': 10.1}" in captured.out
        assert "Fehler: Ungültige Werte in Zeile: {'longitude': 10.2}" in captured.out

    def test_create_heatmap_empty_data(self):
        """Tests creating a heatmap with empty data."""
        test_data = []
        html_file = "test_empty.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=True)

        self.MockFoliumMap.assert_called_once()
        # HeatMap sollte mit leerer Liste aufgerufen werden
        self.MockHeatMap.assert_called_once_with([])
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)
        # PolyLine sollte nicht aufgerufen werden, da weniger als 2 Punkte
        self.MockPolyLine.assert_not_called()
        self.mock_map_instance.save.assert_called_once_with(html_file)

    @patch('heatmap_generator.HeatmapGenerator.read_csv')
    @patch('heatmap_generator.HeatmapGenerator.create_heatmap')
    def test_generate_heatmap_from_csv(self, mock_create_heatmap, mock_read_csv):
        """Tests the generate_heatmap_from_csv method."""
        mock_read_csv.return_value = [{"lat": 1}]
        csv_file = "input.csv"
        html_file = "output.html"

        self.generator.generate_heatmap_from_csv(csv_file, html_file, draw_path=True)

        mock_read_csv.assert_called_once_with(csv_file)
        mock_create_heatmap.assert_called_once_with([{"lat": 1}], html_file, True)

    @patch("builtins.open", new_callable=mock_open, read_data="latitude,longitude\n45.0,10.0\n45.1,10.1")
    def test_read_csv_success(self, mock_file):
        """Tests successful reading of CSV data."""
        csv_file = "test.csv"
        expected_data = [
            {'latitude': '45.0', 'longitude': '10.0'},
            {'latitude': '45.1', 'longitude': '10.1'}
        ]
        result = self.generator.read_csv(csv_file)
        mock_file.assert_called_once_with(csv_file, 'r', newline='')
        assert result == expected_data

    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    def test_read_csv_file_not_found(self, mock_file, capsys):
        """Tests reading CSV when the file is not found."""
        csv_file = "nonexistent.csv"
        result = self.generator.read_csv(csv_file)
        mock_file.assert_called_once_with(csv_file, 'r', newline='')
        assert result == []  # Should return empty list on error
        captured = capsys.readouterr()
        assert "Fehler beim lesen der CSV Datei" in captured.out

    @pytest.mark.slow  # Mark as slow if it involves actual browser interaction (though mocked here)
    @patch('os.path.abspath')  # Mock abspath
    def test_save_html_as_png_success(self, mock_abspath):
        """Tests saving HTML as PNG successfully."""
        html_file = "test.html"
        png_file = "test.png"
        abs_html_path = "/abs/path/to/test.html"
        mock_abspath.return_value = abs_html_path

        self.generator.save_html_as_png(html_file, png_file)

        # Prüfe Aufrufe an DriverManager und WebDriver
        self.MockDriverManager.assert_called_once()
        self.mock_driver_manager_instance.install.assert_called_once()
        # Prüfe, ob Chrome mit den richtigen Optionen aufgerufen wurde
        # Der Service wird intern erstellt, wir prüfen den Chrome-Aufruf
        args, kwargs = self.MockWebDriver.call_args
        assert kwargs['options'] is not None
        assert "--headless" in kwargs['options'].arguments
        assert kwargs['service'].executable_path == "/path/to/mock/chromedriver"

        # Prüfe Aufrufe an die Driver-Instanz
        self.mock_driver_instance.set_window_size.assert_called_once_with(1200, 1000)
        mock_abspath.assert_called_once_with(html_file)
        self.mock_driver_instance.get.assert_called_once_with(f"file:///{abs_html_path}")
        self.mock_driver_instance.save_screenshot.assert_called_once_with(png_file)
        self.mock_driver_instance.quit.assert_called_once()

    @patch('os.path.abspath', return_value="/abs/path/to/fail.html")
    def test_save_html_as_png_failure(self, mock_abspath, capsys):
        """Tests handling failure during PNG saving."""
        html_file = "fail.html"
        png_file = "fail.png"
        # Simuliere einen Fehler beim WebDriver-Aufruf
        self.mock_driver_instance.save_screenshot.side_effect = WebDriverException("Screenshot failed")

        self.generator.save_html_as_png(html_file, png_file)

        # Prüfe, dass die relevanten WebDriver-Methoden aufgerufen wurden
        self.mock_driver_instance.set_window_size.assert_called_once()
        self.mock_driver_instance.get.assert_called_once()
        self.mock_driver_instance.save_screenshot.assert_called_once_with(png_file)
        self.mock_driver_instance.quit.assert_called_once()  # Quit should still be called

        # Prüfe die Fehlermeldung
        captured = capsys.readouterr()
        assert "Fehler beim Erstellen der PNG Datei: Message: Screenshot failed" in captured.out
