import pytest
from utils import read_gps_data_from_csv_string


def test_read_gps_data_valid():
    """Tests reading valid CSV data."""
    csv_string = "46.1,7.1,100.1,5\n46.2,7.2,100.2,6\n46.3,7.3,100.3,7"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        {"lat": 46.2, "lon": 7.2, "timestamp": 100.2, "satellites": 6.0},
        {"lat": 46.3, "lon": 7.3, "timestamp": 100.3, "satellites": 7.0},
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_with_end_marker():
    """Tests reading CSV data containing the end marker."""
    csv_string = "46.1,7.1,100.1,5\n-1,-1,-1,-1\n46.3,7.3,100.3,7"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # The -1 line should be ignored based on the code logic
        {"lat": 46.3, "lon": 7.3, "timestamp": 100.3, "satellites": 7.0},
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_empty_string():
    """Tests reading an empty CSV string."""
    csv_string = ""
    expected = []
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_invalid_values(capsys):
    """Tests reading CSV with invalid numeric values."""
    csv_string = "46.1,7.1,100.1,5\n46.invalid,7.2,100.2,6\n46.3,7.3,100.3,abc"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # The lines with invalid values should be skipped and logged
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected
    captured = capsys.readouterr()
    assert "Fehler: Ungültige Werte in Zeile" in captured.out
    # Check for both invalid lines being reported
    assert "'lat': '46.invalid'" in captured.out
    assert "'satellites': 'abc'" in captured.out


def test_read_gps_data_malformed_csv(capsys):
    """Tests reading CSV with lines having wrong number of columns (handled by DictReader)."""
    # DictReader assigns None to missing fields if fieldnames are provided
    csv_string = "46.1,7.1,100.1,5\n46.2,7.2\n46.3,7.3,100.3,7,extra"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # The second line will likely cause ValueError during float conversion as timestamp/satellites are None
        {"lat": 46.3, "lon": 7.3, "timestamp": 100.3, "satellites": 7.0},  # Extra field ignored by DictReader
    ]
    result = read_gps_data_from_csv_string(csv_string)
    # Depending on exact DictReader behavior and error handling, assert might need adjustment
    assert result == expected
    captured = capsys.readouterr()
    # Expect an error log for the line with missing fields causing float(None)
    assert "Fehler: Ungültige Werte in Zeile" in captured.out
    assert "'lat': '46.2'" in captured.out  # Check it tried to process the line
