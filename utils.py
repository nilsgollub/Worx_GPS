# utils.py
import csv


def read_gps_data_from_csv_string(csv_string):
    """
    Liest GPS-Daten aus einem CSV-String und gibt sie als Liste von Dictionaries zurück.

    Args:
        csv_string: Der CSV-String mit den GPS-Daten.

    Returns:
        Eine Liste von Dictionaries, wobei jedes Dictionary einen GPS-Punkt repräsentiert.
        Format: [{"lat": float, "lon": float, "timestamp": float, "satellites": float}, ...]
    """
    data = []
    try:
        reader = csv.DictReader(csv_string.splitlines(), fieldnames=["lat", "lon", "timestamp", "satellites"])
        for row in reader:
            if row["lat"] != "-1":  # ende Marker
                try:
                    # Versuche, alle Werte in float umzuwandeln
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                    timestamp = float(row["timestamp"])
                    satellites = float(row["satellites"])
                    data.append({"lat": lat, "lon": lon, "timestamp": timestamp, "satellites": satellites})
                except ValueError:
                    print(f"Fehler: Ungültige Werte in Zeile: {row}")
                    # Hier könntest du entscheiden, ob du die Zeile ignorieren, loggen oder andere Maßnahmen ergreifen möchtest
    except Exception as e:
        print(f"Fehler beim Lesen der CSV-Daten: {e}")
    return data
