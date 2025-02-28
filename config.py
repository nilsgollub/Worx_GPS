import os
from dotenv import load_dotenv

load_dotenv()

# MQTT
MQTT_CONFIG = {
    "host": os.getenv("MQTT_HOST"),
    "port": int(os.getenv("MQTT_PORT")),
    "user": os.getenv("MQTT_USER"),
    "password": os.getenv("MQTT_PASSWORD"),
    "host_lokal": os.getenv("MQTT_HOST_LOKAL"),  # Korrektur: Key angepasst.
    "port_lokal": int(os.getenv("MQTT_PORT_LOKAL")) if os.getenv("MQTT_PORT_LOKAL") else 1883,
    # Korrektur: Key angepasst.
    "user_local": os.getenv("MQTT_USER_LOCAL"),
    "password_local": os.getenv("MQTT_PASSWORD_LOCAL"),
}

# GPS
GEO_CONFIG = {
    "is_fake": False,
    "fake_gps_range": ((46.811819, 46.811919), (7.132838, 7.132938)),  # (lat, lon)
    "lat_bounds": (46.810819, 46.812919),  # (min, max)
    "lon_bounds": (7.131838, 7.133938),  # (min, max)
    "map_center": (46.811819, 7.132838),
    "zoom_start": 15,
    "crop_coordinates": ((46.8115, 7.1325), (46.8120, 7.1330)),  # (left-top, right-bottom)
    "crop_enabled": False,
    "save_interval": 5,
}

# Heatmap
HEATMAP_CONFIG = {
    "tile": 'OpenStreetMap',
}

# Recorder
REC_CONFIG = {
    "serial_port": os.getenv("GPS_SERIAL_PORT"),
    "baudrate": int(os.getenv("GPS_BAUDRATE")),
    "test_mode": os.getenv("TEST_MODE") == "True",  # Korrektur: Optionale Variable erstellt.
}

# Problemzonen
PROBLEM_CONFIG = {
    "problem_json": "problemzonen.json",
    "max_problemzonen": 100  # Korrektur: Key hinzugefügt.
}
# Assist now
ASSIST_NOW_CONFIG = {
    "assist_now_enabled": os.getenv("ASSIST_NOW_ENABLED") == "True",  # Korrektur: Key hinzugefügt.
    "assist_now_offline_url": "https://offline-live1.services.u-blox.com/GetOfflineData.ashx",
    # Korrektur: Key angepasst.
    "assist_now_token": os.getenv("ASSIST_NOW_TOKEN")  # Korrektur: Key hinzugefügt.
}
