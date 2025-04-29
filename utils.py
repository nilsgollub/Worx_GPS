# utils.py
import csv
import logging
import io
from typing import List, Dict, Any, Union, Optional # Optional und Type Hinting hinzugefügt

logger = logging.getLogger(__name__) # Logger am Anfang definieren

# Logging konfigurieren (sollte idealerweise zentral in der Hauptdatei erfolgen)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')


def read_gps_data_from_csv_string(csv_string):
    """
    Liest GPS-Daten aus einem CSV-String und gibt sie als Liste von Dictionaries zurück.

    Args:
        csv_string: Der CSV-String mit den GPS-Daten.

    Returns:
        Eine Liste von Dictionaries, wobei jedes Dictionary einen GPS-Punkt repräsentiert.
        Format: [{"lat": float, "lon": float, "timestamp": float, "satellites": float}, ...]
        Gibt eine leere Liste zurück, wenn beim Lesen ein Fehler auftritt oder der String leer ist.
    """
    data = []
    if not csv_string:
        logging.warning("read_gps_data_from_csv_string: Leerer Eingabe-String erhalten.")
        return data  # Leere Liste bei leerem String

    # Verwende StringIO, um den String wie eine Datei zu behandeln
    csvfile = io.StringIO(csv_string)

    try:
        # Lese den CSV-String mit DictReader
        # Wichtig: fieldnames müssen mit den erwarteten Spalten übereinstimmen
        #          (oder die erste Zeile des Strings enthält die Header)
        # Hier gehen wir davon aus, dass keine Header-Zeile vorhanden ist.
        reader = csv.DictReader(csvfile, fieldnames=["lat", "lon", "timestamp", "satellites"])

        for row in reader:
            # Überspringe den End-Marker, falls vorhanden
            if row.get("lat") == "-1":
                logging.debug("End-Marker (-1) in CSV-Daten gefunden, Verarbeitung beendet.")
                break  # Beende die Schleife beim End-Marker

            try:
                # Versuche, alle Werte in float umzuwandeln.
                # Verwende .get() mit Default None, um fehlende Keys abzufangen.
                lat_str = row.get("lat")
                lon_str = row.get("lon")
                ts_str = row.get("timestamp")
                sat_str = row.get("satellites")

                # Prüfe, ob alle Werte vorhanden sind, bevor konvertiert wird
                if lat_str is None or lon_str is None or ts_str is None or sat_str is None:
                    # --- KORREKTUR: Verwende logging statt print ---
                    # print(f"Fehler: Fehlende Werte in Zeile: {row}") # ALT
                    logging.error(f"Fehler: Fehlende Werte in Zeile: {row}")  # NEU
                    continue  # Überspringe diese Zeile

                lat = float(lat_str)
                lon = float(lon_str)
                timestamp = float(ts_str)
                # Satelliten können auch Ganzzahlen sein, float ist aber flexibler
                satellites = float(sat_str)

                data.append({"lat": lat, "lon": lon, "timestamp": timestamp, "satellites": satellites})

            except (ValueError, TypeError) as e:  # Fange spezifischere Fehler ab
                # --- KORREKTUR: Verwende logging statt print ---
                # print(f"Fehler: Ungültige Werte in Zeile: {row} - {e}") # ALT
                logging.error(f"Fehler: Ungültige Werte in Zeile: {row} - {e}")  # NEU
                continue  # Überspringe diese Zeile bei Konvertierungsfehler

    except csv.Error as e:  # Fange Fehler vom csv-Modul selbst ab
        # --- KORREKTUR: Verwende logging statt print ---
        # print(f"Fehler beim Lesen der CSV-Daten (csv.Error): {e}") # ALT
        logging.error(f"Fehler beim Lesen der CSV-Daten (csv.Error): {e}")  # NEU
        return []  # Leere Liste bei grundlegendem CSV-Fehler
    except Exception as e:
        # --- KORREKTUR: Verwende logging statt print ---
        # print(f"Unerwarteter Fehler beim Lesen der CSV-Daten: {e}") # ALT
        logging.error(f"Unerwarteter Fehler beim Lesen der CSV-Daten: {e}", exc_info=True)  # NEU
        return []  # Leere Liste bei unerwartetem Fehler

    return data

def flatten_data(data: Union[List[Dict[str, Any]], List[List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """
    Wandelt eine Liste von Sessions (Liste von Listen von Punkten)
    oder eine einzelne Session (Liste von Punkten) in eine flache Liste von Punkten um.

    Args:
        data: Die Eingabedaten, entweder eine Liste von Punkten oder eine Liste von Listen von Punkten.

    Returns:
        Eine einzelne, flache Liste aller Punkte.
    """
    flat_list: List[Dict[str, Any]] = []
    if not data:
        return flat_list

    # Prüfen, ob das erste Element eine Liste ist (Indikator für Multi-Session)
    # Zusätzliche Prüfung: Sicherstellen, dass 'data' selbst eine Liste ist
    if isinstance(data, list) and data and isinstance(data[0], list):
        # Es ist eine Liste von Listen (Multi-Session)
        for session in data:
            if isinstance(session, list):
                # Stelle sicher, dass die Session Dictionaries enthält (optional, aber robuster)
                if all(isinstance(point, dict) for point in session):
                    flat_list.extend(session)
                else:
                    logging.warning(f"Session in Multi-Session-Daten enthält ungültige Elemente: {session}. Überspringe.")
            else:
                # Dies sollte nicht passieren, wenn die Struktur konsistent ist
                logging.warning(f"Unerwartetes Element in Multi-Session-Daten gefunden: {type(session)}. Überspringe.")
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        # Es ist bereits eine flache Liste (Single-Session)
        # Stelle sicher, dass alle Elemente Dictionaries sind (optional)
        if all(isinstance(point, dict) for point in data):
            flat_list = data
        else:
             logging.warning(f"Single-Session-Daten enthalten ungültige Elemente. Filtere Dictionaries.")
             flat_list = [point for point in data if isinstance(point, dict)]
    elif isinstance(data, list) and not data: # Leere Liste ist okay
        pass # flat_list ist bereits leer
    else:
        logger.error(f"Unbekannte oder inkonsistente Datenstruktur in flatten_data: Typ des ersten Elements ist {type(data[0]) if data else 'N/A'}. Gebe leere Liste zurück.")

    return flat_list
