# utils.py
import csv
import logging
import io
from typing import List, Dict, Any, Union, Optional, Tuple  # Tuple hinzugefügt
import math  # NEU: Für Distanzberechnung

logger = logging.getLogger(__name__)


# ... (read_gps_data_from_csv_string und flatten_data bleiben unverändert) ...
def read_gps_data_from_csv_string(csv_string: Optional[str]) -> List[Dict[str, Any]]:
    """
    Liest GPS-Daten aus einem CSV-String und gibt sie als Liste von Dictionaries zurück.
    Args:
        csv_string: Der CSV-String mit den GPS-Daten. Kann None sein.
    Returns:
        Eine Liste von Dictionaries, wobei jedes Dictionary einen GPS-Punkt repräsentiert.
        Format: [{'lat': float, 'lon': float, 'timestamp': float, 'satellites': Optional[int], 'wifi': Optional[int]}, ...]
        Gibt eine leere Liste zurück, wenn beim Lesen ein Fehler auftritt oder der String leer/None ist.
    """
    data: List[Dict[str, Any]] = []
    if not csv_string:
        logging.info("read_gps_data_from_csv_string: Leerer oder None Eingabe-String erhalten.")
        return data

    csvfile = io.StringIO(csv_string)
    try:
        reader = csv.DictReader(csvfile, fieldnames=["lat", "lon", "timestamp", "satellites", "wifi"])
        for i, row in enumerate(reader):
            if row.get("lat") == "-1":
                logging.debug("End-Marker (-1) in CSV-Daten gefunden, Verarbeitung beendet.")
                break
            try:
                lat_str = row.get("lat")
                lon_str = row.get("lon")
                ts_str = row.get("timestamp")
                sat_str = row.get("satellites")
                wifi_str = row.get("wifi")

                if lat_str is None or lon_str is None or ts_str is None:
                    logging.warning(
                        f"Zeile {i + 1}: Fehlende notwendige Werte (lat/lon/timestamp): {row}. Überspringe.")
                    continue

                lat = float(lat_str)
                lon = float(lon_str)
                timestamp = float(ts_str)

                satellites: Optional[int] = None
                if sat_str is not None and sat_str.strip():
                    try:
                        satellites = int(float(sat_str))
                    except (ValueError, TypeError):
                        logging.warning(
                            f"Zeile {i + 1}: Ungültiger Satellitenwert '{sat_str}'. Wird als None behandelt.")

                wifi: Optional[int] = None
                if wifi_str is not None and wifi_str.strip():
                    try:
                        wifi = int(float(wifi_str))
                    except (ValueError, TypeError):
                        pass

                data.append({"lat": lat, "lon": lon, "timestamp": timestamp, "satellites": satellites, "wifi": wifi})
            except (ValueError, TypeError) as e:
                logging.warning(f"Zeile {i + 1}: Fehler bei Wertkonvertierung: {e} - Zeile: {row}. Überspringe.")
                continue
    except csv.Error as e:
        logging.error(f"Fehler beim Lesen der CSV-Daten (csv.Error): {e}")
        return []
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Lesen der CSV-Daten: {e}", exc_info=True)
        return []
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
    if isinstance(data, list) and data and isinstance(data[0], list):
        for session in data:
            if isinstance(session, list):
                if all(isinstance(point, dict) for point in session):
                    flat_list.extend(session)
                else:
                    logging.warning(
                        f"Session in Multi-Session-Daten enthält ungültige Elemente: {session}. Überspringe.")
            else:
                logging.warning(f"Unerwartetes Element in Multi-Session-Daten gefunden: {type(session)}. Überspringe.")
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        if all(isinstance(point, dict) for point in data):
            flat_list = data
        else:
            logging.warning(f"Single-Session-Daten enthalten ungültige Elemente. Filtere Dictionaries.")
            flat_list = [point for point in data if isinstance(point, dict)]
    elif isinstance(data, list) and not data:
        pass
    else:
        logger.error(
            f"Unbekannte oder inkonsistente Datenstruktur in flatten_data: Typ des ersten Elements ist {type(data[0]) if data else 'N/A'}. Gebe leere Liste zurück.")
    return flat_list


# --- NEUE FUNKTION: calculate_distance ---
def calculate_distance(point1: Dict[str, Any], point2: Dict[str, Any]) -> float:
    """
    Berechnet die Haversine-Distanz zwischen zwei GPS-Punkten in Metern.

    Args:
        point1: Dictionary des ersten Punktes mit 'lat' und 'lon'.
        point2: Dictionary des zweiten Punktes mit 'lat' und 'lon'.

    Returns:
        Die Distanz in Metern oder 0.0 bei ungültigen Eingaben.
    """
    try:
        lat1, lon1 = math.radians(float(point1['lat'])), math.radians(float(point1['lon']))
        lat2, lon2 = math.radians(float(point2['lat'])), math.radians(float(point2['lon']))
    except (KeyError, ValueError, TypeError):
        logger.warning(f"Ungültige Koordinaten für Distanzberechnung: {point1}, {point2}")
        return 0.0

    # Erdradius in Metern
    R = 6371000

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


# --- ENDE calculate_distance ---

# --- NEUE FUNKTION: format_duration ---
def format_duration(seconds: float) -> str:
    """
    Formatiert eine Dauer in Sekunden in einen String (HH:MM:SS oder MM:SS).

    Args:
        seconds: Die Dauer in Sekunden.

    Returns:
        Ein formatierter String.
    """
    if seconds < 0:
        return "N/A"
    try:
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "N/A"
# --- ENDE format_duration ---
