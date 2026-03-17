# GPS-Modul Hardware Setup & Fehlerbehebung

**Status**: ⚠️ Derzeit nicht angebunden (`/dev/ttyACM0` nicht gefunden)  
**Datum**: 2026-03-17

---

## 🎯 Überblick

Das **Worx_GPS System liest GPS-Daten NICHT vom Rasenmäher**, sondern von einem **am Raspberry Pi Zero angebundenen GPS-Modul** über serielle Verbindung (USB).

```
GPS-Modul (USB)
    ↓ [NMEA Daten @ 9600 baud]
Raspberry Pi Zero /dev/ttyACM0
    ↓ [pynmea2 Parser]
GpsHandler (gps_handler.py)
    ↓ [Strukturierte Daten]
Worx_GPS_Rec.py (speichert & versendet)
```

---

## 📋 Wo ist das GPS-Modul angebunden?

### **Serial Port Konfiguration**

```bash
# .env oder pi_env.txt:
GPS_SERIAL_PORT=/dev/ttyACM0      # USB-zu-Serial Adapter
GPS_BAUDRATE=9600                 # Standard NMEA Baudrate
```

### **Kabelverbindung (typisch)**

```
GPS-Modul Pins          Raspberry Pi Zero
─────────────────────────────────────────
VCC (5V)          →     Pin 4  (5V Power)
GND               →     Pin 6  (GND)
TX (Daten OUT)    →     Pin 10 (RX/GPIO15)  [wenn UART]
RX (Daten IN)     →     Pin 8  (TX/GPIO14)  [wenn UART]

ODER (wenn USB-Adapter):
USB Stecker       →     USB-Port am Raspi
```

---

## 🔍 GPS-Modul Typ erkennen

Prüfe welches Modul verbunden ist:

```bash
# 1. Alle seriellen Ports auflisten
ls -la /dev/tty*

# 2. Spezifisch nach USB suchen
ls -la /dev/ttyUSB*     # Wenn einfacher USB-seriell Adapter
ls -la /dev/ttyACM*     # Wenn modernes USB-Gerät

# 3. USB-Geräte anzeigen
lsusb

# 4. Berechtigungen prüfen (muss readable sein)
ls -la /dev/ttyACM0

# 5. Daten live lesen (wenn Modul angebunden)
cat /dev/ttyACM0        # Drücke Ctrl+C zum Beenden
```

### **Typische GPS-Module**

| Modul | Port | Baudrate | Protokoll | Anmerkungen |
|-------|------|----------|-----------|-------------|
| u-blox NEO-6 | /dev/ttyUSB0 | 9600 | NMEA | Häufig, zuverlässig |
| u-blox M8 | /dev/ttyACM0 | 38400 | NMEA + UBX | Höhere Baudrate möglich |
| Quectel L70 | /dev/ttyUSB0 | 9600 | NMEA | Günstig |
| MTK MT3339 | /dev/ttyUSB0 | 9600 | NMEA | PowerBank-Module |

**Worx_GPS erwartet: NMEA-Format @ 9600 baud**

---

## ⚙️ Schritt-für-Schritt Einrichtung

### **Schritt 1: GPS-Modul physisch anschließen**

```bash
# Mit Stromversorgung verbinden (5V + GND)
# Serial-Pins verbinden (TX/RX oder USB)
# Wartet 10 Sekunden auf Boot
```

### **Schritt 2: Port identifizieren**

```bash
# Bevor Modul angeschlossen:
ls /dev/tty* > /tmp/before.txt

# Modul anschließen...
sleep 2

# Nach Modul anschluss:
ls /dev/tty* > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt

# Output:
# < /dev/ttyACM0    ← Neuer Port!
```

### **Schritt 3: .env aktualisieren** (falls Port anders)

```bash
cd ~/Worx_GPS

# Wenn Port /dev/ttyUSB0 statt /dev/ttyACM0:
sed -i 's|GPS_SERIAL_PORT=.*|GPS_SERIAL_PORT=/dev/ttyUSB0|' pi_env.txt

# Oder manuell editieren:
nano pi_env.txt
# Ändere: GPS_SERIAL_PORT=/dev/ttyUSB0
# Speichere: Ctrl+O, Enter, Ctrl+X
```

### **Schritt 4: GPS-Daten live prüfen**

```bash
# Terminal 1: Live GPS-Daten anzeigen
cat /dev/ttyACM0 | head -20

# Solltest du sehen:
# $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
# $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
# $GPGSA,A,3,04,05,09,12,24,,,,,,,2.5,1.3,2.1*30
```

### **Schritt 5: Worx_GPS_Rec.py testen**

```bash
# Aktiviere venv
source ~/.venv/bin/activate

# Führe Recorder aus
python3 Worx_GPS_Rec.py

# Du solltest sehen:
# 2026-03-17 14:23:45,111 - INFO - [gps_handler.py:70] - Serielle Verbindung erfolgreich
# 2026-03-17 14:23:46,234 - INFO - [gps_handler.py:150] - GPS Fix: Qual=1, Sats=8
# 2026-03-17 14:23:47,456 - INFO - [data_recorder.py:45] - GPS-Daten gespeichert

# Ctrl+C zum Beenden
```

### **Schritt 6: Als Systemd Service starten** (wenn getestet)

```bash
# Als systemd service:
systemctl --user start worx_gps_rec.service

# Überwachen:
journalctl --user -u worx_gps_rec.service -f

# Sollte grün sein:
systemctl --user status worx_gps_rec.service
```

---

## 🚨 Fehlerbehandlung

### **Problem: `/dev/ttyACM0: No such file or directory`**

```
SerialException: [Errno 2] could not open port /dev/ttyACM0
```

**Ursachen & Lösungen:**

| Problem | Lösung |
|---------|--------|
| Modul nicht angebunden | Prüfe USB-Kabel und Stromversorgung |
| Falscher Port | `ls /dev/tty*` → korrekte Port in .env setzen |
| Berechtigungsfehler | `chmod 666 /dev/ttyACM0` (oder usergroup) |
| Falscher Baudrate | Modul läuft auf 38400? → GPS_BAUDRATE ändern |
| Port belegt | `lsof /dev/ttyACM0` → andere App schließen |

**Schnelle Diagnose:**

```bash
# 1. Ist das Modul sichtbar?
ls -la /dev/ttyACM0

# 2. Kann ich darauf lesen?
timeout 2 cat /dev/ttyACM0

# 3. Welcher Baudrate richtig?
#    Prüfe GPS-Modul Dokumentation
#    u-blox: 38400 Standard
#    MTK/Quectel: 9600 Standard

# 4. App sendet an Modul?
timeout 2 strace -e write cat /dev/ttyACM0 2>&1 | grep write
```

---

### **Problem: Daten ankommen aber GPS hat kein Fix**

```
qual: -1  (Verbindung hergestellt)
qual:  0  (Kein Signal)
sats:  0  (Keine Satelliten sichtbar)
```

**Lösungen:**

```bash
# 1. Modul im GPS-Fix warten (3-5 min in freiem Himmel)
#    Indikator-LED blinkt → sucht Satelliten
#    Indikator-LED steady → Fix vorhanden

# 2. Modul an bessere Position stellen
#    Outdoor oder fenster - kein Metall/Gebäude überhalb

# 3. GPS Reset durchführen (löscht Almanach)
#    Modul 30 Sekunden Stromversorgung unterbrechen

# 4. Prüfe NMEA-Daten direkt
cat /dev/ttyACM0 | grep GPGGA
# Sollte qual=1 oder höher haben (Bit 6 in GPGGA)
```

---

### **Problem: Intermittierende Verbindungsfehler**

```
ERROR: Serieller Fehler: Input/output error
ERROR: Versuche, serielle Verbindung wiederherzustellen...
```

**Ursachen:**
- USB-Kabel wackelt
- Stromversorgung zu schwach (Raspberry Pi Zero braucht min. 2A)
- Zu lange USB-Kabel (>3m → Qualitätsverlust)

**Lösungen:**

```bash
# 1. Besseres USB-Kabel verwenden (kurz, hochwertig)
# 2. Externe Stromversorgung für Modul prüfen
# 3. USB-Port mit Booster versuchen (Falls nur 1A verfügbar)

# 4. Logs überwachen um Muster zu erkennen
journalctl --user -u worx_gps_rec.service -n 100 | grep -i serial
```

---

## 📊 NMEA-Daten Verstehen

Das GPS-Modul sendet kontinuierlich NMEA-Sätze:

```
$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,...
 ├─ $GPGGA = Global Positioning System Fix Data
 ├─ 123519 = UTC Uhrzeit (12:35:19)
 ├─ 4807.038,N = Latitude (48.117°N)
 ├─ 01131.000,E = Longitude (11.516°E)
 ├─ 1 = Fix Quality (0=invalid, 1=GPS, 2=DGPS, 3=PPS...)
 ├─ 08 = Anzahl Satelliten
 ├─ 0.9 = Horizontal Dilution of Precision (HDOP)
 └─ 545.4,M = Höhe über Meeresspieg
```

**Worx_GPS parst folgende Sätze:**
- `$GPGGA` - GPS Fix Daten (Uhrzeit, Position, Qualität)
- `$GPRMC` - Recommended Minimum (Speed, Track)
- `$GPGSA` - GPS DOP und aktive Satelliten
- `$GPGSV` - Sichtbare Satelliten

**Code in gps_handler.py:**
```python
msg = pynmea2.parse(line)  # NMEA-Satz parsen
if msg.sentence_type == 'GGA':  # GPS Fix?
    lat = float(msg.lat) / 100
    lon = float(msg.lon) / 100
    qual = int(msg.gps_qual)  # 0=invalid, 1=GPS fix
    sats = int(msg.num_sats)  # Satellitenanzahl
```

---

## 🔧 Konfiguration feinabstimmen

### **.env Variablen**

```bash
# Serieller Port (prüfe mit: ls /dev/tty*)
GPS_SERIAL_PORT=/dev/ttyACM0

# Baudrate (typisch 9600, u-blox M8 evt. 38400)
GPS_BAUDRATE=9600

# Timeout für Read (Sekunden)
# Wenn Modul langsam: erhöhen auf 2-3
GPS_TIMEOUT=1

# Polling-Intervall (wie oft GPS-Daten abfragen)
GPS_POLL_INTERVAL=1  # Sekunden
```

### **u-blox Modul spezifische Settings** (falls verfügbar)

```bash
# Mit u-blox Configuration Tool möglich:
# - Message Rate anpassen (wie oft GPGGA gesendet)
# - Baudrate ändern (auf 38400 für Sparsam)
# - Ausgabeformate wählen

# Für Raspi: Standard 9600 ausreichend und zuverlässig
```

---

## 🎓 GPS-Modul Hardware Optionen

Wenn du dein Modul ersetzen möchtest:

### **Empfohlene Module (für Raspi Zero)**

| Modul | € | Vorteile | Nachteile |
|-------|---|----------|-----------|
| **u-blox NEO-6M** | 15-25 | Zuverlässig, viele breakout boards | Ältere Firmware |
| **u-blox M8N** | 25-40 | Schneller Fix, hohe Genauigkeit | Teurer |
| **MTK MT3339** | 20-35 | Günstig, populär | Weniger genau |
| **Quectel L70-R** | 30-50 | Neueste Gen, schnell | Teuer |

### **Für Worx_GPS ausreichend:**
- NEO-6M oder günstiger Clone (~€15) ist völlig OK
- MTK MT3339 auch möglich aber weniger genau
- **Wichtig: NMEA-Protokoll (alle unterstützen das)**

### **Was NICHT kaufen:**
- ❌ Nur GPS ohne UART (nur SPI/I2C)
- ❌ Ohne Antenne
- ❌ Breakout Board ohne 5V/GND Regler

---

## 📱 Live Monitoring

### **GPS-Status anzeigen während Betrieb**

```bash
# Logs live folgen
journalctl --user -u worx_gps_rec.service -f | grep GPS

# Output sieht so aus:
# 2026-03-17 14:45:23 - GPS Fix: qual=1, sats=8, lat=48.1234, lon=11.5678
# 2026-03-17 14:45:24 - GPS Fix: qual=1, sats=9, lat=48.1234, lon=11.5679
```

### **Datenarchiv prüfen**

```bash
# Sind GPS-Daten gespeichert?
ls -lah ~/Worx_GPS/data/

# Daten inspizieren
head -20 ~/Worx_GPS/data/maehvorgang_2026-03-17_14.json | jq '.positions[0]'

# Output:
# {
#   "lat": 48.1234,
#   "lon": 11.5678,
#   "timestamp": "2026-03-17T14:45:23",
#   "satellites": 8,
#   "signal_strength": 0.8
# }
```

---

## 📝 Checkliste: GPS-Modul Einrichtung

```
□ GPS-Modul angeschlossen (5V + GND + TX/RX)
□ USB-Kabel oder Serial-Kabel verbunden
□ ls /dev/tty* zeigt /dev/ttyACM0 oder /dev/ttyUSB0
□ GPS_SERIAL_PORT in .env korrekt
□ GPS_BAUDRATE in .env korrekt (meist 9600)
□ cat /dev/ttyACM0 zeigt NMEA-Daten
□ Worx_GPS_Rec.py läuft ohne Serial-Fehler
□ journalctl zeigt "GPS Fix" Messages
□ Daten werden in /data/maehvorgang_*.json gespeichert
□ Systemd Service läuft (systemctl --user status worx_gps_rec)
```

---

## 🆘 Fragen & Antworten

**F: Kann ich das GPS-Modul einfach austauschen?**  
A: Ja, solange es NMEA sendet @ 9600 oder 38400 baud über UART/Serial

**F: Brauche ich eine externe Stromversorgung für das Modul?**  
A: Raspberry Pi Zero gibt 500mA über USB. Modernes GPS-Modul: ~50mA. OK. Alte Module mit Backup-Batterie: Ggf. externe Versorgung.

**F: Kann ich GPS-Daten über MQTT vom Rasenmäher bekommen?**  
A: Nein! Nur über das Serial GPS-Modul. MQTT würde für Steuerung des Rasenmähers verwendet.

**F: Wie oft sendet das GPS-Modul Daten?**  
A: Typisch 1 Hz (1x pro Sekunde). Kann mit Config Tool auf 5 Hz erhöht werden.

**F: Was ist die Genauigkeit?**  
A: ±5-10 Meter horizontal mit GPS Fix. Genug für Rasenmäher-Tracking.

---

**Fragen? Besuche DOCUMENTATION_INDEX.md oder kontaktiere den Admin.**
