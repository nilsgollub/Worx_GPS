# 🔧 Raspberry Pi Zero - Deployment & Betriebshandbuch

**IP-Adresse**: 192.196.1.202  
**Benutzer**: nilsgollub  
**Hardwarebeschränkungen**: Minimal (Zero W)  
**Power**: Via Rasenmäher

---

## ⚡ Schnelstart (5 Minuten)

```bash
# 1. SSH auf Pi
ssh nilsgollub@192.196.1.202

# 2. App starten
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py

# 3. Läuft jetzt! Output sollte zeigen:
# "MQTT connected: worx/gps"
# "Recording started..."
```

---

## 📋 Was sollte auf dem Pi laufen?

### ✅ MUSS LAUFEN: `Worx_GPS_Rec.py`

Dies ist der **Hauptdatenerfasser**. Funktionen:

| Aufgabe | Quelle | Ziel |
| **GPS-Daten erfassen** | **GPS-Modul (USB/Serial lokal)** | **👉 MUSS IMMER LAUFEN** |
| **Mäher-Status empfangen** | **HomeAssistant via MQTT** | **👉 MUSS IMMER LAUFEN** |
| Daten speichern | DataRecorder | data/*.json |
| Probleme erkennen | GPS + Status Analyse | problemzonen.json |
| Web UI (optional) | `webui.py` | Browser (Port 5000) |

### 🔄 Datenfluss auf dem Pi

```
QUELLE 1: GPS-Position (Lokal Hardware)      
┌─→ GPS-Modul (/dev/ttyACM0 - NMEA @ 9600 baud)
│       ↓
│   gps_handler.py (parst mit pynmea2)
│       ↓ [lat, lon, timestamp, sats, fix_quality]
│
QUELLE 2: Mäher-Status (HomeAssistant → MQTT)
└─→ HomeAssistant
        ↓ [MQTT publish]
    MQTT Broker
        ↓
    mqtt_handler.py (empfängt Topic-Updates)
        ↓ [status, error, battery, ...]

    ↓ ↓ ↓ ↓ ↓

Worx_GPS_Rec.py (FUSION LAYER)
    ├→ GPS-Position + Mäher-Status kombinieren
    ├→ time-aligned speichern
    ├→ DataRecorder (Speichert in data/*.json)
    ├→ ProblemDetector (Anomalien)
    └→ SystemMonitor (Pi-Status)
        ↓
    data/maehvorgang_YYYY-MM-DD_HH.json
        ↓
    Optional → Web UI → Browser Visualisierung
```
    ├→ ProblemDetector (Findet Anomalien)
    └→ MqttHandler (optional: Rasenm. Fernsteuerung)
    └→ System Monitor (Sendet Pi-Status)
    ↓ [Status zurück: worx/status]
MQTT Broker
    ↓
Web UI (kann auf anderem Server sein)
```

---

## 🚀 Installation auf Pi Zero

### ⚠️ VORAUSSETZUNG: GPS-Modul angebunden

Das System benötigt ein angeschlossenes GPS-Modul! 

```bash
# GPS-Modul prüfen
ls -la /dev/ttyACM0    # Sollte existieren!

# Wenn nicht: GPS_MODULE_HARDWARE_SETUP.md lesen
# oder: ls /dev/tty* um den echten Port zu finden
```

### Schritt 1: System Vorbereitung

```bash
# SSH auf den Pi
ssh nilsgollub@192.196.1.202

# Raspberry Pi aktualisieren
sudo apt update
sudo apt upgrade -y

# Benötigte Tools installieren (inkl. serial-tools)
sudo apt install -y git python3-pip python3-venv picocom

# Verzeichnis überprüfen
ls -la ~/Worx_GPS

# GPS-Modul überprüfen (WICHTIG!)
cat /dev/ttyACM0 | head -5
# Sollte NMEA-Daten zeigen: $GPGGA,... $GPRMC,...
# Falls Fehler: Check GPS_MODULE_HARDWARE_SETUP.md
```

### Schritt 2: Python Environment

```bash
# Ins Projekt Verzeichnis
cd ~/Worx_GPS

# Virtual Environment erstellen (falls nicht vorhanden)
python3 -m venv .venv

# Aktivieren
source .venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt
# Das dauert ca. 5-10 Minuten auf Pi Zero!

# Überprüfung
python3 -c "import mqtt_handler; import gps_handler; print('✅ All imports OK')"
```

### Schritt 3: Konfiguration

```bash
# Environment Datei erstellen
nano .env
```

**Minimale .env Inhalt:**

```bash
# GPS-MODUL (KRITISCH!)
GPS_SERIAL_PORT=/dev/ttyACM0    # Port des GPS-Moduls
GPS_BAUDRATE=9600               # NMEA Standard

# MQTT (für Rasenm. Fernsteuerung, optional)
MQTT_HOST=192.168.1.100         # Falls vorhanden
MQTT_PORT=1883
MQTT_USERNAME=worx              # Falls Auth erforderlich
MQTT_PASSWORD=your_password

# Kein TEST_MODE auf Pi!
TEST_MODE=false

# Logging
DEBUG_LOGGING=false

# Recording
REC_STORAGE_INTERVAL=5
```

**Falls Modul an anderem Port:** (z.B. /dev/ttyUSB0)
```bash
sed -i 's|GPS_SERIAL_PORT=.*|GPS_SERIAL_PORT=/dev/ttyUSB0|' .env
```

**Speichern**: `Ctrl+O`, `Enter`, `Ctrl+X`

### Schritt 4: Test - Manuell Starten

```bash
# Sicherstellen dass venv aktiv ist
source .venv/bin/activate

# App starten
python3 Worx_GPS_Rec.py
```

**Erwartet Output** (wenn GPS-Modul angebunden):

```
2026-03-17 10:23:45 - INFO - [gps_handler:70] - Serielle Verbindung zu /dev/ttyACM0 erfolgreich
2026-03-17 10:23:46 - INFO - [gps_handler:150] - GPS Fix: qual=1, sats=8, lat=48.1234, lon=11.5678
2026-03-17 10:23:47 - INFO - [data_recorder:23] - Recording started
2026-03-17 10:23:48 - INFO - [Worx_GPS_Rec:45] - GPS-Daten empfangen & gespeichert
2026-03-17 10:23:49 - INFO - [mqtt_handler:105] - MQTT Status aktualisiert (optional)
```

**Stoppen**: `Ctrl+C`

**Falls Fehler: `/dev/ttyACM0: No such file or directory`**
→ GPS-Modul nicht angebunden! Siehe GPS_MODULE_HARDWARE_SETUP.md Schritt 1

Wenn es **funktioniert**, fahre mit Schritt 5 fort.  
Wenn **andere Fehler**, siehe [Troubleshooting](#troubleshooting)

### Schritt 5: Systemd Service (Autostart)

```bash
# Service Datei erstellen
nano ~/.config/systemd/user/worx_gps_rec.service
```

**Inhalt:**

```ini
[Unit]
Description=Worx GPS Recorder Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/nilsgollub/Worx_GPS
ExecStart=/home/nilsgollub/Worx_GPS/.venv/bin/python3 /home/nilsgollub/Worx_GPS/Worx_GPS_Rec.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=worx_gps_rec
Environment="PATH=/home/nilsgollub/Worx_GPS/.venv/bin"
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=default.target
```

```bash
# Speichern: Ctrl+O, Enter, Ctrl+X

# Service aktivieren
systemctl --user daemon-reload
systemctl --user enable worx_gps_rec.service
systemctl --user start worx_gps_rec.service

# Status überprüfen
systemctl --user status worx_gps_rec.service
```

**Output sollte sein:**

```
● worx_gps_rec.service - Worx GPS Recorder Service
   Loaded: loaded (...; enabled; ...)
   Active: active (running) since ...
```

---

## 🔍 Überprüfung - Läuft alles?

### Test 1: Ist der Service aktiv?

```bash
systemctl --user is-active worx_gps_rec.service
# Sollte antworten: active ✅
```

### Test 2: Logs ansehen

```bash
# Letzte 50 Zeilen
journalctl --user -u worx_gps_rec.service -n 50

# Live folgen
journalctl --user -u worx_gps_rec.service -f
# Stoppen: Ctrl+C
```

**Gute Logs:**

```
Mar 17 10:25:01 raspberrypi worx_gps_rec[1234]: Erfolgreich mit MQTT Broker verbunden
Mar 17 10:25:02 raspberrypi worx_gps_rec[1234]: Recording started
Mar 17 10:25:45 raspberrypi worx_gps_rec[1234]: GPS Data: lat=51.165, lon=10.451
```

### Test 3: Daten werden gespeichert?

```bash
# Datei Größe
ls -lah ~/Worx_GPS/data/

# Output sollte zeigen:
# -rw-r--r-- ... maehvorgang_2026-03-17_10.json (1.2M)
# -rw-r--r-- ... problemzonen.json (4.5K)

# Letzte Daten sehen
tail ~/Worx_GPS/data/maehvorgang_*.json | head -20
```

### Test 4: MQTT Verbindung prüfen

```bash
# Auf anderem Terminal (nicht Pi), oder mit mosquitto_sub auf Pi:
mosquitto_sub -h 192.168.1.100 -u worx -P your_password -t "worx/#" -v

# Sollte zeigen:
# worx/gps { "lat": 51.165, "lon": 10.451, ... }
# worx/pi_status { "temperature": 45.2, "cpu": 25.5, ... }
```

### Test 5: MQTT Broker Test (von Pi aus)

```bash
# Testen ob Broker erreichbar ist
nc -zv 192.168.1.100 1883

# Sollte sagen: Connection succeeded! ✅
```

---

## 🖥️ Tägliche Überwachung

### Quick Status Check (alle 5 Sekunden)

```bash
watch -n 5 'systemctl --user status worx_gps_rec && echo "---" && ls -lh ~/Worx_GPS/data/'
```

### Detaillierte Überwachung

```bash
# 1. Systemd Status
systemctl --user status worx_gps_rec.service

# 2. Aktuelle GPS Daten
tail -1 ~/Worx_GPS/data/maehvorgang_*.json

# 3. Probleme erkannt?
cat ~/Worx_GPS/data/problemzonen.json | python3 -m json.tool

# 4. System Ressourcen
free -h          # RAM
df -h            # Disk
uptime           # Uptime
```

---

## 🚨 Fehlerbehandlung

### Symptom: "MQTT Connection Failed"

```bash
# 1. MQTT Broker erreichbar?
nc -zv 192.168.1.100 1883
# Falls nicht: Broker starten oder IP prüfen

# 2. Falsche Credentials?
# .env prüfen:
grep MQTT_ ~/.env

# 3. Firewall blockiert?
sudo ufw status
# Falls 1883 nicht erlaubt: sudo ufw allow 1883/tcp
```

### Symptom: "Service bleibt nicht aktiv"

```bash
# 1. Details sehen
journalctl --user -u worx_gps_rec.service -n 100

# 2. Manuell starten zum Debuggen
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py

# 3. Hat Fehler? Trace zeigen lassen
python3 -u Worx_GPS_Rec.py 2>&1 | head -50
```

### Symptom: "Keine neuen Daten"

```bash
# 1. Rasenmäher sendet Daten?
mosquitto_sub -h 192.168.1.100 -t "worx/gps" -C 5

# 2. GPS Handler lädt Daten?
grep "GPS Data:" <(journalctl --user -u worx_gps_rec.service -n 50)

# 3. Disk voll?
df -h
# Falls < 500MB: Alte Daten löschen
# rm ~/Worx_GPS/data/maehvorgang_2026-01-*.json
```

### Symptom: "Pi wird heiß"

```bash
# CPU Nutzung
top -b -n 1 | head -10

# Temperatur
vcgencmd measure_temp

# Falls zu hoch (>80C):
# - Kühler anbringen
# - Andere Services stoppen
# - Pi neu starten
sudo reboot
```

---

## 📊 Systemd Service Management

### Service starten/stoppen

```bash
# Starten
systemctl --user start worx_gps_rec.service

# Stoppen
systemctl --user stop worx_gps_rec.service

# Restart
systemctl --user restart worx_gps_rec.service

# Autostart an/aus
systemctl --user enable worx_gps_rec.service
systemctl --user disable worx_gps_rec.service
```

### Logs

```bash
# Aktuelle Logs (Fortlaufend)
journalctl --user -u worx_gps_rec.service -f

# Letzten 100 Zeilen
journalctl --user -u worx_gps_rec.service -n 100

# Von heute
journalctl --user -u worx_gps_rec.service --since today

# Speichern in Datei
journalctl --user -u worx_gps_rec.service > logs.txt
```

---

## 💾 Datenverwaltung auf Pi

### Speicherplatz prüfen

```bash
# Gesamtbelegung
du -sh ~/Worx_GPS

# Pro Verzeichnis
du -sh ~/Worx_GPS/*

# Disk frei
df -h /
```

### Alte Daten löschen (wenn Platz knapp)

```bash
# Nur auf Disk archivieren
# Oder externe USB laden:
rsync -av ~/Worx_GPS/data/ /mnt/usb/backup/

# Dann alte Daten löschen
rm ~/Worx_GPS/data/maehvorgang_2026-01-*.json
```

### Backup erstellen

```bash
# Alle Daten sichern
tar czf ~/backup_$(date +%Y%m%d).tar.gz ~/Worx_GPS/data/

# Auf USB kopieren
cp ~/backup_*.tar.gz /mnt/usb/

# Überprüfung
ls -lh /mnt/usb/backup*
```

---

## 🔄 Wichtige Befehle (Spickzettel)

```bash
# SSH Verbindung
ssh nilsgollub@192.196.1.202

# Status prüfen
systemctl --user status worx_gps_rec.service

# Logs live sehen
journalctl --user -u worx_gps_rec.service -f

# Daten prüfen
ls -lh ~/Worx_GPS/data/ && tail ~/Worx_GPS/data/*.json

# Neu starten
systemctl --user restart worx_gps_rec.service

# MQTT testen
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v

# Disk prüfen
df -h /

# Temperatur sehen
vcgencmd measure_temp

# Reboot (wenn nötig)
sudo reboot
```

---

## 🌐 Web UI Optional

Falls Sie auch den Web-Server auf dem Pi laufen möchten:

```bash
# Optional: Zweiter Service für Web UI
nano ~/.config/systemd/user/worx_webui.service
```

```ini
[Unit]
Description=Worx GPS WebUI
After=network-online.target worx_gps_rec.service

[Service]
Type=simple
WorkingDirectory=/home/nilsgollub/Worx_GPS
ExecStart=/home/nilsgollub/Worx_GPS/.venv/bin/python3 -m web_ui.webui
Restart=on-failure
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable worx_webui.service
systemctl --user start worx_webui.service

# URL: http://192.196.1.202:5000
```

---

## ✅ Produktions-Checkliste

Vor Live-Nutzung überprüfen:

- [ ] SSH Verbindung funktioniert
- [ ] Python venv aktiv und Dependencies installiert
- [ ] .env Datei mit korrekten MQTT-Einstellungen
- [ ] Systemd Service erstellt und aktiv
- [ ] GPS-Daten werden empfangen (MQTT Topic prüfen)
- [ ] Daten werden lokal gespeichert
- [ ] Keine Fehlermeldungen in Logs
- [ ] Genug freier Disk-Platz (>1GB)
- [ ] Pi Temperatur ist normal (<70C)
- [ ] Service startet nach Neustarts automatisch
- [ ] Web UI erreichbar (optional)

---

## 📞 Notfall-Kontakt

Falls Probleme:

1. **Logs prüfen**: `journalctl --user -u worx_gps_rec.service -f`
2. **MQTT testen**: `mosquitto_sub -h BROKER_IP -t "worx/#"`
3. **Manuell starten**: `python3 Worx_GPS_Rec.py`
4. **System Check**: `df -h`, `free -h`, `vcgencmd measure_temp`
5. **Neustart**: `sudo reboot`

---

**Letztes Update**: 2026-03-17  
**Status**: ✅ Produktionsreif
