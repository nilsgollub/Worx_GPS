# 📋 Worx_GPS - Schnell-Referenz & Cheat Sheet

## 🚀 Raspberry Pi - Erste Schritte (5 min)

```bash
# 1. SSH zum Pi
ssh nilsgollub@192.168.1.202  # Passwort: JhiswenP3003!

# 2. GPS-Modul überprüfen (WICHTIG!)
cat /dev/ttyACM0 | head -5      # Sollte NMEA-Daten zeigen!

# 3. Repository prüfen
cd ~/Worx_GPS && ls -la

# 4. Virtual Environment aktivieren
source .venv/bin/activate

# 5. Service starten
systemctl --user start worx_gps_rec.service

# 6. Status prüfen
systemctl --user status worx_gps_rec.service

# 7. Logs ansehen
journalctl --user -u worx_gps_rec.service -f
```

---

## 🛰️ GPS-Modul überprüfen

```bash
# Port auflisten
ls -la /dev/ttyACM*     # Sollte /dev/ttyACM0 zeigen (oder USB0)

# Live GPS-Daten ansehen
cat /dev/ttyACM0 | head -10
# Sollte sehen: $GPGGA,... $GPRMC,... etc.

# Datenfluss testen  
timeout 5 cat /dev/ttyACM0 | wc -l       # Sollte >0 zeigen

# Fehler? → Siehe GPS_MODULE_HARDWARE_SETUP.md!
```

---

## 🔧 Systemd Service

```bash
# Status
systemctl --user status worx_gps_rec.service

# Start
systemctl --user start worx_gps_rec.service

# Stop
systemctl --user stop worx_gps_rec.service

# Restart
systemctl --user restart worx_gps_rec.service

# Enable (Autostart)
systemctl --user enable worx_gps_rec.service

# Disable
systemctl --user disable worx_gps_rec.service

# Logs
journalctl --user -u worx_gps_rec.service -f

# Logs (letzte 50 Zeilen)
journalctl --user -u worx_gps_rec.service -n 50

# Logs (nur Fehler)
journalctl --user -u worx_gps_rec.service -p err
```

---

## 📊 Daten & Überwachung

```bash
# Daten-Verzeichnis prüfen
ls -lh ~/Worx_GPS/data/

# Größe
du -sh ~/Worx_GPS/data/

# Letzte Einträge anzeigen
tail ~/Worx_GPS/data/maehvorgang_*.json

# Problemzonen prüfen
cat ~/Worx_GPS/data/problemzonen.json | python3 -m json.tool

# Disk verfügbar
df -h /

# RAM verfügbar
free -h

# Pi Temperatur
vcgencmd measure_temp

# CPU Auslastung
top -b -n 1 | head -10
```

---

## 🌐 MQTT & Netzwerk

```bash
# MQTT Broker erreichbar?
nc -zv 192.168.1.100 1883

# GPS Daten empfangen?
mosquitto_sub -h 192.168.1.100 -t "worx/gps" -v

# Pi Status empfangen?
mosquitto_sub -h 192.168.1.100 -t "worx/pi_status" -v

# Alle Topics
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v

# IP Adresse überprüfen
hostname -I

# Ping Pi
ping 192.168.1.202
```

---

## 🔍 Testing & Debugging

```bash
# Tests laufen
cd ~/Worx_GPS
python3 -m pytest tests/ -v

# Server Tests
python3 -m pytest tests/test_servers.py -v

# Manuell starten (Debugging)
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py

# Mit Debug-Output
DEBUG_LOGGING=true python3 Worx_GPS_Rec.py

# Test-Modus (Fake Daten)
TEST_MODE=true python3 Worx_GPS_Rec.py
```

---

## 🌐 Web UI

```bash
# Lokal starten (für Testing)
python3 -m web_ui.webui

# Im Browser öffnen
http://localhost:5000

# Vom Pi aus
http://192.168.1.202:5000

# API Status testen
curl http://localhost:5000/api/status

# API Stats testen
curl http://localhost:5000/api/stats
```

---

## 📱 Systemd Setup (Installation)

```bash
# 1. Service Datei erstellen
nano ~/.config/systemd/user/worx_gps_rec.service

# 2. Inhalt aus systemd_worx_gps_rec.service kopieren

# 3. Speichern & aktivieren
systemctl --user daemon-reload
systemctl --user enable worx_gps_rec.service
systemctl --user start worx_gps_rec.service

# 4. Überprüfung
systemctl --user status worx_gps_rec.service
```

---

## 🔐 Konfiguration

```bash
# .env bearbeiten
nano ~/Worx_GPS/.env

# Wichtige Einstellungen
MQTT_HOST=192.168.1.100
MQTT_PORT=1883
TEST_MODE=false
DEBUG_LOGGING=false

# Speichern: Ctrl+O, Enter, Ctrl+X
```

---

## 🐛 Fehlersuche

| Problem | Befehl |
|---------|--------|
| Service läuft nicht | `systemctl --user status worx_gps_rec.service` |
| Keine Logs | `journalctl --user -u worx_gps_rec.service -n 50` |
| MQTT nicht erreichbar | `nc -zv 192.168.1.100 1883` |
| Keine GPS-Daten | `mosquitto_sub -h 192.168.1.100 -t "worx/gps" -v` |
| Daten nicht gespeichert | `ls -lah ~/Worx_GPS/data/` |
| Pi zu heiß | `vcgencmd measure_temp` |
| Disk voll | `df -h /` |
| RAM zu voll | `free -h` |

---

## 🚀 Firewall (Falls aktiviert)

```bash
# MQTT Port öffnen
sudo ufw allow 1883/tcp

# SSH Port (falls nicht Standard)
sudo ufw allow 22/tcp

# Web UI Port (optional)
sudo ufw allow 5000/tcp

# Status
sudo ufw status
```

---

## 💾 Backup & Archivierung

```bash
# Backup erstellen
tar czf ~/backup_$(date +%Y%m%d).tar.gz ~/Worx_GPS/data/

# Backup-Liste
ls -lh ~backup*.tar.gz

# Auf USB kopieren
rsync -av ~/Worx_GPS/data/ /mnt/usb/worx_backup/

# Alte Daten löschen (VORSICHT!)
rm ~/Worx_GPS/data/maehvorgang_2026-01-*.json
```

---

## 🔄 Häufige Aufgaben

### Neu starten

```bash
sudo reboot
```

### Service neu laden

```bash
systemctl --user daemon-reload
systemctl --user restart worx_gps_rec.service
```

### Daten anschauen

```bash
# Aktuelle Datei
tail -f ~/Worx_GPS/data/maehvorgang_*.json

# JSON formatiert
cat ~/Worx_GPS/data/maehvorgang_*.json | python3 -m json.tool | less
```

### Performance tuning

```bash
# Top 5 Prozesse
ps aux --sort=-%cpu | head -6

# Top speicherfresser
ps aux --sort=-%mem | head -6
```

---

## 📚 Dateien & Verzeichnisse

```bash
# Projektverzeichnis
~/Worx_GPS/

# Daten
~/Worx_GPS/data/
  └─ maehvorgang_YYYY-MM-DD_HH.json
  └─ problemzonen.json

# Konfiguration
~/.env
~/.config/systemd/user/worx_gps_rec.service

# Logs
journalctl --user -u worx_gps_rec.service

# Heatmaps
~/Worx_GPS/heatmaps/
```

---

## 🎯 Checkliste für Neustarts

Nach Pi-Neustart überprüfen:

```bash
# 1. SSH funktioniert
ssh nilsgollub@192.168.1.202 "echo OK"

# 2. Service läuft automatisch
systemctl --user status worx_gps_rec.service

# 3. Daten werden empfangen
mosquitto_sub -h 192.168.1.100 -t "worx/gps" -C 1

# 4. Logs clean
journalctl --user -u worx_gps_rec.service -n 10
```

---

## 💡 Pro Tipps

1. **Continuous Monitoring:**
   ```bash
   watch -n 5 'systemctl --user status worx_gps_rec && ls -lh ~/Worx_GPS/data/'
   ```

2. **Schnelles System Status Check:**
   ```bash
   ssh nilsgollub@192.168.1.202 "systemctl --user status worx_gps_rec && df -h"
   ```

3. **Backup vor großen Änderungen:**
   ```bash
   tar czf ~/backup_$(date +%Y%m%d_%H%M%S).tar.gz ~/Worx_GPS/
   ```

4. **Logs mit Timestamps:**
   ```bash
   journalctl --user -u worx_gps_rec.service --since "1 hour ago"
   ```

5. **MQTT Message Count:**
   ```bash
   # Zähle Nachrichten für 10 Sekunden
   timeout 10 mosquitto_sub -h 192.168.1.100 -t "worx/gps" -v | wc -l
   ```

---

**Letzte Aktualisierung**: 2026-03-17  
**Status**: ✅ Praxiserprobt
