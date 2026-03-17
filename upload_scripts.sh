#!/bin/bash
# Script zum Hochladen der Diagnose-Tools zum Pi
# Für Linux/Mac Nutzer

RASPI_HOST="192.168.1.202"
RASPI_USER="nilsgollub"
RASPI_PATH="~/Worx_GPS"

echo "Uploading diagnostic scripts to $RASPI_HOST..."

# Upload run_funktionscheck.sh
scp run_funktionscheck.sh $RASPI_USER@$RASPI_HOST:$RASPI_PATH/

# Upload check_raspi.sh
scp check_raspi.sh $RASPI_USER@$RASPI_HOST:$RASPI_PATH/

# Mache Scripts ausführbar
ssh $RASPI_USER@$RASPI_HOST "chmod +x $RASPI_PATH/run_funktionscheck.sh $RASPI_PATH/check_raspi.sh"

echo "✅ Scripts uploaded successfully!"
echo "Run: ssh $RASPI_USER@$RASPI_HOST"
echo "Then: cd Worx_GPS && bash run_funktionscheck.sh"
