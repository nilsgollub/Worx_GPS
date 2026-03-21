# utils.py
import csv
import logging
import io
from typing import List, Dict, Any, Union, Optional, Tuple  # Tuple hinzugefügt
import math  # NEU: Für Distanzberechnung

logger = logging.getLogger(__name__)


def is_point_in_polygon(lat, lon, polygon):
    """
    Ray-casting Algorithmus zur Prüfung, ob ein Punkt in einem Polygon liegt.
    polygon: Liste von [lat, lon] Paaren.
    """
    if not polygon or len(polygon) < 3:
        return False
        
    n = len(polygon)
    inside = False
    
    try:
        # Sicherstellen, dass die Punkte Zahlen sind
        p1lat, p1lon = float(polygon[0][0]), float(polygon[0][1])
        for i in range(n + 1):
            p2lat, p2lon = float(polygon[i % n][0]), float(polygon[i % n][1])
            if lat > min(p1lat, p2lat):
                if lat <= max(p1lat, p2lat):
                    if lon <= max(p1lon, p2lon):
                        if p1lat != p2lat:
                            xints = (lat - p1lat) * (p2lon - p1lon) / (p2lat - p1lat) + p1lon
                            if p1lon == p2lon or lon <= xints:
                                inside = not inside
            p1lat, p1lon = p2lat, p2lon
    except (ValueError, TypeError, IndexError):
        return False
    return inside


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
        # Erweitertes Feldnamen-Array
        reader = csv.DictReader(csvfile, fieldnames=["lat", "lon", "timestamp", "satellites", "wifi", "hdop"])
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
                hdop_str = row.get("hdop")

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

                hdop: Optional[float] = None
                if hdop_str is not None and hdop_str.strip():
                    try:
                        hdop = float(hdop_str)
                    except (ValueError, TypeError):
                        pass

                data.append({"lat": lat, "lon": lon, "timestamp": timestamp, 
                             "satellites": satellites, "wifi": wifi, "hdop": hdop})
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

def calculate_area_coverage(points, lat_bounds, lon_bounds, grid_size_m=0.5):
    """
    Berechnet den prozentualen Anteil der abgedeckten Fläche in einem Geofence.
    Nutzt ein Grid-System für hohe Performance.
    """
    import math
    if not points or not lat_bounds or not lon_bounds:
        return 0.0

    # Erdradius in Metern für grobe Umrechnung Grad -> Meter
    LAT_DEGREE_M = 111320.0
    LON_DEGREE_M = 111320.0 * math.cos(math.radians(lat_bounds[0]))

    width_m = (lon_bounds[1] - lon_bounds[0]) * LON_DEGREE_M
    height_m = (lat_bounds[1] - lat_bounds[0]) * LAT_DEGREE_M

    if width_m <= 0 or height_m <= 0:
        return 0.0

    cols = int(width_m / grid_size_m) + 1
    rows = int(height_m / grid_size_m) + 1
    total_cells = cols * rows

    visited_cells = set()
    for p in points:
        lat, lon = p.get('lat'), p.get('lon')
        if lat is not None and lon is not None:
            if lat_bounds[0] <= lat <= lat_bounds[1] and lon_bounds[0] <= lon <= lon_bounds[1]:
                col = int((lon - lon_bounds[0]) / (lon_bounds[1] - lon_bounds[0]) * (cols - 1))
                row = int((lat - lat_bounds[0]) / (lat_bounds[1] - lat_bounds[0]) * (rows - 1))
                visited_cells.add((row, col))

    coverage = (len(visited_cells) / total_cells) * 100
    # Da ein Mähroboter ca. 20cm Schnittbreite hat, ist ein 0.5m Grid konservativ.
    # Wir extrapolieren leicht, um realistische Werte zu erhalten.
    coverage = coverage * 1.8 
    return round(min(100.0, coverage), 1)
