#!/bin/bash

# Worx_GPS Funktionscheck für Raspberry Pi Zero
# Kostet 2-3 Minuten, zeigt komplette Diagnose

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      WORX_GPS RASPBERRY PI ZERO - FUNKTIONSCHECK          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# FARBEN für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}1️⃣  SYSTEM INFO${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Hostname: $(hostname)"
echo "Kernel: $(uname -r)"
echo "Arch: $(uname -m)"
echo "Python: $(python3 --version 2>&1)"
echo "Uptime: $(uptime -p 2>/dev/null || uptime)"
echo ""

echo -e "${BLUE}2️⃣  DISK & SPEICHER${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -n "Disk (/): "
df -h / | tail -1 | awk '{print $4 " frei (" $5 " verwendet)"}'
echo -n "Memory: "
free -h | grep Mem | awk '{print $7 " frei / " $2 " gesamt"}'
echo ""

echo -e "${BLUE}3️⃣  WORX_GPS PROJEKT${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd ~/Worx_GPS 2>/dev/null || { echo -e "${RED}❌ Worx_GPS Verzeichnis nicht gefunden!${NC}"; exit 1; }
echo "Arbeitsverzeichnis: $(pwd)"
echo "Python-Dateien: $(ls -1 *.py 2>/dev/null | wc -l)"
if [ -d .venv ]; then
    echo -e "${GREEN}✅ Virtual Environment vorhanden${NC}"
else
    echo -e "${RED}❌ Virtual Environment FEHLT${NC}"
fi
echo ""

echo -e "${BLUE}4️⃣  GPS-MODUL STATUS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -e /dev/ttyACM0 ]; then
    echo -e "${GREEN}✅ GPS-Port /dev/ttyACM0 gefunden${NC}"
    echo "   Berechtigung: $(ls -l /dev/ttyACM0 | awk '{print $1, $3, $4}')"
    echo "   GPS-Daten-Test:"
    timeout 2 cat /dev/ttyACM0 | head -1 | head -c 80
    if [ $? -eq 0 ]; then
        echo -e "\n${GREEN}   ✅ NMEA-Daten werden empfangen${NC}"
    else
        echo -e "\n${YELLOW}   ⚠️  Keine NMEA-Daten oder Timeout${NC}"
    fi
elif ls /dev/ttyUSB* >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Kein ttyACM0, aber ttyUSB* gefunden:${NC}"
    ls -1 /dev/ttyUSB*
else
    echo -e "${RED}❌ KEIN GPS-MODUL GEFUNDEN!${NC}"
    echo "   Verfügbare Geräte: $(ls /dev/tty* 2>/dev/null | tr '\n' ' ')"
fi
echo ""

echo -e "${BLUE}5️⃣  SERVICE STATUS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
status=$(systemctl --user is-active worx_gps_rec.service 2>/dev/null)
if [ "$status" = "active" ]; then
    echo -e "${GREEN}✅ Service AKTIV${NC}"
    systemctl --user status worx_gps_rec.service --no-pager | head -3
else
    echo -e "${RED}❌ Service NICHT AKTIV${NC}"
    echo "   Status: $status"
fi
echo ""

echo -e "${BLUE}6️⃣  LOGS (Letzten 10 Zeilen)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
journalctl --user -u worx_gps_rec.service -n 10 --no-pager 2>/dev/null | tail -10
if grep -q "ERROR\|Exception" <<< "$(journalctl --user -u worx_gps_rec.service -n 50 --no-pager)"; then
    echo -e "${RED}⚠️  FEHLER in Logs gefunden!${NC}"
fi
echo ""

echo -e "${BLUE}7️⃣  GESPEICHERTE DATEN${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d data ]; then
    echo "Daten-Verzeichnis: $(pwd)/data"
    count=$(ls -1 data/maehvorgang*.json 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        echo -e "${GREEN}✅ $count Fahrtdaten-Dateien vorhanden${NC}"
        ls -lh data/maehvorgang*.json 2>/dev/null | tail -3 | awk '{print "   " $9 " (" $5 ")"}'
    else
        echo -e "${YELLOW}⚠️  Keine Fahrtdaten vorhanden${NC}"
    fi
    
    if [ -f data/problemzonen.json ]; then
        echo -e "${GREEN}✅ Problemzonen-Datei vorhanden${NC}"
        ls -lh data/problemzonen.json | awk '{print "   Size: " $5}'
    fi
else
    echo -e "${RED}❌ data/ Verzeichnis fehlt!${NC}"
fi
echo ""

echo -e "${BLUE}8️⃣  KONFIGURATION${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f pi_env.txt ] || [ -f .env ]; then
    config_file=$([ -f pi_env.txt ] && echo "pi_env.txt" || echo ".env")
    echo "Konfigurationsdatei: $config_file"
    echo "GPS Settings:"
    grep "GPS_" $config_file | head -3
    echo "MQTT Settings:"
    grep "MQTT_" $config_file | grep -v PASSWORD | head -3
else
    echo -e "${RED}❌ Konfigurationsdatei fehlt!${NC}"
fi
echo ""

echo -e "${BLUE}9️⃣  NETZWERK${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "IP-Adresse:"
ip addr show | grep "inet " | grep -v 127.0.0.1 | awk '{print "   " $2}'
echo "MQTT Broker erreichbar?"
mqtt_host=$(grep MQTT_HOST pi_env.txt .env 2>/dev/null | grep -o '[0-9.]*' | head -1)
if [ -n "$mqtt_host" ]; then
    if timeout 1 bash -c "cat > /dev/null < /dev/tcp/$mqtt_host/1883" 2>/dev/null; then
        echo -e "   ${GREEN}✅ $mqtt_host:1883 erreichbar${NC}"
    else
        echo -e "   ${YELLOW}⚠️  $mqtt_host:1883 nicht erreichbar${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  MQTT_HOST nicht konfiguriert${NC}"
fi
echo ""

echo -e "${BLUE}🔟 PROZESSE${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ps aux | grep -E "Worx_GPS|python3.*Worx" | grep -v grep
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Worx_GPS Python-Prozess läuft nicht direkt${NC}"
    echo "   (Läuft wahrscheinlich als Systemd Service)"
fi
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  CHECK ABGESCHLOSSEN                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Gehen Sie zu: ~/Worx_GPS"
echo "Für mehr Infos: cat DEBUG_CHECKLIST_SSH.md"
echo ""
