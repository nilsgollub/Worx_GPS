# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# MQTT
MQTT_CONFIG = {
    "host": os.getenv("MQTT_HOST"),
    # --- Korrektur: Standardwert für Port hinzufügen ---
    "port": int(os.getenv("MQTT_PORT") or 1883),
    "user": os.getenv("MQTT_USER"),
    "password": os.getenv("MQTT_PASSWORD"),
    "host_lokal": os.getenv("MQTT_HOST_LOKAL"),
    # --- Korrektur: Standardwert für Port hinzufügen ---
    "port_lokal": int(os.getenv("MQTT_PORT_LOKAL") or 1883),
    "user_local": os.getenv("MQTT_USER_LOCAL"),
    "password_local": os.getenv("MQTT_PASSWORD_LOCAL"),
    "topic_gps": os.getenv("MQTT_TOPIC_GPS"),
    "topic_status": os.getenv("MQTT_TOPIC_STATUS"),
    "topic_control": os.getenv("MQTT_TOPIC_CONTROL"),
}

# GPS
GEO_CONFIG = {
    # "is_fake": True, # Veraltet, wird durch GpsHandler.mode gesteuert
    "fake_gps_range": ((46.811819, 46.811919), (7.132838, 7.132938)),  # (lat, lon)
    "lat_bounds": (46.810819, 46.812919),  # (min, max)
    "lon_bounds": (7.131838, 7.133938),  # (min, max)
    "map_center": (46.811819, 7.132838),
    "zoom_start": 15,  # Standard-Zoom für neue Karten
    "max_zoom": 22,  # Maximal erlaubter Zoom-Level
    "crop_coordinates": ((46.8115, 7.1325), (46.8120, 7.1330)),
    # (left-top, right-bottom) - Wird aktuell nicht verwendet
    "crop_enabled": True,  # PNG Cropping generell aktivieren/deaktivieren
    "crop_center_percentage": 90,  # Behalte X% der kleineren Dimension als Quadrat in der Mitte
    # Alternative: Pixel-Offsets (werden nur verwendet, wenn crop_center_percentage nicht gesetzt/gültig ist)
    # "crop_pixel_left": 150,
    # "crop_pixel_top": 100,
    # "crop_pixel_right": 150,
    # "crop_pixel_bottom": 200,
    "save_interval": 5,  # Wird aktuell nicht direkt hier verwendet
}

# Heatmap
HEATMAP_CONFIG = {
    # "tile": 'OpenStreetMap', # Veraltet, wird jetzt direkt im Code gesetzt (Google Sat + OSM)
    "heatmap_aktuell": {
        "output": "heatmaps/heatmap_aktuell.html",
        "png_output": "heatmaps/heatmap_aktuell.png",
        "radius": 5,
        "blur": 10,
        # --- NEU: Pfad-Styling & Marker ---
        "path_weight": 2.0,  # Dicke der Linie
        "path_opacity": 1.0,  # Transparenz der Linie (0.0 bis 1.0)
        "show_start_end_markers": True,  # Start-/Endpunkte anzeigen?
        "path_colors": ["#3388ff"],  # Farbe(n) für den Pfad (nur eine für Single-Session)
        "use_heatmap_with_time": True,
        # --- ENDE NEU ---
    },
    "heatmap_10_maehvorgang": {
        "output": "heatmaps/heatmap_10.html",
        "png_output": "heatmaps/heatmap_10.png",
        "radius": 5,
        "blur": 10,
        # --- NEU: Pfad-Styling & Marker ---
        "path_weight": 1.0,
        "path_opacity": 0.8,
        "show_start_end_markers": True,
        "use_heatmap_with_time": False,
        # "path_colors": [...] # Optional: Eigene Liste von Farben, sonst werden Defaults verwendet
        # --- ENDE NEU ---
    },
    "heatmap_kumuliert": {
        "output": "heatmaps/heatmap_kumuliert.html",
        "png_output": "heatmaps/heatmap_kumuliert.png",
        "radius": 5,
        "blur": 10,
        # --- NEU: Pfad-Styling & Marker ---
        "path_weight": 1.0,
        "path_opacity": 0.7,
        "show_start_end_markers": False,  # Bei Gesamtdaten oft nicht sinnvoll
        # "path_colors": [...] # Keine Pfade für Gesamtdaten erwartet, aber Option wäre da
        # --- ENDE NEU ---
    },
    "problemzonen_heatmap": {
        "output": "heatmaps/problemzonen.html",
        "png_output": "heatmaps/problemzonen.png",
        "radius": 5,
        "blur": 5
        # Pfad-Optionen hier nicht relevant, da es um Punkte geht
    },
}

# Recorder
REC_CONFIG = {
    "serial_port": os.getenv("GPS_SERIAL_PORT"),
    # --- Korrektur: Leere Strings abfangen ---
    "baudrate": int(os.getenv("GPS_BAUDRATE") or "9600"),
    # --- Korrektur: Logik für Boolean ---
    # "True" (case-insensitive) -> True, alles andere -> False
    "test_mode": os.getenv("TEST_MODE", "False").lower() == "true",
    "storage_interval": 1,  # Speicherintervall in Sekunden
    "debug_logging": False  # Setze hier True oder False

}

# Problemzonen
PROBLEM_CONFIG = {
    "problem_json": "problemzonen.json",
    "max_problemzonen": 100,
    # --- Korrektur: Key hinzugefügt (Beispielwert) ---
    "problem_threshold_time": 30  # Zeit in Sekunden, wie lange der Worx stehen darf
}

# Assist now
ASSIST_NOW_CONFIG = {
    # --- Korrektur: Logik für Boolean ---
    "assist_now_enabled": os.getenv("ASSIST_NOW_ENABLED", "False").lower() == "true",
    "assist_now_offline_url": "https://offline-live1.services.u-blox.com/GetOfflineData.ashx",
    "assist_now_token": os.getenv("ASSIST_NOW_TOKEN"),
    # --- NEU: Gültigkeitsdauer für Offline-Daten (u-blox 7) ---
    # Gültige Werte für u-blox 7: 1, 2, 3, 5, 7, 10, 14
    "days": 7
}

# --- NEU: Nachverarbeitung (Auswertung) ---
POST_PROCESSING_CONFIG = {
    # Methode: "none", "moving_average", "kalman"
    "method": "kalman",

    # Einstellungen für Gleitenden Durchschnitt
    "moving_average_window": 5,  # Anzahl der Punkte für den Durchschnitt

    # Einstellungen für Kalman-Filter (Experimentelle Werte!)
    "kalman_measurement_noise": 5.0,  # Unsicherheit der GPS-Messung (größer = mehr Glättung)
    "kalman_process_noise": 0.05,  # Unsicherheit der Bewegung (größer = schnellere Reaktion)

    # Einstellungen für Ausreißererkennung
    "outlier_detection": {
        "enable": True,  # Aktivieren/Deaktivieren
        "max_speed_mps": 1.5  # Maximale plausible Geschwindigkeit in m/s
    }
}


# --- Validierung (Optional, aber hilfreich) ---
def validate_config():
    required_mqtt = ["host", "port", "topic_gps", "topic_status", "topic_control"]
    required_rec = ["serial_port", "baudrate", "storage_interval"]
    required_problem = ["problem_json", "max_problemzonen", "problem_threshold_time"]
    required_assist = ["assist_now_offline_url", "assist_now_token"]

    missing = []
    for key in required_mqtt:
        # Angepasste Logik für lokale vs. externe MQTT-Konfiguration
        is_local_mode = REC_CONFIG.get("test_mode", False)  # Sicherstellen, dass test_mode existiert
        host_key = "host_lokal" if is_local_mode else "host"
        port_key = "port_lokal" if is_local_mode else "port"
        user_key = "user_local" if is_local_mode else "user"
        password_key = "password_local" if is_local_mode else "password"

        # Prüfe die relevanten Keys basierend auf dem Modus
        if key == "host" and (host_key not in MQTT_CONFIG or MQTT_CONFIG[host_key] is None):
            missing.append(f"MQTT_CONFIG['{host_key}']")
        elif key == "port" and (port_key not in MQTT_CONFIG or MQTT_CONFIG[port_key] is None):
            missing.append(f"MQTT_CONFIG['{port_key}']")
        # User/Passwort sind optional, daher nicht prüfen
        # elif key == "user" and (user_key not in MQTT_CONFIG or MQTT_CONFIG[user_key] is None):
        #      missing.append(f"MQTT_CONFIG['{user_key}']")
        # elif key == "password" and (password_key not in MQTT_CONFIG or MQTT_CONFIG[password_key] is None):
        #      missing.append(f"MQTT_CONFIG['{password_key}']")
        elif key not in ["host", "port", "user", "password"] and (key not in MQTT_CONFIG or MQTT_CONFIG[key] is None):
            missing.append(f"MQTT_CONFIG['{key}']")

    for key in required_rec:
        if key not in REC_CONFIG or REC_CONFIG[key] is None:
            missing.append(f"REC_CONFIG['{key}']")
    for key in required_problem:
        if key not in PROBLEM_CONFIG or PROBLEM_CONFIG[key] is None:
            missing.append(f"PROBLEM_CONFIG['{key}']")
    if ASSIST_NOW_CONFIG.get("assist_now_enabled", False):  # Sicherstellen, dass Key existiert
        for key in required_assist:
            if key not in ASSIST_NOW_CONFIG or ASSIST_NOW_CONFIG[key] is None:
                missing.append(f"ASSIST_NOW_CONFIG['{key}']")

    if missing:
        print(
            "WARNUNG: Folgende Konfigurationswerte fehlen oder sind nicht gesetzt (prüfe .env oder config.py Defaults):")
        for item in missing:
            print(f" - {item}")
        # Optional: Hier einen Fehler auslösen, wenn die Konfiguration kritisch ist
        # raise ValueError("Kritische Konfigurationswerte fehlen!")


# Führe Validierung beim Import aus
validate_config()
