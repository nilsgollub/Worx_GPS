# processing.py
import logging
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import numpy as np
from filterpy.kalman import KalmanFilter
import time  # Für Zeitstempel

logger = logging.getLogger(__name__)


def haversine(lon1, lat1, lon2, lat2):
    """Berechnet die Distanz zwischen zwei Punkten auf der Erde in Metern."""
    # Konvertiere Grad in Radianten
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine Formel
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius der Erde in Metern
    return c * r


def remove_outliers_by_speed(gps_data, max_speed_mps=1.5):
    """
    Entfernt Punkte, die eine unrealistische Geschwindigkeit im Vergleich
    zum vorherigen akzeptierten Punkt implizieren.

    Args:
        gps_data (list): Liste von GPS-Daten-Dictionaries.
                         Erwartet Keys: 'lat', 'lon', 'timestamp'.
        max_speed_mps (float): Maximale erlaubte Geschwindigkeit in m/s.

    Returns:
        list: Gefilterte Liste von GPS-Daten-Dictionaries.
    """
    if not gps_data or len(gps_data) < 2:
        return gps_data

    filtered_data = [gps_data[0]]  # Erster Punkt wird immer behalten
    removed_count = 0

    for i in range(1, len(gps_data)):
        # Vergleiche immer mit dem letzten *akzeptierten* Punkt
        prev_point = filtered_data[-1]
        curr_point = gps_data[i]

        try:
            # Extrahiere Daten sicher, konvertiere zu float
            lat1 = float(prev_point['lat'])
            lon1 = float(prev_point['lon'])
            # Verwende time.time() als Fallback, falls Timestamp fehlt
            ts1 = float(prev_point.get('timestamp', time.time()))

            lat2 = float(curr_point['lat'])
            lon2 = float(curr_point['lon'])
            ts2 = float(curr_point.get('timestamp', time.time()))

            distance = haversine(lon1, lat1, lon2, lat2)
            time_diff = ts2 - ts1

            # Vermeide Division durch Null oder unrealistisch kleine Zeitintervalle
            if time_diff <= 1e-6:
                speed = 0.0
            else:
                speed = distance / time_diff

            # Prüfe, ob Geschwindigkeit im plausiblen Bereich liegt
            if 0 <= speed <= max_speed_mps:
                filtered_data.append(curr_point)
            else:
                logger.debug(
                    f"Ausreißer entfernt (Punkt {i}): Geschwindigkeit {speed:.2f} m/s > {max_speed_mps:.2f} m/s. Dist: {distance:.2f}m, Zeit: {time_diff:.2f}s")
                removed_count += 1

        except (KeyError, ValueError, TypeError) as e:
            # Logge Fehler und behalte den Punkt im Zweifel
            logger.warning(f"Fehler bei Ausreißerprüfung für Punkt {i}: {e}. Punkt wird behalten. Daten: {curr_point}")
            filtered_data.append(curr_point)

    if removed_count > 0:
        logger.info(f"{removed_count} Ausreißer basierend auf Geschwindigkeit entfernt.")
    return filtered_data


def apply_moving_average(gps_data, window_size=5):
    """
    Wendet einen einfachen gleitenden Durchschnitt auf Lat/Lon an.

    Args:
        gps_data (list): Liste von GPS-Daten-Dictionaries.
                         Erwartet Keys: 'lat', 'lon'.
        window_size (int): Anzahl der Punkte für den Durchschnitt.

    Returns:
        list: Liste von GPS-Daten-Dictionaries mit geglätteten 'lat'/'lon'.
    """
    if not gps_data or window_size < 2:
        return gps_data

    smoothed_data = []
    # Verwende deques für effizientes Hinzufügen/Entfernen
    from collections import deque
    lat_buffer = deque(maxlen=window_size)
    lon_buffer = deque(maxlen=window_size)

    for i, point in enumerate(gps_data):
        try:
            lat = float(point['lat'])
            lon = float(point['lon'])

            lat_buffer.append(lat)
            lon_buffer.append(lon)

            # Berechne Durchschnitt der aktuellen Pufferinhalte
            avg_lat = sum(lat_buffer) / len(lat_buffer)
            avg_lon = sum(lon_buffer) / len(lon_buffer)

            # Erstelle einen neuen Punkt mit geglätteten Werten,
            # behalte andere Daten (wie timestamp) bei.
            new_point = point.copy()
            new_point['lat'] = avg_lat
            new_point['lon'] = avg_lon
            smoothed_data.append(new_point)

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Fehler bei Moving Average für Punkt {i}: {e}. Punkt wird übersprungen. Daten: {point}")
            # Optional: Originalpunkt hinzufügen? smoothed_data.append(point)

    return smoothed_data


def apply_kalman_filter(gps_data, measurement_noise=5.0, process_noise=0.05):
    """
    Wendet einen Kalman-Filter auf Lat/Lon an, um die Position zu schätzen.
    Verwendet ein Modell mit konstanter Geschwindigkeit.

    Args:
        gps_data (list): Liste von GPS-Daten-Dictionaries.
                         Erwartet Keys: 'lat', 'lon', 'timestamp'.
        measurement_noise (float): Standardabweichung des Messrauschens (GPS-Ungenauigkeit in Metern).
        process_noise (float): Standardabweichung des Prozessrauschens (Wie stark kann sich die Geschwindigkeit ändern?).

    Returns:
        list: Liste von GPS-Daten-Dictionaries mit gefilterten 'lat'/'lon'.
    """
    if not gps_data:
        return []

    # Zustand x = [latitude, longitude, lat_velocity, lon_velocity] (4 Dimensionen)
    # Messung z = [latitude, longitude] (2 Dimensionen)
    kf = KalmanFilter(dim_x=4, dim_z=2)

    # --- Initialisierung ---
    try:
        initial_lat = float(gps_data[0]['lat'])
        initial_lon = float(gps_data[0]['lon'])
        # Verwende time.time() als Fallback
        initial_ts = float(gps_data[0].get('timestamp', time.time()))
        kf.x = np.array(
            [initial_lat, initial_lon, 0., 0.])  # Startzustand: Position vom ersten Punkt, Geschwindigkeit 0
    except (KeyError, ValueError, TypeError, IndexError) as e:
        logger.error(
            f"Kann Kalman Filter nicht initialisieren, ungültiger erster GPS-Punkt: {e}. Daten: {gps_data[0] if gps_data else 'leer'}")
        return gps_data  # Gib Originaldaten zurück bei Fehler

    # Unsicherheit des Startzustands (P) - relativ hoch ansetzen
    kf.P = np.eye(4) * 50.

    # Messfunktion (H) - Wir messen nur die Position
    kf.H = np.array([[1., 0., 0., 0.],
                     [0., 1., 0., 0.]])

    # Messrauschen (R) - Kovarianzmatrix der Messung
    # Annahme: Rauschen in Lat/Lon ist unabhängig und hat Varianz measurement_noise^2
    # Die Einheit hier ist problematisch (Grad vs Meter). Für kleine Bereiche ist die Annahme
    # einer konstanten Varianz in Grad^2 *okay*, aber nicht ideal.
    # Besser wäre Umrechnung in lokales Koordinatensystem (UTM), Filterung dort, und Rückrechnung.
    # Hier vereinfacht:
    kf.R = np.eye(2) * (measurement_noise / 111000) ** 2  # Grobe Umrechnung Meter in Grad

    # Prozessrauschen (Q) - Kovarianzmatrix des Prozessrauschens
    # Modelliert die Unsicherheit in der Annahme konstanter Geschwindigkeit.
    # Verwendung von filterpy.common.Q_discrete_white_noise ist üblich.
    # Hier manuell für Verständnis, Annahme: Rauschen beeinflusst Beschleunigung.
    # dt wird später dynamisch gesetzt.

    # --- Filterung ---
    filtered_data = []
    last_ts = initial_ts

    for i, point in enumerate(gps_data):
        try:
            lat = float(point['lat'])
            lon = float(point['lon'])
            current_ts = float(point.get('timestamp', last_ts + 1.0))  # Fallback: 1 Sekunde

            # Berechne Zeitdifferenz dt
            dt = current_ts - last_ts
            if dt <= 0:  # Vermeide ungültige oder Null-Zeitschritte
                dt = 1.0  # Fallback auf 1 Sekunde
            last_ts = current_ts

            # --- Zustandsübergangsmatrix (F) aktualisieren ---
            # Position = alte Position + Geschwindigkeit * dt
            # Geschwindigkeit = alte Geschwindigkeit (Annahme: konstante Geschwindigkeit)
            kf.F = np.array([[1., 0., dt, 0.],
                             [0., 1., 0., dt],
                             [0., 0., 1., 0.],
                             [0., 0., 0., 1.]])

            # --- Prozessrauschen (Q) aktualisieren (optional, aber besser) ---
            # Annahme: Rauschen wirkt auf Beschleunigung -> beeinflusst Geschw. und Pos.
            # Einfaches Modell: Q proportional zu dt
            q_val = process_noise * dt
            kf.Q = np.diag([q_val, q_val, q_val, q_val])  # Vereinfacht

            # --- Vorhersage (Predict) ---
            kf.predict()

            # --- Messung (Update) ---
            z = np.array([lat, lon])  # Aktuelle Messung
            kf.update(z)

            # Speichere den gefilterten Zustand (Position)
            new_point = point.copy()
            new_point['lat'] = kf.x[0]
            new_point['lon'] = kf.x[1]
            # Optional: Geschwindigkeit speichern
            # new_point['vel_lat'] = kf.x[2]
            # new_point['vel_lon'] = kf.x[3]
            filtered_data.append(new_point)

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Fehler bei Kalman Filter für Punkt {i}: {e}. Punkt wird übersprungen. Daten: {point}")
            # Optional: Originalpunkt hinzufügen? filtered_data.append(point)

    return filtered_data
