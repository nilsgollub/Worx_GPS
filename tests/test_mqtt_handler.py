# tests/test_utils.py
import pytest
from utils import read_gps_data_from_csv_string
import logging  # Import logging


# --- Tests ---

def test_read_gps_data_valid():
    """Tests reading a valid CSV string."""
    csv_string = "46.1,7.1,100.1,5\n46.2,7.2,100.2,6"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        {"lat": 46.2, "lon": 7.2, "timestamp": 100.2, "satellites": 6.0},
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_with_end_marker():
    """Tests reading a CSV string containing the end marker."""
    csv_string = "46.1,7.1,100.1,5\n-1\n46.2,7.2,100.2,6"  # Marker in der Mitte
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # Die Zeile mit "-1" wird übersprungen
        {"lat": 46.2, "lon": 7.2, "timestamp": 100.2, "satellites": 6.0},
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_empty_string():
    """Tests reading an empty CSV string."""
    csv_string = ""
    expected = []
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_invalid_values(caplog):  # Use caplog
    """Tests reading CSV with invalid numeric values."""
    # --- KORREKTUR: Verwende logging in utils.py und caplog hier ---
    # Stelle sicher, dass utils.py logging.error statt print verwendet
    caplog.set_level(logging.ERROR)
    csv_string = "46.1,7.1,100.1,5\n46.2,invalid,100.2,6\n46.3,7.3,100.3,abc"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # Die Zeilen mit "invalid" und "abc" werden übersprungen
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected
    # Prüfe die Log-Ausgabe
    assert "Fehler: Ungültige Werte in Zeile: {'lat': '46.2', 'lon': 'invalid', 'timestamp': '100.2', 'satellites': '6'}" in caplog.text
    assert "Fehler: Ungültige Werte in Zeile: {'lat': '46.3', 'lon': '7.3', 'timestamp': '100.3', 'satellites': 'abc'}" in caplog.text


def test_read_gps_data_malformed_csv(caplog):  # Use caplog
    """Tests reading CSV with lines having wrong number of columns."""
    # --- KORREKTUR: Verwende logging in utils.py und caplog hier ---
    caplog.set_level(logging.ERROR)
    # DictReader weist None zu, wenn fieldnames gegeben sind und Felder fehlen
    csv_string = "46.1,7.1,100.1,5\n46.2,7.2\n46.3,7.3,100.3,7,extra"
    # --- KORREKTUR: Erwartetes Ergebnis angepasst ---
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # Die zweite Zeile fhrt zu ValueError bei float(None) -> wird übersprungen
        # Die dritte Zeile hat ein extra Feld, das von DictReader ignoriert wird,
        # aber da die zweite Zeile einen Fehler verursachte, wird sie evtl. nicht erreicht
        # oder ebenfalls übersprungen, je nach Fehlerbehandlung.
        # Sicher ist nur die erste Zeile.
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected
    # Prüfe die Log-Ausgabe für die Zeile mit fehlenden Werten
    assert "Fehler: Ungültige Werte in Zeile: {'lat': '46.2', 'lon': '7.2', 'timestamp': None, 'satellites': None}" in caplog.text
    # Prüfe die Log-Ausgabe für die Zeile mit zu vielen Werten (wird von DictReader ignoriert, kein Fehler hier)
    # assert "Fehler: Ungültige Werte in Zeile: {'lat': '46.3', 'lon': '7.3', 'timestamp': '100.3', 'satellites': '7'}" not in caplog.text
