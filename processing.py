# processing.py
import logging
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import numpy as np
import time  # Für Zeitstempel
from kalman_filter import GpsKalmanFilter

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


def apply_kalman_filter(gps_data, measurement_noise=5.0, process_noise=0.1):
    """
    Wendet den neuen GpsKalmanFilter an, der HDOP berücksichtigt.
    Integriert interne Umrechnung von Metern in Grad-Varianz.
    """
    if not gps_data:
        return []

    # Umrechnung: 1 Grad ca. 111.320 Meter
    # R/Q sind Varianzen (Standardabweichung zum Quadrat)
    r_deg2 = (measurement_noise / 111320.0) ** 2
    q_deg2 = (process_noise / 111320.0) ** 2

    kf = GpsKalmanFilter(process_noise=q_deg2, measurement_noise=r_deg2)
    filtered_data = []

    for i, point in enumerate(gps_data):
        try:
            lat = float(point['lat'])
            lon = float(point['lon'])
            ts = float(point.get('timestamp', time.time()))
            hdop = point.get('hdop')
            if hdop is not None:
                try:
                    hdop = float(hdop)
                except (ValueError, TypeError):
                    hdop = None

            f_lat, f_lon = kf.update(lat, lon, ts, hdop=hdop)

            new_point = point.copy()
            new_point['lat'] = f_lat
            new_point['lon'] = f_lon
            filtered_data.append(new_point)

        except Exception as e:
            logger.warning(f"Kalman-Fehler in Punkt {i}: {e}")
            filtered_data.append(point)

    return filtered_data


def remove_drift_at_standstill(gps_data, min_dist_m=0.25):
    """
    Verhindert das GPS-Driften im Stillstand. Wenn die Distanz zum letzten
    Punkt zu gering ist, wird die Position 'festgehalten'.
    """
    if not gps_data or len(gps_data) < 2:
        return gps_data

    # Wir behalten den ersten Punkt immer
    filtered_data = [gps_data[0]]
    
    for i in range(1, len(gps_data)):
        prev = filtered_data[-1]
        curr = gps_data[i]
        
        # Distanzberechnung
        dist = haversine(float(prev['lat']), float(prev['lon']), 
                         float(curr['lat']), float(curr['lon']))
        
        # Wenn Bewegung > Schwellwert ist (z.B. 25cm), Punkt akzeptieren
        if dist >= min_dist_m:
            filtered_data.append(curr)
        else:
            # Im Stillstand: Wir überspringen den Punkt, um Zick-Zack Linien zu vermeiden.
            pass

    logger.debug(f"Drift-Filter: {len(gps_data) - len(filtered_data)} Punkte im Stillstand gruppiert.")
    return filtered_data
