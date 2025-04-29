# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# MQTT (unverändert)
MQTT_CONFIG = {
    "host": os.getenv("MQTT_HOST"),
    "port": int(os.getenv("MQTT_PORT") or 1883),
    "user": os.getenv("MQTT_USER"),
    "password": os.getenv("MQTT_PASSWORD"),
    "host_lokal": os.getenv("MQTT_HOST_LOKAL"),
    "port_lokal": int(os.getenv("MQTT_PORT_LOKAL") or 1883),
    "user_local": os.getenv("MQTT_USER_LOCAL"),
    "password_local": os.getenv("MQTT_PASSWORD_LOCAL"),
    "topic_gps": os.getenv("MQTT_TOPIC_GPS"),
    "topic_status": os.getenv("MQTT_TOPIC_STATUS"),
    "topic_control": os.getenv("MQTT_TOPIC_CONTROL"),
}

# GPS (unverändert)
GEO_CONFIG = {
    "fake_gps_range": ((46.811819, 46.811919), (7.132838, 7.132938)),
    "lat_bounds": (46.810819, 46.812919),
    "lon_bounds": (7.131838, 7.133938),
    "map_center": (46.811819, 7.132838),
    "zoom_start": 15,
    "max_zoom": 22,
    "crop_coordinates": ((46.8115, 7.1325), (46.8120, 7.1330)),
    "crop_enabled": True,
    "crop_center_percentage": 90,
    "save_interval": 5,
}

# Heatmap & Path Maps
HEATMAP_CONFIG = {
    "heatmap_aktuell": {
        "output": "heatmaps/heatmap_aktuell.html",
        "png_output": "heatmaps/heatmap_aktuell.png",
        "generate_png": False,
        "radius": 5,
        "blur": 10,
        "path_weight": 2.0,
        "path_opacity": 1.0,
        "show_start_end_markers": True,
        "path_colors": ["#3388ff"],
        "use_heatmap_with_time": True,
        "use_satellite_weight": False,  # Wird für Heatmap nicht verwendet
        "visualize_quality_path": False,  # Ist keine Qualitäts-Pfadkarte
    },
    "heatmap_10_maehvorgang": {
        "output": "heatmaps/heatmap_10.html",
        "png_output": "heatmaps/heatmap_10.png",
        "generate_png": False,
        "radius": 5,
        "blur": 10,
        "path_weight": 1.0,
        "path_opacity": 0.8,
        "show_start_end_markers": True,
        "use_heatmap_with_time": False,
        "use_satellite_weight": False,
        "visualize_quality_path": False,
    },
    "heatmap_kumuliert": {
        "output": "heatmaps/heatmap_kumuliert.html",
        "png_output": "heatmaps/heatmap_kumuliert.png",
        "generate_png": False,
        "radius": 5,
        "blur": 10,
        "path_weight": 1.0,  # Irrelevant, da kein Pfad gezeichnet wird
        "path_opacity": 0.7,  # Irrelevant
        "show_start_end_markers": False,
        "use_satellite_weight": False,
        "visualize_quality_path": False,
    },
    "problemzonen_heatmap": {
        "output": "heatmaps/problemzonen.html",
        "png_output": "heatmaps/problemzonen.png",
        "generate_png": False,
        "radius": 5,
        "blur": 5,
        "use_satellite_weight": False,
        "visualize_quality_path": False,
    },
    # --- NEU: Kumulierte Qualitäts-Pfadkarte ---
    "quality_path_10": {
        "output": "heatmaps/quality.html",
        "png_output": "heatmaps/quality.png",
        "generate_png": False, # PNG für segmentierte Pfade ist komplex
        # Pfad-Styling
        "path_weight": 3.0,
        "path_opacity": 0.85,
        "show_start_end_markers": True, # Start/End Marker pro Session anzeigen
        # Qualitäts-Visualisierung
        "visualize_quality_path": True, # Aktiviert die Pfad-Färbung
        "quality_colormap_colors": ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'], # Rot-Gelb-Grün
        "quality_colormap_index": [4, 6, 8, 10], # Schwellenwerte
        "quality_legend_caption": "Anzahl Satelliten (GPS Qualität)",
        # Folgende werden nicht verwendet
        "use_heatmap_with_time": False,
        "use_satellite_weight": False,
        "radius": 0,
        "blur": 0,
    }
    # --- ENDE NEU ---
}

# Recorder (unverändert)
REC_CONFIG = {
    "serial_port": os.getenv("GPS_SERIAL_PORT"),
    "baudrate": int(os.getenv("GPS_BAUDRATE") or "9600"),
    "test_mode": os.getenv("TEST_MODE", "False").lower() == "true",
    "storage_interval": 1,
    "debug_logging": os.getenv("DEBUG_LOGGING", "False").lower() == "true"
}

# Problemzonen (unverändert)
PROBLEM_CONFIG = {
    "problem_json": "problemzonen.json",
    "max_problemzonen": 100,
    "problem_threshold_time": 30
}

# Assist now (unverändert)
ASSIST_NOW_CONFIG = {
    "assist_now_enabled": os.getenv("ASSIST_NOW_ENABLED", "False").lower() == "true",
    "assist_now_offline_url": "https://offline-live1.services.u-blox.com/GetOfflineData.ashx",
    "assist_now_token": os.getenv("ASSIST_NOW_TOKEN"),
    "days": 7
}

# Nachverarbeitung (unverändert)
POST_PROCESSING_CONFIG = {
    "method": "kalman",
    "moving_average_window": 5,
    "kalman_measurement_noise": 5.0,
    "kalman_process_noise": 0.05,
    "outlier_detection": {
        "enable": True,
        "max_speed_mps": 1.5
    }
}


# Validierung (unverändert)
def validate_config():
    required_mqtt = ["topic_gps", "topic_status", "topic_control"]
    required_rec = ["baudrate", "storage_interval"]
    required_problem = ["problem_json", "max_problemzonen", "problem_threshold_time"]
    required_assist = ["assist_now_offline_url", "assist_now_token"]

    missing = []

    is_local_mode = REC_CONFIG.get("test_mode", False)
    host_key = "host_lokal" if is_local_mode else "host"
    port_key = "port_lokal" if is_local_mode else "port"

    if not MQTT_CONFIG.get(host_key):
        missing.append(f"MQTT_CONFIG['{host_key}'] (oder entsprechende .env Variable)")
    if not MQTT_CONFIG.get(port_key):
        if port_key not in MQTT_CONFIG:
            print(f"INFO: MQTT Port '{port_key}' nicht explizit gesetzt, verwende Standard 1883.")
        elif MQTT_CONFIG.get(port_key) is None:
            missing.append(f"MQTT_CONFIG['{port_key}'] (oder entsprechende .env Variable)")

    for key in required_mqtt:
        if not MQTT_CONFIG.get(key):
            missing.append(f"MQTT_CONFIG['{key}'] (oder entsprechende .env Variable)")

    if not is_local_mode and not REC_CONFIG.get("serial_port"):
        missing.append("REC_CONFIG['serial_port'] (oder GPS_SERIAL_PORT in .env) - Nötig im Realmodus")
    for key in required_rec:
        if REC_CONFIG.get(key) is None:
            missing.append(f"REC_CONFIG['{key}'] (oder entsprechende .env Variable)")

    for key in required_problem:
        if PROBLEM_CONFIG.get(key) is None:
            missing.append(f"PROBLEM_CONFIG['{key}']")

    if ASSIST_NOW_CONFIG.get("assist_now_enabled"):
        for key in required_assist:
            if not ASSIST_NOW_CONFIG.get(key):
                missing.append(f"ASSIST_NOW_CONFIG['{key}'] (oder entsprechende .env Variable)")
        valid_days = [1, 2, 3, 5, 7, 10, 14]
        if ASSIST_NOW_CONFIG.get("days") not in valid_days:
            print(
                f"WARNUNG: ASSIST_NOW_CONFIG['days'] hat ungültigen Wert ({ASSIST_NOW_CONFIG.get('days')}). Erlaubt: {valid_days}. Verwende Standard 7.")
            ASSIST_NOW_CONFIG["days"] = 7

    if missing:
        print("\nWARNUNG: Folgende kritische Konfigurationswerte fehlen oder sind nicht gesetzt:")
        print("Bitte prüfe deine .env Datei oder die Standardwerte in config.py.")
        for item in missing:
            print(f" - {item}")
        print("-" * 30)
    else:
        print("Konfigurationsvalidierung erfolgreich.")


validate_config()
