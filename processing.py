# processing.py
import logging
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import numpy as np
import time  # Für Zeitstempel
from kalman_filter import GpsKalmanFilter

logger = logging.getLogger(__name__)


from utils import is_point_in_polygon 


def filter_by_geofence(gps_data, geofences):
    """
    Filtert GPS-Daten basierend auf Geofences.
    Logik:
    1. Wenn 'mow_area' definiert sind: Punkt muss in MINDESTENS EINER liegen.
    2. Wenn 'forbidden_area' definiert sind: Punkt darf in KEINER liegen.
    """
    mow_areas = [f['coordinates'] for f in geofences if f.get('type') == 'mow_area']
    forbidden_areas = [f['coordinates'] for f in geofences if f.get('type') == 'forbidden_area']
    
    if not mow_areas and not forbidden_areas:
        return gps_data
        
    filtered_data = []
    for point in gps_data:
        try:
            lat, lon = float(point['lat']), float(point['lon'])
            
            # Check allowed areas (if any exists, point must be inside)
            is_allowed = True
            if mow_areas:
                is_allowed = False
                for area in mow_areas:
                    if is_point_in_polygon(lat, lon, area):
                        is_allowed = True
                        break
            
            if not is_allowed:
                continue
                
            # Check forbidden areas (point MUST NOT be inside any)
            is_forbidden = False
            for area in forbidden_areas:
                if is_point_in_polygon(lat, lon, area):
                    is_forbidden = True
                    break
            
            if not is_forbidden:
                filtered_data.append(point)
        except (ValueError, KeyError, TypeError):
            continue
            
    return filtered_data


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
    """
    if not gps_data or len(gps_data) < 2:
        return gps_data

    filtered_data = [gps_data[0]]  # Erster Punkt wird immer behalten
    for i in range(1, len(gps_data)):
        prev_point = filtered_data[-1]
        curr_point = gps_data[i]

        try:
            dist = haversine(
                float(prev_point['lon']), float(prev_point['lat']),
                float(curr_point['lon']), float(curr_point['lat'])
            )
            dt = abs(float(curr_point['timestamp']) - float(prev_point['timestamp']))

            if dt > 0:
                speed = dist / dt
                if speed <= max_speed_mps:
                    filtered_data.append(curr_point)
            else:
                filtered_data.append(curr_point)
        except (ValueError, KeyError, TypeError):
            filtered_data.append(curr_point)

    return filtered_data


def filter_by_hdop(gps_data, max_hdop=2.0):
    """Filtert Punkte mit hohem HDOP-Wert."""
    filtered = []
    for p in gps_data:
        try:
            val = p.get('hdop')
            if val is None:
                val = 99.0
            if float(val) <= max_hdop:
                filtered.append(p)
        except (ValueError, TypeError):
            continue
    return filtered


def apply_kalman_filter(gps_data, process_noise=0.05, measurement_noise=5.0):
    """Wendet einen Kalman-Filter auf die GPS-Daten an."""
    if not gps_data:
        return []

    kf = GpsKalmanFilter(process_noise=process_noise, measurement_noise=measurement_noise)
    # Initialisierung mit dem ersten Punkt
    kf.state = np.array([float(gps_data[0]['lat']), float(gps_data[0]['lon']), 0, 0])
    kf.last_time = float(gps_data[0]['timestamp'])

    filtered_data = []
    for point in gps_data:
        lat, lon = kf.update(float(point['lat']), float(point['lon']), float(point['timestamp']))
        new_point = point.copy()
        new_point['lat'], new_point['lon'] = lat, lon
        filtered_data.append(new_point)

    return filtered_data

def apply_moving_average(gps_data, window_size=5):
    """Wendet einen gleitenden Durchschnitt zur Glättung an."""
    if not gps_data or len(gps_data) < 2:
        return gps_data
        
    filtered_data = []
    for i in range(len(gps_data)):
        start = max(0, i - window_size + 1)
        window = gps_data[start : i + 1]
        
        try:
            avg_lat = sum(float(p['lat']) for p in window) / len(window)
            avg_lon = sum(float(p['lon']) for p in window) / len(window)
            
            new_point = gps_data[i].copy()
            new_point['lat'], new_point['lon'] = avg_lat, avg_lon
            filtered_data.append(new_point)
        except (ValueError, KeyError, TypeError):
            filtered_data.append(gps_data[i])
            
    return filtered_data

def remove_drift_at_standstill(gps_data, min_dist_move=0.4, window_size=5):
    """Unterdrückt Drift-Bewegungen, wenn der Mäher steht (kleine Distanzänderungen)."""
    if not gps_data or len(gps_data) < 2:
        return gps_data
        
    filtered_data = [gps_data[0]]
    last_fixed_point = gps_data[0]
    
    for i in range(1, len(gps_data)):
        curr = gps_data[i]
        dist = haversine(float(last_fixed_point['lon']), float(last_fixed_point['lat']),
                         float(curr['lon']), float(curr['lat']))
        
        if dist > min_dist_move:
            filtered_data.append(curr)
            last_fixed_point = curr
        else:
            # Punkt wird 'eingefroren' auf den letzten stabilen Punkt, um Zappeln zu verhindern
            frozen = curr.copy()
            frozen['lat'] = last_fixed_point['lat']
            frozen['lon'] = last_fixed_point['lon']
            filtered_data.append(frozen)
            
    return filtered_data

def process_gps_data(gps_data, config, geofences=None):
    """Zentrale Verarbeitungs-Pipeline für GPS-Daten."""
    if not gps_data:
        return []

    # 1. Grober HDOP Filter
    data = filter_by_hdop(gps_data, config.get('hdop_threshold', 2.5))
    
    # 2. Geofencing Filter (NEU)
    if geofences:
        data = filter_by_geofence(data, geofences)

    # 3. Drift-Sperre bei Stillstand
    data = remove_drift_at_standstill(data)

    # 4. Geschwindigkeits-Plausibilität
    data = remove_outliers_by_speed(data, config.get('max_speed_mps', 1.5))

    # 5. Kalman-Filter zur Glättung
    data = apply_kalman_filter(
        data,
        process_noise=config.get('kalman_process_noise', 0.05),
        measurement_noise=config.get('kalman_measurement_noise', 5.0)
    )

    return data
