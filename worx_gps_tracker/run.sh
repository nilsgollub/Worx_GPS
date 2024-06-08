#!/bin/sh

# Umgebungsvariablen setzen
export ENV_FILE=$(jq --raw-output '.env_file' /data/options.json)
export OUTPUT_DIR=$(jq --raw-output '.output_dir' /data/options.json)

# Skript ausführen
python3 /app/Worx_GPS.py
