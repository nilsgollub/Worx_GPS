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
export MQTT_TOPIC_GPS="worx/gps"
export MQTT_TOPIC_STATUS="worx/status"
export MQTT_TOPIC_CONTROL="worx/control"
export MQTT_TOPIC_LOGS="worx/logs"
export DATA_DIR="/data"
export HEATMAPS_DIR="/data/heatmaps"
export DB_PATH="/data/worx_gps.db"
export FLASK_PORT=5001

# 3b. Worx Cloud Credentials (aus HA Add-on Options)
WORX_EMAIL=$(jq --raw-output '.worx_email // ""' $CONFIG_PATH)
WORX_PASSWORD=$(jq --raw-output '.worx_password // ""' $CONFIG_PATH)
WORX_CLOUD_TYPE=$(jq --raw-output '.worx_cloud_type // "worx"' $CONFIG_PATH)

export WORX_EMAIL=$WORX_EMAIL
export WORX_PASSWORD=$WORX_PASSWORD
export WORX_CLOUD_TYPE=$WORX_CLOUD_TYPE

echo "[System] Worx Cloud Email: '${WORX_EMAIL:-nicht gesetzt}'"

if [ "$DEBUG_LOGGING" = "true" ]; then
    echo "[System] Debug-Logging AKTIVIERT."
    export LOG_LEVEL="DEBUG"
else
    export LOG_LEVEL="INFO"
fi

# 3c. Erstelle persistente .env in /data, falls keine existiert (WICHTIG für HA Add-on!)
# Dadurch kann config.py alle Variablen finden, auch die wir nicht in config.yaml haben.
PERSISTENT_ENV="/data/.env"
if [ ! -f "$PERSISTENT_ENV" ]; then
    echo "[System] Initialisiere persistente .env in $PERSISTENT_ENV..."
    cat <<EOF > "$PERSISTENT_ENV"
# Worx GPS Add-on - Automatisierte Konfiguration
MQTT_HOST=$MQTT_HOST
MQTT_PORT=$MQTT_PORT
MQTT_USER=$MQTT_USER
MQTT_PASSWORD=$MQTT_PASS
MQTT_TOPIC_GPS=worx/gps
MQTT_TOPIC_STATUS=worx/status
MQTT_TOPIC_CONTROL=worx/control
MQTT_TOPIC_PI_STATUS=worx/pi/temperature
PI_STATUS_INTERVAL=30
WORX_EMAIL=$WORX_EMAIL
WORX_PASSWORD=$WORX_PASSWORD
WORX_CLOUD_TYPE=$WORX_CLOUD_TYPE
GPS_SERIAL_PORT=/dev/ttyACM0
GPS_BAUDRATE=9600
TEST_MODE=FALSE
FLASK_PORT=5001
FLASK_DEBUG=FALSE
GEO_ZOOM_START=20
GEO_MAX_ZOOM=22
DEAD_RECKONING_ENABLED=FALSE
MOVING_AVERAGE_WINDOW=5
KALMAN_MEASUREMENT_NOISE=0.5
KALMAN_PROCESS_NOISE=0.2
HDOP_THRESHOLD=2.5
MAX_SPEED_MPS=1.5
OUTLIER_DETECTION_ENABLE=TRUE
HEATMAP_GENERATE_PNG=FALSE
HEATMAP_RADIUS=5
HEATMAP_BLUR=10
EOF
    echo "[System] .env erfolgreich initialisiert."
else
    # Falls Datei existiert, aktualisiere nur die Kern-Secrets aus den HA-Optionen
    # (Damit Änderungen in der HA-GUI auch in der .env landen)
    echo "[System] Aktualisiere Secrets in bestehender .env..."
    sed -i "s/^MQTT_HOST=.*/MQTT_HOST=$MQTT_HOST/" "$PERSISTENT_ENV"
    sed -i "s/^MQTT_PORT=.*/MQTT_PORT=$MQTT_PORT/" "$PERSISTENT_ENV"
    sed -i "s/^MQTT_USER=.*/MQTT_USER=$MQTT_USER/" "$PERSISTENT_ENV"
    sed -i "s/^MQTT_PASSWORD=.*/MQTT_PASSWORD=$MQTT_PASS/" "$PERSISTENT_ENV"
    sed -i "s/^WORX_EMAIL=.*/WORX_EMAIL=$WORX_EMAIL/" "$PERSISTENT_ENV"
    sed -i "s/^WORX_PASSWORD=.*/WORX_PASSWORD=$WORX_PASSWORD/" "$PERSISTENT_ENV"
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
