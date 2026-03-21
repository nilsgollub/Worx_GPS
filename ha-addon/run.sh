#!/bin/bash

# --- Home Assistant Add-on Startskript ---
echo "================================================================="
echo "   Worx GPS Monitoring - Home Assistant Add-on Start"
echo "================================================================="

CONFIG_PATH="/data/options.json"

# 1. Konfiguration einlesen (via jq aus /data/options.json)
echo "[System] Lese Konfiguration aus $CONFIG_PATH..."
if [ -f "$CONFIG_PATH" ]; then
    DEBUG_LOGGING=$(jq --raw-output '.debug_logging // false' $CONFIG_PATH)
    MQTT_HOST=$(jq --raw-output '.mqtt_host // "core-mosquitto"' $CONFIG_PATH)
    MQTT_PORT=$(jq --raw-output '.mqtt_port // 1883' $CONFIG_PATH)
    MQTT_USER=$(jq --raw-output '.mqtt_user // ""' $CONFIG_PATH)
    MQTT_PASS=$(jq --raw-output '.mqtt_password // ""' $CONFIG_PATH)
else
    echo "[Warnung] Keine options.json gefunden, nutze Standardwerte."
    DEBUG_LOGGING="false"
    MQTT_HOST="localhost"
    MQTT_PORT=1883
fi

# 2. Persistente Daten vorbereiten
# Die App braucht Schreibzugriff auf die DB und Heatmaps im /data Verzeichnis
echo "[System] Bereite persistenten Speicher in /data vor..."
mkdir -p /data/heatmaps
mkdir -p /data/data
mkdir -p /data/logs

# Falls noch keine DB da ist, initialisiere eine leere oder kopiere das Schema
if [ ! -f /data/worx_gps.db ]; then
    echo "[System] Erstelle neue Datenbank in /data/worx_gps.db..."
    # (Optional: Hier könnte ein Initial-Schema kopiert werden)
fi

# 3. Umgebungsvariablen für Python (.env Mapping)
# Wir mappen die HA-Optionen auf die Variablennamen der App
export MQTT_HOST=$MQTT_HOST
export MQTT_PORT=$MQTT_PORT
export MQTT_USER=$MQTT_USER
export MQTT_PASSWORD=$MQTT_PASS
export DATA_DIR="/data"
export HEATMAPS_DIR="/data/heatmaps"
export DB_PATH="/data/worx_gps.db"
export FLASK_PORT=5001

if [ "$DEBUG_LOGGING" = "true" ]; then
    echo "[System] Debug-Logging AKTIVIERT."
    export LOG_LEVEL="DEBUG"
else
    export LOG_LEVEL="INFO"
fi

# 4. Dienste starten
echo "[System] Starte Worx GPS Dienste..."

# Wir nutzen start_services.py, müssen aber Pfade anpassen falls nötig
# Da wir im Docker sind, können wir auch direkt parallel starten
python3 web_ui/webui.py &
python3 Worx_GPS.py &

# Halte den Container am Leben
wait -n
exit $?
