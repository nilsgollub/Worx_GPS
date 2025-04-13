import pytest
import os
from unittest.mock import patch, MagicMock, mock_open, call
import folium  # Required for mocks
import csv
import io

# Mock config before importing HeatmapGenerator
GEO_CONFIG_MOCK = {
    "map_center": (46.8, 7.1),
    "zoom_start": 14,
    "crop_coordinates": ((46.7, 7.0), (46.9, 7.2)),
    "crop_enabled": False,
}
HEATMAP_CONFIG_MOCK = {
    "tile": 'TestTile',
}


# Mock external dependencies that might not be installed in test env or are slow
@patch('heatmap_generator.webdriver')
@patch('heatmap_generator.ChromeDriverManager')
@patch('heatmap_generator.folium.Map')
@patch('heatmap_generator.folium.plugins.HeatMap')
@patch('heatmap_generator.folium.PolyLine')
@patch('heatmap_generator.GEO_CONFIG', GEO_CONFIG_MOCK)
@patch('heatmap_generator.HEATMAP_CONFIG', HEATMAP_CONFIG_MOCK)
class TestHeatmapGenerator:

    @pytest.fixture(autouse=True)
    def setup_mocks(self, MockPolyLine, MockHeatMap, MockFoliumMap, MockDriverManager, MockWebDriver):
        # Store mocks for access within tests if needed
        self.MockPolyLine = MockPolyLine
        self.MockHeatMap = MockHeatMap
        self.MockFoliumMap = MockFoliumMap
        self.mock_map_instance = MockFoliumMap.return_value
        self.mock_map_instance.save = MagicMock()  # Mock the save method

        self.MockWebDriver = MockWebDriver
        self.mock_driver_instance = MockWebDriver.Chrome.return_value
        self.MockDriverManager = MockDriverManager

        # Create generator instance for tests
        from heatmap_generator import HeatmapGenerator
        self.generator = HeatmapGenerator()
        yield  # Run the test

    def test_heatmap_generator_init(self):
        """Tests HeatmapGenerator initialization."""
        assert self.generator.map_center == GEO_CONFIG_MOCK["map_center"]
        assert self.generator.tile == HEATMAP_CONFIG_MOCK[
            "tile"]  # Note: tile is used in code, but not directly set in init
        assert self.generator.zoom_start == GEO_CONFIG_MOCK["zoom_start"]
        assert self.generator.crop_coordinates == GEO_CONFIG_MOCK["crop_coordinates"]
        assert self.generator.crop_enabled == GEO_CONFIG_MOCK["crop_enabled"]

    def test_create_heatmap_no_path(self):
        """Tests creating a heatmap without drawing the path."""
        data = [
            {'latitude': '46.81', 'longitude': '7.11'},  # Use strings as they might come from CSV
            {'latitude': '46.82', 'longitude': '7.12'}
        ]
        html_file = "test_heatmap_no_path.html"

        self.generator.create_heatmap(data, html_file, draw_path=False)

        # Check Map initialization
        self.MockFoliumMap.assert_called_once_with(
            location=self.generator.map_center,
            zoom_start=self.generator.zoom_start,
            tiles="OpenStreetMap"  # Code uses OpenStreetMap directly
        )

        # Check HeatMap plugin call
        expected_points = [[46.81, 7.11], [46.82, 7.12]]
        self.MockHeatMap.assert_called_once_with(expected_points)
        self.MockHeatMap.return_value.add_to.assert_called_once_with(self.mock_map_instance)

        # Check PolyLine was NOT called
        self.MockPolyLine.assert_not_called()

        # Check map save
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_with_path(self):
        """Tests creating a heatmap with drawing the path."""
        data = [
            {'latitude': 46.81, 'longitude': 7.11},  # Use floats
            {'latitude': 46.82, 'longitude': 7.12}
        ]
        html_file = "test_heatmap_with_path.html"

        self.generator.create_heatmap(data, html_file, draw_path=True)

        # Check Map initialization
        self.MockFoliumMap.assert_called_once()

        # Check HeatMap plugin call
        expected_points = [[46.81, 7.11], [46.82, 7.12]]
        self.MockHeatMap.assert_called_once_with(expected_points)
        self.MockHeatMap.return_value.add_to.assert_called_once_with(self.mock_map_instance)

        # Check PolyLine WAS called
        self.MockPolyLine.assert_called_once_with(expected_points, color="blue", weight=2.5, opacity=1)
        self.MockPolyLine.return_value.add_to.assert_called_once_with(self.mock_map_instance)

        # Check map save
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_invalid_data(self, capsys):
        """Tests creating a heatmap with some invalid data points."""
        data = [
            {'latitude': '46.81', 'longitude': '7.11'},
            {'latitude': 'invalid', 'longitude': '7.12'},  # Invalid latitude
            {'longitude': '7.13'},  # Missing latitude key
            {'latitude': 46.83, 'longitude': 7.14}
        ]
        html_file = "test_heatmap_invalid.html"

        self.generator.create_heatmap(data, html_file, draw_path=False)

        # Check HeatMap was called only with valid points
        expected_points = [[46.81, 7.11], [46.83, 7.14]]
        self.MockHeatMap.assert_called_once_with(expected_points)

        # Check logs for errors
        captured = capsys.readouterr()
        assert "Fehler: Ungültige Werte in Zeile: {'latitude': 'invalid', 'longitude': '7.12'}" in captured.out
        assert "could not convert string to float: 'invalid'" in captured.out
        assert "Fehler: Ungültige Werte in Zeile: {'longitude': '7.13'}" in captured.out
        assert "'latitude'" in captured.out  # KeyError message

        # Check map save was still called
        self.mock_map_instance.save.assert_called_once_with(html_file)

    def test_create_heatmap_empty_data(self):
        """Tests creating a heatmap with empty data."""
        data = []
        html_file = "test_heatmap_empty.html"

        self.generator.create_heatmap(data, html_file, draw_path=True)

        # Check HeatMap was called with empty list
        self.MockHeatMap.assert_called_once_with([])
        # Check PolyLine was not called (needs > 1 point)
        self.MockPolyLine.assert_not_called()
        # Check map save
        self.mock_map_instance.save.assert_called_once_with(html_file)

    @patch('heatmap_generator.HeatmapGenerator.read_csv')
    @patch('heatmap_generator.HeatmapGenerator.create_heatmap')
    def test_generate_heatmap_from_csv(self, mock_create_heatmap, mock_read_csv):
        """Tests the generate_heatmap_from_csv wrapper method."""
        csv_file = "input.csv"
        html_file = "output.html"
        mock_data = [{'lat': 1}]
        mock_read_csv.return_value = mock_data

        self.generator.generate_heatmap_from_csv(csv_file, html_file, draw_path=True)

        mock_read_csv.assert_called_once_with(csv_file)
        mock_create_heatmap.assert_called_once_with(mock_data, html_file, True)

    def test_read_csv_success(self):
        """Tests reading a valid CSV file."""
        csv_content = "latitude,longitude,other\n46.1,7.1,a\n46.2,7.2,b"
        # Use mock_open to simulate reading the file
        m_open = mock_open(read_data=csv_content)
        with patch('builtins.open', m_open):
            result = self.generator.read_csv("dummy.csv")

        expected = [
            {'latitude': '46.1', 'longitude': '7.1', 'other': 'a'},
            {'latitude': '46.2', 'longitude': '7.2', 'other': 'b'}
        ]
        assert result == expected
        m_open.assert_called_once_with("dummy.csv", 'r', newline='')

    def test_read_csv_file_not_found(self, capsys):
        """Tests reading a non-existent CSV file."""
        m_open = mock_open()
        m_open.side_effect = FileNotFoundError("File not found error")
        with patch('builtins.open', m_open):
            result = self.generator.read_csv("nonexistent.csv")

        assert result == []
        captured = capsys.readouterr()
        assert "Fehler beim lesen der CSV Datei File not found error" in captured.out

    # Mark test as potentially slow or requiring external setup
    @pytest.mark.slow
    def test_save_html_as_png_success(self):
        """Tests saving HTML as PNG successfully (mocks selenium)."""
        html_file = "test.html"
        png_file = "test.png"
        abs_path = "/abs/path/to/test.html"

        # Mock os.path.abspath
        with patch('os.path.abspath', return_value=abs_path):
            self.generator.save_html_as_png(html_file, png_file)

        # Check WebDriverManager was called
        self.MockDriverManager.assert_called_once()
        self.MockDriverManager.return_value.install.assert_called_once()

        # Check Chrome options (basic check)
        # Need to mock ChromeOptions if specific options are critical
        # from selenium.webdriver.chrome.options import Options as ChromeOptions
        # with patch('heatmap_generator.ChromeOptions') as MockOptions:
        #     ... check options ...

        # Check WebDriver initialization
        self.MockWebDriver.Chrome.assert_called_once()  # Check service and options passed

        # Check driver actions
        self.mock_driver_instance.set_window_size.assert_called_once_with(1200, 1000)
        self.mock_driver_instance.get.assert_called_once_with(f"file:///{abs_path}")
        self.mock_driver_instance.save_screenshot.assert_called_once_with(png_file)
        self.mock_driver_instance.quit.assert_called_once()

    @patch('os.path.abspath', return_value="/abs/path/to/fail.html")
    def test_save_html_as_png_failure(self, mock_abspath, capsys):
        """Tests failure during PNG generation (mocks selenium exception)."""
        html_file = "fail.html"
        png_file = "fail.png"

        # Simulate an error during WebDriver execution
        self.MockWebDriver.Chrome.side_effect = Exception("WebDriver Error")

        self.generator.save_html_as_png(html_file, png_file)

        # Check error log
        captured = capsys.readouterr()
        assert "Fehler beim Erstellen der PNG Datei: WebDriver Error" in captured.out
        # Ensure quit wasn't called if initialization failed
        self.mock_driver_instance.quit.assert_not_called()
