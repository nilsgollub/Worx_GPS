# config.py
import os
from dotenv import load_dotenv

# Persistente Konfiguration: Im HA Add-on liegt /data/.env im persistenten Speicher.
# Wir laden diese ZUERST (falls vorhanden), dann die lokale .env als Fallback.
_persistent_env = os.path.join(os.getenv('DATA_DIR', '/data'), '.env')
if os.path.exists(_persistent_env):
    load_dotenv(_persistent_env, override=True)
    print(f"[Config] Persistente .env geladen: {_persistent_env}")

# Lokale .env (Entwicklungs-Fallback) — überschreibt NICHT, was aus /data/.env kam
load_dotenv(override=False)

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
    "topic_logs": os.getenv("MQTT_TOPIC_LOGS"),
    # NEU: Status Intervall hinzugefügt (aus vorheriger main_loop Logik)
    "status_interval": int(os.getenv("MQTT_STATUS_INTERVAL", 5))
}

# GPS (unverändert)
GEO_CONFIG = {
    "fake_gps_range": ((46.777540, 46.777709), (7.162430, 7.162690)),
    "lat_bounds": (46.777500, 46.777800),
    "lon_bounds": (7.162400, 7.162750),
    "map_center": (46.777625, 7.162560),
    "zoom_start": int(os.getenv("GEO_ZOOM_START", 20)),
    "max_zoom": int(os.getenv("GEO_MAX_ZOOM", 22)),
    "crop_coordinates": ((46.7774, 7.1623), (46.7779, 7.1629)),
    "crop_enabled": True,
    "crop_center_percentage": 90,
    "save_interval": 5,
}

# Heatmap & Path Maps
HEATMAP_CONFIG = {
    "heatmap_aktuell": {
        "output": "heatmaps/heatmap_aktuell.html",
        "png_output": "heatmaps/heatmap_aktuell.png",
        "generate_png": os.getenv("HEATMAP_GENERATE_PNG", "False").lower() == "true",
        "radius": int(os.getenv("HEATMAP_RADIUS", 5)),
        "blur": int(os.getenv("HEATMAP_BLUR", 10)),
        "path_weight": 2.0,
        "path_opacity": 1.0,
        "show_start_end_markers": True,
        "path_colors": ["#3388ff"],
        "use_heatmap_with_time": False,
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
        "generate_png": False,  # PNG für segmentierte Pfade ist komplex
        # Pfad-Styling
        "path_weight": 3.0,
        "path_opacity": 0.85,
        "show_start_end_markers": True,  # Start/End Marker pro Session anzeigen
        # Qualitäts-Visualisierung
        "visualize_quality_path": True,  # Aktiviert die Pfad-Färbung
        "quality_colormap_colors": ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'],  # Rot-Gelb-Grün
        "quality_colormap_index": [4, 6, 8, 10],  # Schwellenwerte
        "quality_legend_caption": "Anzahl Satelliten (GPS Qualität)",
        # Folgende werden nicht verwendet
        "use_heatmap_with_time": False,
        "use_satellite_weight": False,
        "radius": 0,
        "blur": 0,
    },
    # --- WiFi Signalstärke (Letzte 10 Sessions) ---
    "wifi_heatmap": {
        "output": "heatmaps/wifi.html",
        "png_output": "heatmaps/wifi.png",
        "generate_png": False,
        "path_weight": 4.0,
        "path_opacity": 0.85,
        "show_start_end_markers": False,
        "visualize_wifi_path": True,
        "wifi_colormap_colors": ['#d7191c', '#fdae61', '#a6d96a', '#1a9641'],
        "wifi_colormap_index": [-85, -75, -65],
        "wifi_legend_caption": "WiFi Signalstärke (dBm)"
    },
    # --- Kumulierte GPS-Qualität (alle Sessions) ---
    "quality_kumuliert": {
        "output": "heatmaps/quality_kumuliert.html",
        "png_output": "heatmaps/quality_kumuliert.png",
        "generate_png": False,
        "radius": 15,
        "blur": 20,
        "show_start_end_markers": False,
        "visualize_quality_path": True,
        "quality_colormap_colors": ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'],
        "quality_colormap_index": [4, 6, 8, 10],
        "quality_legend_caption": "GPS Qualität kumuliert (Satelliten)",
        "use_heatmap_with_time": False,
        "use_satellite_weight": False,
        "path_weight": 2.0,
        "path_opacity": 0.6,
    },
    # --- Kumulierte WiFi-Signalstärke (alle Sessions) ---
    "wifi_kumuliert": {
        "output": "heatmaps/wifi_kumuliert.html",
        "png_output": "heatmaps/wifi_kumuliert.png",
        "generate_png": False,
        "radius": 15,
        "blur": 20,
        "show_start_end_markers": False,
        "visualize_wifi_path": True,
        "wifi_colormap_colors": ['#d7191c', '#fdae61', '#a6d96a', '#1a9641'],
        "wifi_colormap_index": [-85, -75, -65],
        "wifi_legend_caption": "WiFi Signalstärke kumuliert (dBm)",
    }
}

# Recorder (unverändert)
REC_CONFIG = {
    "serial_port": os.getenv("GPS_SERIAL_PORT"),
    "baudrate": int(os.getenv("GPS_BAUDRATE") or "9600"),
    "test_mode": os.getenv("TEST_MODE", "False").lower() == "true",
    "storage_interval": int(os.getenv("REC_STORAGE_INTERVAL", 1)),  # NEU: Aus .env lesen
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
    "assist_now_url": os.getenv("ASSIST_NOW_URL", "https://api.thingstream.io/assistnow/online"),  # Standard auf Online
    "assist_now_token": os.getenv("ASSIST_NOW_TOKEN"),
    "days": 7
}

# Nachverarbeitung
POST_PROCESSING_CONFIG = {
    "method": "kalman",
    "moving_average_window": int(os.getenv("MOVING_AVERAGE_WINDOW", 5)),
    "kalman_measurement_noise": float(os.getenv("KALMAN_MEASUREMENT_NOISE", 0.5)),
    "kalman_process_noise": float(os.getenv("KALMAN_PROCESS_NOISE", 0.2)),
    "hdop_threshold": float(os.getenv("HDOP_THRESHOLD", 2.5)),
    "max_speed_mps": float(os.getenv("MAX_SPEED_MPS", 1.5)),
    "dead_reckoning_enabled": os.getenv("DEAD_RECKONING_ENABLED", "True").lower() == "true",
    "outlier_detection": {
        "enable": os.getenv("OUTLIER_DETECTION_ENABLE", "True").lower() == "true",
        "max_speed_mps": float(os.getenv("MAX_SPEED_MPS", 1.5))
    }
}

# GPS GNSS Modus: 'sbas' = GPS+SBAS/EGNOS, 'glonass' = GPS+GLONASS (NEO-7M kann nicht beides)
GPS_CONFIG = {
    "gnss_mode": os.getenv("GPS_GNSS_MODE", "sbas").lower(),  # 'sbas' oder 'glonass'
}

# --- NEU: Pi Status Konfiguration ---
PI_STATUS_CONFIG = {
    # MQTT Topic, auf dem die Temperatur veröffentlicht wird
    "topic_pi_status": str(os.getenv("MQTT_TOPIC_PI_STATUS", "worx/pi_status")).split("#")[0].strip(),
    # Intervall in Sekunden, wie oft die Temperatur gesendet werden soll
    "pi_status_interval": int(str(os.getenv("PI_STATUS_INTERVAL", "60")).split("#")[0].strip())
    }

# --- ENDE NEU ---


# Validierung
def validate_config():
    required_mqtt = ["topic_gps", "topic_status", "topic_control"]
    required_rec = ["baudrate", "storage_interval"]
    required_problem = ["problem_json", "max_problemzonen", "problem_threshold_time"]
    required_assist = [] # Wir nutzen jetzt AssistNow Autonomous (kein Token nötig)

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

    # Optional: Neue Werte validieren
    if not PI_STATUS_CONFIG.get("topic_pi_status"):
        missing.append("PI_STATUS_CONFIG['topic_pi_status'] (oder MQTT_TOPIC_PI_STATUS in .env)")

    pi_interval_val = PI_STATUS_CONFIG.get("pi_status_interval")
    try:
        if pi_interval_val is None or int(pi_interval_val) <= 0:
            print(f"WARNUNG: PI_STATUS_CONFIG['pi_status_interval'] ('{pi_interval_val}') ist ungültig oder nicht gesetzt. Verwende Standard 60s.")
            PI_STATUS_CONFIG["pi_status_interval"] = 60
    except ValueError: # Falls es nach der Bereinigung immer noch kein Int ist
        print(f"WARNUNG: PI_STATUS_CONFIG['pi_status_interval'] ('{pi_interval_val}') konnte nicht in eine Zahl umgewandelt werden. Verwende Standard 60s.")
        PI_STATUS_CONFIG["pi_status_interval"] = 60

    if missing:
        print("\nWARNUNG: Folgende kritische Konfigurationswerte fehlen oder sind nicht gesetzt:")
        print("Bitte prüfe deine .env Datei oder die Standardwerte in config.py.")
        for item in missing:
            print(f" - {item}")
        print("-" * 30)
    else:
        print("Konfigurationsvalidierung erfolgreich.")


validate_config()
