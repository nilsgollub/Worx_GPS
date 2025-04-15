# tests/test_heatmap_generator.py
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import folium  # Import für Patch-Pfade und Typ-Hinweise
from folium import plugins  # Import für Patch-Pfade
import os
import io
# from PIL import Image # PIL wird hier nicht direkt benötigt
# Importiere Selenium und WebDriver Manager für Patch-Pfade
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
import csv
# import json # json wird hier nicht direkt benötigt
import logging  # Import für caplog

# Importiere die zu testende Klasse und Konfigurationen
from heatmap_generator import HeatmapGenerator
from config import HEATMAP_CONFIG, GEO_CONFIG


# --- FIXTURE DEFINITIONS ---
@pytest.fixture
def MockFoliumMap():
    """Fixture to mock folium.Map."""
    with patch('heatmap_generator.folium.Map', autospec=True) as MockMap:
        mock_instance = MockMap.return_value
        mock_instance.save = MagicMock()
        # Mock add_child, da dies intern von add_to aufgerufen wird
        mock_instance.add_child = MagicMock()
        yield MockMap  # Gibt die Mock-Klasse zurück


# --- KORREKTUR: side_effect für add_to wieder einführen ---
@pytest.fixture
def MockHeatMap():
    """Fixture to mock folium.plugins.HeatMap."""
    with patch('heatmap_generator.folium.plugins.HeatMap', autospec=True) as MockHM:
        mock_instance = MockHM.return_value

        # Definiere die side_effect Funktion HIER
        def mock_add_to(map_object):
            # Diese Funktion wird aufgerufen, wenn mock_instance.add_to(map_obj) im Code läuft
            # map_object wird die übergebene Map-Instanz sein (in unserem Test self.mock_map_instance)
            map_object.add_child(mock_instance)  # Rufe add_child auf der übergebenen Map auf

        # Weise die side_effect Funktion dem add_to Mock zu
        mock_instance.add_to = MagicMock(side_effect=mock_add_to)
        yield MockHM  # Gibt die Mock-Klasse zurück


@pytest.fixture
def MockPolyLine():
    """Fixture to mock folium.PolyLine."""
    with patch('heatmap_generator.folium.PolyLine', autospec=True) as MockPL:
        mock_instance = MockPL.return_value

        # Gleiche side_effect Logik wie bei MockHeatMap
        def mock_add_to(map_object):
            map_object.add_child(mock_instance)

        mock_instance.add_to = MagicMock(side_effect=mock_add_to)
        yield MockPL  # Gibt die Mock-Klasse zurück


# --- ENDE KORREKTUR ---

@pytest.fixture
def MockWebDriver():
    """Fixture to mock selenium.webdriver.Chrome."""
    with patch('heatmap_generator.webdriver.Chrome', autospec=True) as MockDriver:
        mock_instance = MockDriver.return_value
        mock_instance.set_window_size = MagicMock()
        mock_instance.get = MagicMock()
        mock_instance.save_screenshot = MagicMock()
        mock_instance.quit = MagicMock()
        yield MockDriver


@pytest.fixture
def MockDriverManager():
    """Fixture to mock webdriver_manager.chrome.ChromeDriverManager."""
    with patch('heatmap_generator.ChromeDriverManager', autospec=True) as MockDM:
        mock_instance = MockDM.return_value
        mock_instance.install.return_value = "/mock/path/to/chromedriver"
        yield MockDM


# --- END FIXTURE DEFINITIONS ---

class TestHeatmapGenerator:

    @pytest.fixture(autouse=True)
    def setup_mocks(self, MockDriverManager, MockWebDriver, MockPolyLine, MockHeatMap, MockFoliumMap, monkeypatch):
        """Sets up mocks and applies config."""
        self.mock_geo = GEO_CONFIG.copy()
        self.mock_heatmap_config = HEATMAP_CONFIG.copy()
        monkeypatch.setattr("heatmap_generator.GEO_CONFIG", self.mock_geo)
        monkeypatch.setattr("heatmap_generator.HEATMAP_CONFIG", self.mock_heatmap_config)

        # Wichtig: Die Instanzen werden hier geholt, *nachdem* die Fixtures gelaufen sind
        self.mock_map_class = MockFoliumMap
        self.mock_map_instance = MockFoliumMap.return_value
        self.mock_heatmap_class = MockHeatMap
        self.mock_heatmap_instance = MockHeatMap.return_value
        self.mock_polyline_class = MockPolyLine
        self.mock_polyline_instance = MockPolyLine.return_value
        self.mock_driver_manager_class = MockDriverManager
        self.mock_webdriver_class = MockWebDriver
        self.mock_driver_instance = MockWebDriver.return_value

        self.generator = HeatmapGenerator()
        yield

    def test_heatmap_generator_init(self):
        """Tests the initialization of HeatmapGenerator."""
        assert self.generator.map_center == self.mock_geo["map_center"]
        assert self.generator.tile == self.mock_heatmap_config["tile"]
        assert self.generator.zoom_start == self.mock_geo["zoom_start"]
        assert self.generator.crop_coordinates == self.mock_geo["crop_coordinates"]
        assert self.generator.crop_enabled == self.mock_geo["crop_enabled"]

    def test_create_heatmap_no_path(self):
        """Tests creating a heatmap without drawing the path."""
        test_data = [{'latitude': '46.0', 'longitude': '7.0'}, {'latitude': '46.1', 'longitude': '7.1'}]
        html_file = "test_heatmap_no_path.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=False)

        self.mock_map_class.assert_called_once_with(
            location=self.generator.map_center,
            zoom_start=self.generator.zoom_start,
            tiles="OpenStreetMap"
        )

        expected_points = [[46.0, 7.0], [46.1, 7.1]]
        self.mock_heatmap_class.assert_called_once_with(expected_points)

        # --- KORREKTUR: Prüfe add_to UND add_child ---
        # 1. Wurde add_to auf dem Plugin mit der Map aufgerufen?
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)
        # 2. Wurde add_child auf der Map mit dem Plugin aufgerufen? (Dank side_effect sollte das jetzt klappen)
        self.mock_map_instance.add_child.assert_any_call(self.mock_heatmap_instance)
        # --- ENDE KORREKTUR ---

        self.mock_polyline_class.assert_not_called()
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_with_path(self):
        """Tests creating a heatmap with drawing the path."""
        test_data = [{'latitude': '46.0', 'longitude': '7.0'}, {'latitude': '46.1', 'longitude': '7.1'}]
        html_file = "test_heatmap_with_path.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=True)

        self.mock_map_class.assert_called_once()
        expected_points = [[46.0, 7.0], [46.1, 7.1]]
        self.mock_heatmap_class.assert_called_once_with(expected_points)

        # --- KORREKTUR: Prüfe add_to UND add_child ---
        # Heatmap
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)
        self.mock_map_instance.add_child.assert_any_call(self.mock_heatmap_instance)

        self.mock_polyline_class.assert_called_once_with(expected_points, color="blue", weight=2.5, opacity=1)

        # Polyline
        self.mock_polyline_instance.add_to.assert_called_once_with(self.mock_map_instance)
        self.mock_map_instance.add_child.assert_any_call(self.mock_polyline_instance)
        # --- ENDE KORREKTUR ---

        self.mock_map_instance.save.assert_called_once_with(html_file)

    @patch('builtins.print')  # heatmap_generator verwendet hier print
    def test_create_heatmap_invalid_data(self, mock_print):
        """Tests creating a heatmap with invalid data points."""
        test_data = [
            {'latitude': '46.0', 'longitude': '7.0'},
            {'latitude': 'invalid', 'longitude': '7.1'},
            {'latitude': '46.2'},
            {'latitude': '46.3', 'longitude': '7.3'}
        ]
        html_file = "test_heatmap_invalid.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=False)

        self.mock_map_class.assert_called_once()
        expected_points = [[46.0, 7.0], [46.3, 7.3]]
        self.mock_heatmap_class.assert_called_once_with(expected_points)

        # --- KORREKTUR: Prüfe add_to UND add_child ---
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)
        self.mock_map_instance.add_child.assert_any_call(self.mock_heatmap_instance)
        # --- ENDE KORREKTUR ---

        mock_print.assert_any_call("Fehler: Ungültige Werte in Zeile: {'latitude': 'invalid', 'longitude': '7.1'}")
        mock_print.assert_any_call("Fehler: Ungültige Werte in Zeile: {'latitude': '46.2'}")
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_empty_data(self):
        """Tests creating a heatmap with empty data."""
        test_data = []
        html_file = "test_heatmap_empty.html"

        self.generator.create_heatmap(test_data, html_file, draw_path=False)

        self.mock_map_class.assert_called_once()
        self.mock_heatmap_class.assert_called_once_with([])

        # --- KORREKTUR: Prüfe add_to UND add_child ---
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)
        self.mock_map_instance.add_child.assert_any_call(self.mock_heatmap_instance)
        # --- ENDE KORREKTUR ---

        self.mock_polyline_class.assert_not_called()
        self.mock_map_instance.save.assert_called_once_with(html_file)

    @patch('heatmap_generator.HeatmapGenerator.read_csv')
    @patch('heatmap_generator.HeatmapGenerator.create_heatmap')
    def test_generate_heatmap_from_csv(self, mock_create_heatmap, mock_read_csv):
        """Tests the main function generating heatmap from CSV."""
        csv_file = "input.csv"
        html_file = "output.html"
        mock_data = [{'latitude': '46.0', 'longitude': '7.0'}]
        mock_read_csv.return_value = mock_data
        self.generator.generate_heatmap_from_csv(csv_file, html_file, draw_path=True)
        mock_read_csv.assert_called_once_with(csv_file)
        mock_create_heatmap.assert_called_once_with(mock_data, html_file, True)

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
    @patch('builtins.print')  # heatmap_generator verwendet hier print
    def test_read_csv_file_not_found(self, mock_print, mock_file):
        """Tests reading a non-existent CSV file."""
        csv_file = "not_found.csv"
        result = self.generator.read_csv(csv_file)
        mock_file.assert_called_once_with(csv_file, 'r', newline='')
        assert result == []
        mock_print.assert_called_with("Fehler beim lesen der CSV Datei File not found")

    @pytest.mark.slow
    @patch('os.path.abspath')
    @patch('heatmap_generator.ChromeService', autospec=True)
    def test_save_html_as_png_success(self, mock_service, mock_abspath):
        """Tests successfully saving HTML as PNG."""
        html_file = "test.html"
        png_file = "test.png"
        mock_abs_path = "/abs/path/to/test.html"
        mock_abspath.return_value = mock_abs_path
        mock_driver_path = "/mock/path/to/chromedriver"
        self.mock_driver_manager_class.return_value.install.return_value = mock_driver_path

        self.generator.save_html_as_png(html_file, png_file)

        self.mock_driver_manager_class.assert_called_once()
        self.mock_driver_manager_class.return_value.install.assert_called_once()
        mock_service.assert_called_once_with(executable_path=mock_driver_path)
        self.mock_webdriver_class.assert_called_once()
        call_args, call_kwargs = self.mock_webdriver_class.call_args
        assert call_kwargs['service'] is mock_service.return_value
        assert isinstance(call_kwargs['options'], ChromeOptions)
        assert "--headless" in call_kwargs['options'].arguments
        assert "--disable-gpu" in call_kwargs['options'].arguments

        self.mock_driver_instance.set_window_size.assert_called_once_with(1200, 1000)
        expected_uri = f"file:///{mock_abs_path.replace(os.sep, '/')}"
        self.mock_driver_instance.get.assert_called_once_with(expected_uri)
        self.mock_driver_instance.save_screenshot.assert_called_once_with(png_file)
        self.mock_driver_instance.quit.assert_called_once()

    @patch('os.path.abspath', return_value="/abs/path/to/fail.html")
    @patch('builtins.print')  # heatmap_generator verwendet hier print
    def test_save_html_as_png_failure(self, mock_print, mock_abspath):
        """Tests failure during PNG saving (e.g., WebDriver error)."""
        html_file = "fail.html"
        png_file = "fail.png"
        self.mock_webdriver_class.side_effect = Exception("WebDriver crashed")

        self.generator.save_html_as_png(html_file, png_file)

        self.mock_driver_manager_class.assert_called_once()
        self.mock_webdriver_class.assert_called_once()
        self.mock_driver_instance.set_window_size.assert_not_called()
        self.mock_driver_instance.get.assert_not_called()
        self.mock_driver_instance.save_screenshot.assert_not_called()
        mock_print.assert_called_with("Fehler beim Erstellen der PNG Datei: WebDriver crashed")
