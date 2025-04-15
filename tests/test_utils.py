# tests/test_utils.py
import pytest
import logging  # Importiere logging für caplog

# Importiere die zu testende Funktion
try:
    from utils import read_gps_data_from_csv_string
except ImportError:
    import sys
    import os

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils import read_gps_data_from_csv_string


# --- Tests für read_gps_data_from_csv_string (aus utils.py) ---

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
    """Tests reading CSV data containing the end marker."""
    csv_string = "46.1,7.1,100.1,5\n-1,-1,-1,-1\n46.3,7.3,100.3,7"
    # --- KORREKTUR: Erwartetes Ergebnis angepasst ---
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # Die Verarbeitung stoppt beim Marker "-1"
    ]
    # --- ENDE KORREKTUR ---
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


def test_read_gps_data_empty_string():
    """Tests reading an empty CSV string."""
    csv_string = ""
    expected = []
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected


# --- KORREKTUR: Verwende caplog statt capsys ---
def test_read_gps_data_invalid_values(caplog):  # caplog statt capsys
    """Tests reading CSV with invalid numeric values."""
    caplog.set_level(logging.ERROR)  # Level für caplog setzen
    csv_string = "46.1,7.1,100.1,5\n46.invalid,7.2,100.2,6\n46.3,7.3,100.3,abc"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # The lines with invalid values should be skipped and logged
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected
    # captured = capsys.readouterr() # Nicht mehr nötig
    # assert "Fehler: Ungültige Werte in Zeile" in captured.out # Alt
    assert "Fehler: Ungültige Werte in Zeile: {'lat': '46.invalid', 'lon': '7.2', 'timestamp': '100.2', 'satellites': '6'}" in caplog.text
    assert "Fehler: Ungültige Werte in Zeile: {'lat': '46.3', 'lon': '7.3', 'timestamp': '100.3', 'satellites': 'abc'}" in caplog.text


# --- ENDE KORREKTUR ---

# --- KORREKTUR: Verwende caplog statt capsys ---
def test_read_gps_data_malformed_csv(caplog):  # caplog statt capsys
    """Tests reading CSV with lines having wrong number of columns."""
    caplog.set_level(logging.ERROR)  # Level für caplog setzen
    csv_string = "46.1,7.1,100.1,5\n46.2,7.2\n46.3,7.3,100.3,7,extra"
    expected = [
        {"lat": 46.1, "lon": 7.1, "timestamp": 100.1, "satellites": 5.0},
        # Die zweite Zeile führt zu Fehler -> wird übersprungen
        {"lat": 46.3, "lon": 7.3, "timestamp": 100.3, "satellites": 7.0},  # Dritte Zeile ist ok
    ]
    result = read_gps_data_from_csv_string(csv_string)
    assert result == expected
    # captured = capsys.readouterr() # Nicht mehr nötig
    # Expect an error log for the line with missing fields causing float(None)
    # assert "Fehler: Ungültige Werte in Zeile" in captured.out # Alt
    assert "Fehler: Fehlende Werte in Zeile: {'lat': '46.2', 'lon': '7.2', 'timestamp': None, 'satellites': None}" in caplog.text
# --- ENDE KORREKTUR ---
