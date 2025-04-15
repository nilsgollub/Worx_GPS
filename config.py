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
    "zoom_start": 15,
    "crop_coordinates": ((46.8115, 7.1325), (46.8120, 7.1330)),  # (left-top, right-bottom)
    "crop_enabled": True,
    "crop_center_percentage": 20, # Beispiel: Behalte 75% der kleineren Dimension als Quadrat
    # "crop_pixel_left": 150,  # Pixel vom linken Rand
    # "crop_pixel_top": 100,  # Pixel vom oberen Rand
    # "crop_pixel_right": 150,  # Pixel vom rechten Rand (Abstand, nicht Koordinate!)
    # "crop_pixel_bottom": 200,  # Pixel vom unteren Rand (Abstand, nicht Koordinate!)
    # --- ENDE NEU ---
    "save_interval": 5,  # Wird aktuell nicht direkt hier verwendet
}

# Heatmap
HEATMAP_CONFIG = {
    "tile": 'OpenStreetMap',
    "heatmap_aktuell": {
        "output": "heatmaps/heatmap_aktuell.html",
        "png_output": "heatmaps/heatmap_aktuell.png",
        "radius": 3,
        "blur": 3
    },
    "heatmap_10_maehvorgang": {
        "output": "heatmaps/heatmap_10.html",
        "png_output": "heatmaps/heatmap_10.png",
        "radius": 3,
        "blur": 3
    },
    "heatmap_kumuliert": {
        "output": "heatmaps/heatmap_kumuliert.html",
        "png_output": "heatmaps/heatmap_kumuliert.png",
        "radius": 3,
        "blur": 3
    },
    "problemzonen_heatmap": {
        "output": "heatmaps/problemzonen.html",
        "png_output": "heatmaps/problemzonen.png",
        "radius": 5,
        "blur": 3
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
    "storage_interval": 2  # Speicherintervall in Sekunden
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
    "assist_now_token": os.getenv("ASSIST_NOW_TOKEN")
}


# --- Validierung (Optional, aber hilfreich) ---
def validate_config():
    required_mqtt = ["host", "port", "topic_gps", "topic_status", "topic_control"]
    required_rec = ["serial_port", "baudrate", "storage_interval"]
    required_problem = ["problem_json", "max_problemzonen", "problem_threshold_time"]
    required_assist = ["assist_now_offline_url", "assist_now_token"]

    missing = []
    for key in required_mqtt:
        if key not in MQTT_CONFIG or MQTT_CONFIG[key] is None:
            # Spezielle Prüfung für lokale vs. externe Config je nach test_mode
            if REC_CONFIG["test_mode"]:
                if f"{key}_lokal" not in MQTT_CONFIG or MQTT_CONFIG[f"{key}_lokal"] is None:
                    if key != "host" and key != "port":  # host/port haben keine _lokal Variante
                        missing.append(f"MQTT_CONFIG['{key}'] (oder '{key}_lokal' im Testmodus)")
            elif MQTT_CONFIG[key] is None:
                missing.append(f"MQTT_CONFIG['{key}']")

    for key in required_rec:
        if key not in REC_CONFIG or REC_CONFIG[key] is None:
            missing.append(f"REC_CONFIG['{key}']")
    for key in required_problem:
        if key not in PROBLEM_CONFIG or PROBLEM_CONFIG[key] is None:
            missing.append(f"PROBLEM_CONFIG['{key}']")
    if ASSIST_NOW_CONFIG["assist_now_enabled"]:
        for key in required_assist:
            if key not in ASSIST_NOW_CONFIG or ASSIST_NOW_CONFIG[key] is None:
                missing.append(f"ASSIST_NOW_CONFIG['{key}']")

    if missing:
        print("WARNUNG: Folgende Konfigurationswerte fehlen oder sind nicht gesetzt (prüfe .env):")
        for item in missing:
            print(f" - {item}")
        # Optional: Hier einen Fehler auslösen, wenn die Konfiguration kritisch ist
        # raise ValueError("Kritische Konfigurationswerte fehlen!")


# Führe Validierung beim Import aus
validate_config()
