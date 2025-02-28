# config.py
import os
from dotenv import load_dotenv

load_dotenv(".env")  # Laden der Umgebungsvariablen

MQTT_CONFIG = {
    "broker": os.getenv("MQTT_HOST"),
    "port": int(os.getenv("MQTT_PORT", 1883)),
    "topic_gps": os.getenv("MQTT_TOPIC_GPS"),
    "topic_status": os.getenv("MQTT_TOPIC_STATUS"),
    "topic_control": os.getenv("MQTT_TOPIC_CONTROL"),
    "user": os.getenv("MQTT_USER"),
    "password": os.getenv("MQTT_PASSWORD"),
    "broker_lokal": os.getenv("MQTT_HOST_LOCAL"),
    "port_lokal": int(os.getenv("MQTT_PORT_LOCAL", 1883)),
    "user_local": os.getenv("MQTT_USER_LOCAL"),
    "password_local": os.getenv("MQTT_PASSWORD_LOCAL"),
}
HEATMAP_CONFIG = {
    "heatmap_aktuell": "heatmap_aktuell.html",
    "heatmap_10_maehvorgang": "heatmap_10_maehvorgang.html",
    "heatmap_kumuliert": "heatmap_kumuliert.html",
    "problemzonen_heatmap": "heatmap_problemzonen.html",
    "heatmap_aktuell_png": "heatmap_aktuell.png",
    "heatmap_kumuliert_png": "heatmap_kumuliert.png",
    "problemzonen_heatmap_png": "problemzonen_heatmap.png",
    "tile": 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
}
GEO_CONFIG = {
    "lat_bounds": [46.811819, 46.812107],
    "lon_bounds": [7.132838, 7.133173],
    "map_center": [(46.811819 + 46.812107) / 2, (7.132838 + 7.133173) / 2],
}
PROBLEM_CONFIG = {
    "max_problemzonen": 20,
    "problem_json": "problemzonen.json"
}

ASSIST_NOW_CONFIG = {
    "assist_now_token": os.getenv("ASSIST_NOW_TOKEN"),
    "assist_now_offline_url": "https://offline-live1.services.u-blox.com/GetOfflineData.ashx",
    "assist_now_enabled": os.getenv("ASSIST_NOW_ENABLED", "False").lower() == "true",
}
REC_CONFIG = {
    "serial_port": os.getenv("SERIAL_PORT", '/dev/ttyACM0'),
    "baudrate": int(os.getenv("BAUDRATE", 9600)),
    "test_mode": os.getenv("TEST_MODE", "False").lower() == "true",
    "gps_message_count": 100,  # Anzhal der GPS Zeilen pro Paket
    "storage_interval": 2
}
