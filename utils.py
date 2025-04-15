# utils.py
import csv
import logging  # Logging importieren
import io  # Für StringIO

# Logging konfigurieren (kann auch zentral erfolgen, hier zur Sicherheit)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
