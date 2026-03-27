#!/bin/bash
# Worx_GPS - ALLE Funktionschecks auf einmal
# Einfach kopieren und auf dem Pi ausführen

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         WORX_GPS FUNKTIONSCHECK - ALLE TESTS              ║"
echo "║    (3-5 Minuten, alles auf einmal durchlaufen)            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Wechsle ins Script-Verzeichnis oder nutze aktuelles Verzeichnis
cd "$(dirname "$0")" 2>/dev/null || true

# 1️⃣ SYSTEM
echo "1️⃣  SYSTEM INFORMATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
hostname
uname -r
python3 --version
echo ""

# 2️⃣ SPEICHER
echo "2️⃣  DISK & SPEICHER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Disk:"
df -h / | tail -1 | awk '{printf "  %s (%s/%s, %s frei)\n", $1, $3, $2, $4}'
echo "Memory:"
free -h | tail -1 | awk '{printf "  %s/%s (%s frei)\n", $3, $2, $7}'
echo ""

# 3️⃣ GPS-MODUL
echo "3️⃣  GPS-MODUL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -e /dev/ttyACM0 ]; then
    echo "✅ /dev/ttyACM0 gefunden"
    echo "   Berechtigungen: $(ls -l /dev/ttyACM0 | awk '{print $1, $3, $4}')"
else
    echo "❌ /dev/ttyACM0 NICHT GEFUNDEN"
    if [ -e /dev/ttyUSB0 ]; then
        echo "   ℹ️  aber /dev/ttyUSB0 vorhanden"
    else
        echo "   ℹ️  Keine USB/Serial Geräte gefunden"
    fi
fi
echo ""

# 4️⃣ SERVICE
echo "4️⃣  SERVICE STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if systemctl --user is-active --quiet worx_gps_rec.service; then
    echo "✅ Service läuft"
    systemctl --user status worx_gps_rec.service --no-pager | head -4
else
    echo "❌ Service läuft NICHT"
    echo "   Status: $(systemctl --user is-active worx_gps_rec.service)"
fi
echo ""

# 5️⃣ GPS-ROHDATEN
echo "5️⃣  GPS-ROHDATEN TEST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Versuche 3 Sekunden GPS-Daten zu lesen..."
gps_output=$(timeout 3 cat /dev/ttyACM0 2>/dev/null | head -2)
if [ -n "$gps_output" ]; then
    echo "✅ GPS-Daten empfangen:"
    echo "$gps_output" | head -1
else
    echo "❌ KEINE GPS-Daten empfangen!"
    echo "   Wurde timeout 3 cat /dev/ttyACM0 ausgeführt?"
fi
echo ""

# 6️⃣ LOGS
echo "6️⃣  SERVICE LOGS (Letzte 10 Zeilen)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
journalctl --user -u worx_gps_rec.service -n 10 --no-pager
if journalctl --user -u worx_gps_rec.service -n 50 --no-pager | grep -q "ERROR\|Exception"; then
    echo "⚠️  FEHLER in Logs gefunden! (siehe oben)"
fi
echo ""

# 7️⃣ DATEN
echo "7️⃣  GESPEICHERTE FAHRTDATEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
count=$(ls -1 data/maehvorgang*.json 2>/dev/null | wc -l)
if [ "$count" -gt 0 ]; then
    echo "✅ $count Fahrtdaten-Dateien vorhanden:"
    ls -lh data/maehvorgang*.json 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
else
    echo "❌ KEINE Fahrtdaten vorhanden!"
    echo "   data/ Verzeichnis: $(ls -la data/ 2>/dev/null | wc -l) Einträge"
fi
echo ""

# 8️⃣ MQTT
echo "8️⃣  MQTT-BROKER ERREICHBAR?"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if timeout 2 bash -c "cat > /dev/null < /dev/tcp/192.168.1.100/1883" 2>/dev/null; then
    echo "✅ MQTT Broker (192.168.1.100:1883) erreichbar"
else
    echo "❌ MQTT Broker nicht erreichbar"
    echo "   Falls MQTT auf anderem Host läuft, config.py prüfen"
fi
echo ""

# 9️⃣ VENV
echo "9️⃣  VIRTUAL ENVIRONMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d .venv ]; then
    echo "✅ Virtual Environment vorhanden"
else
    echo "⚠️  Virtual Environment fehlt"
fi
echo ""

# 🔟 ZUSAMMENFASSUNG
echo "🔟 ZUSAMMENFASSUNG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Prüfen Sie diese Punkte:"
checks=0
total=0

# Check 1: Disk
total=$((total+1))
free_disk=$(df -h / | tail -1 | awk '{print $4}')
if [ "$free_disk" != "" ]; then
    checks=$((checks+1))
fi

# Check 2: GPS
total=$((total+1))
if [ -e /dev/ttyACM0 ]; then
    checks=$((checks+1))
fi

# Check 3: Service
total=$((total+1))
if systemctl --user is-active --quiet worx_gps_rec.service; then
    checks=$((checks+1))
fi

# Check 4: Logs
total=$((total+1))
if ! journalctl --user -u worx_gps_rec.service -n 20 --no-pager | grep -q "ERROR"; then
    checks=$((checks+1))
fi

# Check 5: Daten
total=$((total+1))
if [ "$(ls -1 data/maehvorgang*.json 2>/dev/null | wc -l)" -gt 0 ]; then
    checks=$((checks+1))
fi

echo "✅ Bestandene Checks: $checks/$total"
echo ""

if [ "$checks" -eq "$total" ]; then
    echo "🎉 ALLES GRÜN! System läuft einwandfrei!"
else
    echo "⚠️  Einige Probleme gefunden - siehe oben für Details"
    echo "    Lesen Sie: ~/Worx_GPS/FUNKTIONSCHECK_ANLEITUNG.md"
fi

echo ""
echo "╚════════════════════════════════════════════════════════════╝"
