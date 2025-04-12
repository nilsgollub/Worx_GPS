# tests/test_heatmap_generator.py
import unittest
from unittest.mock import patch, mock_open, MagicMock, ANY, call
import os
import io
import csv
from heatmap_generator import HeatmapGenerator
from config import GEO_CONFIG, HEATMAP_CONFIG

# Mock-Konfigurationen für Tests
MOCK_GEO_CONFIG = {
    "map_center": (46.5, 7.5),
    "zoom_start": 16,
    "crop_coordinates": ((46.4, 7.4), (46.6, 7.6)),
    "crop_enabled": False,
    # Weitere GEO_CONFIG Werte hier, falls benötigt
}
MOCK_HEATMAP_CONFIG = {
    "tile": 'CartoDB positron', # Anderer Tile-Layer für Tests
}

# Kombiniere die Mock-Konfigs für den Patch
FULL_MOCK_CONFIG = {
    "GEO_CONFIG": MOCK_GEO_CONFIG,
    "HEATMAP_CONFIG": MOCK_HEATMAP_CONFIG,
}

# Mocke Folium und seine Komponenten
# Wichtig: Mocke die spezifischen Klassen/Funktionen, die verwendet werden
@patch('heatmap_generator.folium.Map')
@patch('heatmap_generator.folium.plugins.HeatMap')
@patch('heatmap_generator.folium.PolyLine')
@patch.dict('heatmap_generator.GEO_CONFIG', MOCK_GEO_CONFIG, clear=True)
@patch.dict('heatmap_generator.HEATMAP_CONFIG', MOCK_HEATMAP_CONFIG, clear=True)
class TestHeatmapGenerator(unittest.TestCase):
    """
    Testet die HeatmapGenerator Klasse.
    Selenium-Tests für PNG-Generierung werden übersprungen oder separat behandelt.
    """

    def setUp(self, mock_polyline, mock_heatmap, mock_map):
        """
        Setzt die Testumgebung für jeden Test auf.
        Die Mocks werden von den Klassen-Decorators übergeben.
        """
        # Speichere die Mocks für die Verwendung in Tests
        self.mock_map_constructor = mock_map
        self.mock_heatmap_constructor = mock_heatmap
        self.mock_polyline_constructor = mock_polyline

        # Erstelle eine Mock-Instanz für das Kartenobjekt
        self.mock_map_instance = MagicMock()
        # Konfiguriere den Map-Konstruktor, um unsere Instanz zurückzugeben
        self.mock_map_constructor.return_value = self.mock_map_instance

        # Erstelle Mock-Instanzen für Heatmap und Polyline (werden an add_to übergeben)
        self.mock_heatmap_instance = MagicMock()
        self.mock_heatmap_constructor.return_value = self.mock_heatmap_instance
        self.mock_polyline_instance = MagicMock()
        self.mock_polyline_constructor.return_value = self.mock_polyline_instance

        # Instanziiere den HeatmapGenerator
        self.heatmap_generator = HeatmapGenerator()

    def test_init(self):
        """Testet die Initialisierungswerte."""
        self.assertEqual(self.heatmap_generator.map_center, MOCK_GEO_CONFIG["map_center"])
        self.assertEqual(self.heatmap_generator.zoom_start, MOCK_GEO_CONFIG["zoom_start"])
        self.assertEqual(self.heatmap_generator.tile, MOCK_HEATMAP_CONFIG["tile"]) # Sollte aus MOCK_HEATMAP_CONFIG kommen
        self.assertEqual(self.heatmap_generator.crop_coordinates, MOCK_GEO_CONFIG["crop_coordinates"])
        self.assertEqual(self.heatmap_generator.crop_enabled, MOCK_GEO_CONFIG["crop_enabled"])

    def test_create_heatmap_no_path(self):
        """Testet create_heatmap ohne Pfadzeichnung."""
        test_data = [
            {'latitude': '46.1', 'longitude': '7.1', 'timestamp': '1000', 'satellites': '5', "state": "moving"},
            {'latitude': '46.2', 'longitude': '7.2', 'timestamp': '1001', 'satellites': '6', "state": "stopped"},
        ]
        html_file = "test_output.html"
        draw_path = False

        self.heatmap_generator.create_heatmap(test_data, html_file, draw_path)

        # Überprüfe Map-Konstruktor Aufruf
        self.mock_map_constructor.assert_called_once_with(
            location=MOCK_GEO_CONFIG["map_center"],
            zoom_start=MOCK_GEO_CONFIG["zoom_start"],
            tiles="OpenStreetMap" # Beachte: Der Code verwendet hartcodiert "OpenStreetMap", nicht den Wert aus der Config
        )

        # Überprüfe HeatMap-Konstruktor Aufruf
        expected_heatmap_points = [[46.1, 7.1], [46.2, 7.2]]
        self.mock_heatmap_constructor.assert_called_once_with(expected_heatmap_points)
        # Überprüfe, ob Heatmap zur Karte hinzugefügt wurde
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)

        # Überprüfe, dass PolyLine NICHT aufgerufen/hinzugefügt wurde
        self.mock_polyline_constructor.assert_not_called()
        self.mock_polyline_instance.add_to.assert_not_called()

        # Überprüfe, ob die Karte gespeichert wurde
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_with_path(self):
        """Testet create_heatmap mit Pfadzeichnung."""
        test_data = [
            {'latitude': '46.1', 'longitude': '7.1'}, # Minimaldaten
            {'latitude': 46.2, 'longitude': 7.2},   # Float-Daten
            {'latitude': '46.3', 'longitude': '7.3'},
        ]
        html_file = "test_path.html"
        draw_path = True

        self.heatmap_generator.create_heatmap(test_data, html_file, draw_path)

        # Überprüfe Map-Konstruktor Aufruf (nur einmal pro Testklasse durch setUp)
        self.mock_map_constructor.assert_called_once()

        # Überprüfe HeatMap-Konstruktor Aufruf
        expected_heatmap_points = [[46.1, 7.1], [46.2, 7.2], [46.3, 7.3]]
        self.mock_heatmap_constructor.assert_called_once_with(expected_heatmap_points)
        self.mock_heatmap_instance.add_to.assert_called_once_with(self.mock_map_instance)

        # Überprüfe PolyLine Aufruf
        expected_path_points = [[46.1, 7.1], [46.2, 7.2], [46.3, 7.3]]
        self.mock_polyline_constructor.assert_called_once_with(
            expected_path_points, color="blue", weight=2.5, opacity=1
        )
        # Überprüfe, ob Polyline zur Karte hinzugefügt wurde
        self.mock_polyline_instance.add_to.assert_called_once_with(self.mock_map_instance)

        # Überprüfe, ob die Karte gespeichert wurde
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_invalid_data(self):
        """Testet create_heatmap mit ungültigen Datenpunkten."""
        test_data = [
            {'latitude': '46.1', 'longitude': '7.1'},
            {'latitude': 'invalid', 'longitude': '7.2'}, # Ungültige Latitude
            {'latitude': '46.3'}, # Fehlende Longitude
            {'latitude': '46.4', 'longitude': '7.4'},
        ]
        html_file = "test_invalid.html"
        draw_path = True

        # Mock print to suppress error message
        with patch('builtins.print'):
             self.heatmap_generator.create_heatmap(test_data, html_file, draw_path)

        # Überprüfe HeatMap-Konstruktor Aufruf (nur mit gültigen Punkten)
        expected_heatmap_points = [[46.1, 7.1], [46.4, 7.4]]
        self.mock_heatmap_constructor.assert_called_once_with(expected_heatmap_points)

        # Überprüfe PolyLine Aufruf (nur mit gültigen Punkten)
        expected_path_points = [[46.1, 7.1], [46.4, 7.4]]
        self.mock_polyline_constructor.assert_called_once_with(
            expected_path_points, color="blue", weight=2.5, opacity=1
        )

        # Überprüfe, ob die Karte gespeichert wurde
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_read_csv_success(self):
        """Testet das erfolgreiche Lesen einer CSV-Datei."""
        csv_content = """latitude,longitude,timestamp,satellites,state
46.1,7.1,1000,5,moving
46.2,7.2,1001,6,stopped
"""
        test_csv_file = "temp_read.csv"
        # Mock open für das Lesen
        m = mock_open(read_data=csv_content)
        with patch("heatmap_generator.open", m):
             data = self.heatmap_generator.read_csv(test_csv_file)

             # Überprüfe open Aufruf
             m.assert_called_once_with(test_csv_file, 'r', newline='')
             # Überprüfe das Ergebnis
             expected_data = [
                 {'latitude': '46.1', 'longitude': '7.1', 'timestamp': '1000', 'satellites': '5', 'state': 'moving'},
                 {'latitude': '46.2', 'longitude': '7.2', 'timestamp': '1001', 'satellites': '6', 'state': 'stopped'},
             ]
             self.assertEqual(data, expected_data)

    def test_read_csv_file_not_found(self):
        """Testet das Lesen einer nicht existierenden CSV-Datei."""
        test_csv_file = "non_existent.csv"
        # Mock open, um FileNotFoundError auszulösen
        m = mock_open()
        m.side_effect = FileNotFoundError("File not found")
        with patch("heatmap_generator.open", m):
             # Mock print to suppress error message
             with patch('builtins.print'):
                  data = self.heatmap_generator.read_csv(test_csv_file)
                  # Sollte leere Liste zurückgeben
                  self.assertEqual(data, [])

    @patch.object(HeatmapGenerator, 'read_csv') # Mocke read_csv innerhalb der Klasse
    @patch.object(HeatmapGenerator, 'create_heatmap') # Mocke create_heatmap
    def test_generate_heatmap_from_csv(self, mock_create_heatmap, mock_read_csv):
        """Testet generate_heatmap_from_csv."""
        csv_file = "input.csv"
        html_file = "output_from_csv.html"
        draw_path = True

        # Simuliere Rückgabewert von read_csv
        mock_data = [{'lat': '46.1', 'lon': '7.1'}]
        mock_read_csv.return_value = mock_data

        self.heatmap_generator.generate_heatmap_from_csv(csv_file, html_file, draw_path)

        # Überprüfe, ob read_csv aufgerufen wurde
        mock_read_csv.assert_called_once_with(csv_file)
        # Überprüfe, ob create_heatmap mit den gelesenen Daten aufgerufen wurde
        mock_create_heatmap.assert_called_once_with(mock_data, html_file, draw_path)

    # --- Tests für save_html_as_png (Selenium) ---
    # Diese Tests erfordern eine funktionierende Selenium/WebDriver-Umgebung.
    # Sie werden oft separat ausgeführt oder übersprungen, wenn die Umgebung fehlt.

    @unittest.skip("Selenium test requires WebDriver setup")
    @patch('heatmap_generator.webdriver.Chrome')
    @patch('heatmap_generator.ChromeDriverManager')
    @patch('heatmap_generator.os.path.abspath', return_value='/fake/path/to/test.html')
    def test_save_html_as_png_success(self, mock_abspath, mock_driver_manager, mock_chrome):
        """
        Testet save_html_as_png (erfordert Selenium/WebDriver Mocks).
        Wird standardmässig übersprungen.
        """
        mock_driver_instance = MagicMock()
        mock_chrome.return_value = mock_driver_instance
        # Mocke den install Pfad
        mock_manager_instance = MagicMock()
        mock_manager_instance.install.return_value = "/fake/chromedriver/path"
        mock_driver_manager.return_value = mock_manager_instance

        html_file = "test.html"
        png_file = "test.png"

        # Erstelle eine Dummy-HTML-Datei (optional, da Pfad gemockt ist)
        # with open(html_file, "w") as f: f.write("<html></html>")

        self.heatmap_generator.save_html_as_png(html_file, png_file)

        # Überprüfe, ob WebDriver korrekt initialisiert und verwendet wurde
        mock_chrome.assert_called_once() # Prüfe Optionen genauer, falls nötig
        mock_driver_instance.set_window_size.assert_called_once_with(1200, 1000)
        mock_driver_instance.get.assert_called_once_with("file:///fake/path/to/test.html")
        mock_driver_instance.save_screenshot.assert_called_once_with(png_file)
        mock_driver_instance.quit.assert_called_once()

        # if os.path.exists(html_file): os.remove(html_file)
        # if os.path.exists(png_file): os.remove(png_file) # Wird nicht wirklich erstellt

if __name__ == '__main__':
    unittest.main()
