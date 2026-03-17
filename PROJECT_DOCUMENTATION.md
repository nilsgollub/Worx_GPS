# 🚀 Worx_GPS - Komplette Projektdokumentation

**Version**: 1.0  
**Datum**: 2026-03-17  
**Status**: Produktionsreif ✅

---

## 📋 Inhaltsverzeichnis

1. [Projektübersicht](#projektübersicht)
2. [Architektur](#architektur)
3. [Komponenten](#komponenten)
4. [Installation & Setup](#installation--setup)
5. [Raspberry Pi Deployment](#raspberry-pi-deployment)
6. [Verwendung](#verwendung)
7. [Konfiguration](#konfiguration)
8. [Troubleshooting](#troubleshooting)
9. [API Referenz](#api-referenz)

---

## 📊 Projektübersicht

**Worx_GPS** ist ein intelligentes GPS-Tracking- und Analysesystem für **automatische Rasenmäher** (Worx/Kress).

### 🎯 Kernfunktionalität

```
ZWEI DATENQUELLEN:

1. GPS-POSITION (Hardware lokal am Raspi)
   GPS-Modul (/dev/ttyACM0)
        ↓ [NMEA @ 9600 baud]

2. MÄHER-STATUS (Software über HomeAssistant)
   HomeAssistant
        ↓ [MQTT publish]
        
   ↓ ↓ ↓
   
Raspberry Pi Zero (192.196.1.202)
   Worx_GPS_Rec.py - Datenerfassung & -speicherung
   (fusioniert GPS + Status)
        ↓ [JSON Speicherung local]
   data/*.json
        ↓ [REST APIs]
    
Web-Server (webui.py, optional)
    ↓ [REST APIs + WebSocket]
    
Web Browser (React Frontend)
    ↓ [Live Dashboards, Heatmaps, Statistiken]
```

### ✨ Hauptfunktionen

- **Live-GPS-Tracking**: Echtzeit-Position des Mäher auf interaktiver Karte
- **Heatmaps**: Visualisierung von Mähintensität und Fahrtmuster
- **Datenanalyse**: Mähgeschichte, Statistiken, Problemzonen-Erkennung
- **Web-Dashboard**: Responsive UI mit React für alle Geräte
- **Offline-Funktionalität**: Raspberry Pi arbeitet unabhängig
- **Problem-Erkennung**: Automatische Analyse kritischer Zonen

---

## 🏗️ Architektur

### 🔑 Kern-Datenquellen

Das System kombiniert **zwei unabhängige Datenquellen**:

```
1. GPS-POSITION (Lokal am Raspi)
   GPS-Modul (/dev/ttyACM0)
        ↓ [NMEA @ 9600 baud]
   gps_handler.py [pynmea2 Parser]
        ↓ [lat, lon, timestamp, sats...]
   Worx_GPS_Rec.py

2. MÄHER-STATUS (HomeAssistant über MQTT)
   HomeAssistant (z.B. 192.168.1.50)
        ↓ [MQTT publish]
   MQTT Broker (z.B. 192.168.1.100:1883)
        ↓ [Topic: worx/status, worx/error, etc.]
   mqtt_handler.py [MQTT Subscribe]
        ↓ [Mähvorgang, Fehler, Batterie...]
   Worx_GPS_Rec.py

FUSION:
   Worx_GPS_Rec.py kombiniert beide Quellen
        ↓ [Fahrtdaten + Status]
   data/*.json [Speicherung lokal]
        ↓ [REST APIs]
   Web UI / Dashboard
```

### Schichten-Modell

```
┌─────────────────────────────────────────┐
│     PRESENTATION LAYER (React)          │
│  Dashboard | Maps | Stats | Config      │
└──────────────────┬──────────────────────┘
                   │ HTTP/WebSocket
┌──────────────────┴──────────────────────┐
│   API LAYER (Flask + SocketIO)          │
│  /api/status | /api/stats | /api/maps   │
│  webui.py | live_gps_map_server.py      │
└──────────────────┬──────────────────────┘
                   │ In-Process / Events
┌──────────────────┴──────────────────────┐
│    SERVICE LAYER (Python Services)      │
│ MqttService | DataService | StatusMgr   │
└──────────────────┬──────────────────────┘
                   │ Module Imports
┌──────────────────┴──────────────────────┐
│   BUSINESS LOGIC LAYER                  │
│ GPS Handler | Data Recorder | Problem   │
│ Detector | Heatmap Generator            │
└──────────────────┬──────────────────────┘
                   │ File I/O / MQTT
┌──────────────────┴──────────────────────┐
│       DATA & COMMUNICATION               │
│ JSON Files | MQTT Broker | GPS Module   │
└─────────────────────────────────────────┘
```

### Deployment-Topologie

```
┌──────────────────────────────────────────────────────────────┐
│                    EXTERNE DATENQUELLEN                       │
│                                                                │
│  HomeAssistant          GPS-Modul         MQTT Broker         │
│  192.168.1.50           (am Raspi)        192.168.1.100:1883  │
│  • Mähvorgang          USB /dev/ttyACM0   Message Bus         │
│  • Fehler              NMEA @ 9600Hz      (optional remote)   │
│  • Batterie %                                                  │
│  • Status                                                      │
└─────────┬──────────────────┬──────────────────┬────────────────┘
          │                  │                  │
          │ MQTT publish     │ Serial read      │ MQTT subscribe
          │                  │                  │
┌─────────┴──────────────────┴──────────────────┴────────────────┐
│                    RASPBERRY PI ZERO                            │
│                    192.196.1.202                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │        Worx_GPS_Rec.py (Hauptprogramm)                │   │
│  │                                                         │   │
│  │  ├─ mqtt_handler.py       → Status empfangen           │   │
│  │  ├─ gps_handler.py        → GPS-Daten parsen          │   │
│  │  ├─ data_recorder.py      → Fahrtdaten speichern      │   │
│  │  ├─ problem_detector.py   → Anomalien erkennen        │   │
│  │  └─ system_monitor.py     → Pi-Status überwachen      │   │
│  │                                                         │   │
│  └────────────┬────────────────────────────────────────┘   │
│               │ JSON Files                                  │
│               ↓                                             │
│  ~/Worx_GPS/data/                                          │
│  ├─ maehvorgang_YYYY-MM-DD_HH.json                        │
│  ├─ problemzonen.json                                     │
│  └─ (wachsendes Archiv)                                   │
│               │ REST API                                   │
│               ↓                                             │
│  webui.py (optional auf Raspi)                            │
│  Port 5000: REST APIs                                     │
│  Port 5001: WebSocket (live GPS)                          │
└────────────────────────────────────────┬───────────────────┘
                                          │ HTTP/WebSocket
                                          ↓
                            ┌──────────────────────┐
                            │   Web Browser        │
                            │                      │
                            │ • Live Maps (Folium) │
                            │ • Heatmaps          │
                            │ • Statistiken       │
                            │ • Fehleranalyse     │
                            └──────────────────────┘
```
│   Raspberry Pi / Jetson    │
├────────────────────────────┤
│ • Worx_GPS_Rec.py         │
│ • webui.py (Flask)         │
│ • live_gps_map_server.py   │
│ • React Frontend (dist)    │
│ • MQTT Broker (optional)   │
└────────────────────────────┘
```

---

## 🔧 Komponenten

### 1. **Raspberry Pi Zero - Datenerfassung** ⚙️

#### Worx_GPS_Rec.py (Hauptprogramm)

```python
Funktion: Datenerfassung und -verarbeitung
Läuft: 24/7 auf Raspberry Pi
Eingaben: 
  - GPS Daten vom Rasenmäher (MQTT)
  - Befehle vom WebServer
Ausgaben:
  - Gespeicherte Fahrtdaten (JSON)
  - MQTT Status Messages
  - Erkannte Problemzonen
```

**Kernfunktionalität:**
- Liest GPS-Daten direkt vom GPS-Modul (`/dev/ttyACM0`)
- Empfängt Mäher-Status über MQTT (von HomeAssistant)
- Fusioniert beide Datenströme
- Speichert kombinierte Fahrtdaten lokal
- Erkennt Probleme (Blockierungen, Problembereiche)
- Sendet Temperatur & CPU-Status zurück (optional)

**Datenquellen:**

```
1. GPS-POSITION (Lokal Hardware)
   GPS-Modul (/dev/ttyACM0, NMEA-Daten)
        ↓
   gps_handler.py [pynmea2 parser]

2. MÄHER-STATUS (HomeAssistant über MQTT)
   HomeAssistant-MQTT-Publisher
        ↓ [worx/status, worx/error, etc.]
   mqtt_handler.py [MQTT Subscribe]

   ↓ ↓ ↓

   Worx_GPS_Rec.py (FUSION)
   ├─ GPS-Position
   ├─ Mähvorgang Status
   ├─ Fehlerzustände
   ├─ Batteriestand
   └─ Timestamp
        ↓
   data/maehvorgang_*.json
```

**Main Loops:**
```
┌─ GPS Reading Loop (kontinuierlich)
│  └─ Liest NMEA von /dev/ttyACM0
├─ MQTT Listener (kontinuierlich)
│  └─ Empfängt Status von HomeAssistant
├─ Data Recording Loop
│  └─ Speichert fusionierte Daten
├─ Problem Detection Loop
│  └─ Analysiert auf Anomalien
└─ Status Reporting Loop
   └─ Sendet Pi-Status alle 60s
```

**Abhängigkeiten:**
- `mqtt_handler.py` - MQTT Client (für Status vom HomeAssistant)
- `gps_handler.py` - GPS Modul Interface (lokale Serial-Verbindung)
- `data_recorder.py` - Persistente Speicherung
- `problem_detection.py` - Anomalieerkennung

#### GpsHandler (gps_handler.py)

```python
Funktion: GPS-Modul Interface & NMEA-Parser
Quelle: Direkt vom GPS-Modul (/dev/ttyACM0)
Protokoll: NMEA @ 9600 Baud
Ausgabe: Strukturierte Daten
  - latitude, longitude
  - timestamp
  - number of satellites
  - fix quality (0=invalid, 1=GPS, 2=DGPS...)
  - hdop (Horizontal Dilution of Precision)
```

**Wie es funktioniert:**
1. Serial-Verbindung zum GPS-Modul öffnen
2. NMEA-Sätze empfangen: `$GPGGA,...` `$GPRMC,...` etc.
3. Mit `pynmea2` parsen
4. Strukturierte GPS-Objekte zurückgeben

#### MqttHandler (mqtt_handler.py)

```python
Funktion: MQTT Client für HomeAssistant Kommunikation
Quelle:HomeAssistant MQTT Broker
Topics: worx/status, worx/error, worx/battery, ...
Ausgabe: Mäher-Status Daten
  - mowing status (idle/mowing/returning/charging...)
  - error codes
  - battery percentage
  - location (optional)
```

**Wie es funktioniert:**
1. Verbindung zum MQTT Broker aufbauen
2. Topics von HomeAssistant subscriben
3. Status-Updates empfangen (HomeAssistant publiziert die)
4. Daten für Worx_GPS_Rec.py zur Verfügung stellen

#### DataRecorder (data_recorder.py)

```python
Funktion: Persistente Speicherung
Format: JSON pro Fahrsession
Pfad: /data/maehvorgang_*.json
Struktur: Liste von GPS-Punkten mit Metadaten
```

#### ProblemDetector (problem_detection.py)

```python
Funktion: Anomalieerkennung
Prüft: Stillstand, Langsamfahrt, GPS-Fehler
Speichert: Problempunkte in /data/problemzonen.json
```

### 2. **Web-Server** 🌐

#### webui.py (Flask Hauptserver)

```python
Port: 5000
Funktionen:
  - React SPA Serving
  - REST API Endpoints
  - SocketIO für WebSockets
  - Konfigurationsverwaltung
```

**REST API Endpoints:**

| Endpoint | Methode | Funktion |
|----------|---------|----------|
| `/` | GET | React Frontend |
| `/api/status` | GET | Server + System Status |
| `/api/stats` | GET | Statistiken & Probleme |
| `/api/heatmaps` | GET | Verfügbare Heatmaps |
| `/api/config` | GET | Konfiguration |
| `/config/save` | POST | Config speichern |

#### live_gps_map_server.py (Echtzeit-Karten)

```python
Port: 5001
Funktion: Live GPS-Position via WebSocket
Verbindung: MQTT → SocketIO → Browser
Aktualisierung: Real-time
```

### 3. **Services Layer** (web_ui/)

#### MqttService
- Verbindung zum MQTT Broker
- Topic-Management
- Message Handling

#### DataService
- Lädt historische Daten
- Verwaltet Heatmaps
- Bereitstellung für Frontend

#### StatusManager
- Verfolgt Systemstatus
- CPU, Memory, Temperatur

#### SystemMonitor
- Überwacht Raspberry Pi Ressourcen
- psutil Integration

### 4. **Frontend** (React)

```
src/
├── pages/
│   ├── Dashboard.jsx    - Live Status
│   ├── Maps.jsx         - Heatmaps & Karten
│   ├── Stats.jsx        - Statistiken
│   └── Config.jsx       - Einstellungen
├── App.jsx
└── main.jsx
```

---

## 💻 Installation & Setup

### Voraussetzungen

```
Hardware:
  ✓ Raspberry Pi Zero W / Jet Son Nano
  ✓ 2+ GB RAM
  ✓ 16+ GB Storage
  ✓ WiFi/Ethernet Verbindung
  ✓ MQTT Broker erreichbar

Software:
  ✓ Python 3.7+
  ✓ pip3
  ✓ git
  ✓ MQTT Broker (mosquitto oder adäquat)
```

### Installation auf Raspberry Pi

```bash
# 1. Repository klonen
git clone <repo-url>
cd Worx_GPS

# 2. Python Environment einrichten
python3 -m venv .venv
source .venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Konfiguration erstellen
cp .env.example .env
nano .env  # Bearbeite MQTT_HOST, Credentials, etc.

# 5. Testen
python tests/test_servers.py -v

# 6. Starten (with systemd)
sudo cp systemd/worx_gps_rec.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable worx_gps_rec
sudo systemctl start worx_gps_rec
```

### .env Konfiguration

```bash
# MQTT Settings
MQTT_HOST=192.168.1.100
MQTT_PORT=1883
MQTT_USERNAME=worx
MQTT_PASSWORD=secure_password

# Topics
MQTT_TOPIC_GPS=worx/gps
MQTT_TOPIC_STATUS=worx/status
MQTT_TOPIC_CONTROL=worx/control

# Recorder Settings
TEST_MODE=false
HEATMAP_RADIUS=10
HEATMAP_BLUR=15

# GPS Settings
GEO_ZOOM_START=12
GEO_MAX_ZOOM=18

# Flask
FLASK_SECRET_KEY=your-secret-key-here
```

---

## 📡 Raspberry Pi Deployment

### Was sollte auf dem Pi ZWINGEND laufen?

#### ✅ **Hauptprogramm: Worx_GPS_Rec.py**

```bash
python3 Worx_GPS_Rec.py
```

**Funktion:**
- Hauptdatenerfasser
- Muss IMMER laufen
- Läuft 24/7
- Speichert GPS-Daten
- Sendet Status

**Systemd Service:**

```ini
[Unit]
Description=Worx GPS Recorder
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=nilsgollub
WorkingDirectory=/home/nilsgollub/Worx_GPS
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/nilsgollub/Worx_GPS/.venv/bin/python3 Worx_GPS_Rec.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 🔍 Überprüfung auf dem Pi

```bash
# 1. SSH Verbindung
ssh nilsgollub@192.196.1.202

# 2. Prozess prüfen
ps aux | grep Worx_GPS_Rec

# 3. Logs anschauen
journalctl -u worx_gps_rec -n 50 -f

# 4. Systemd Status
systemctl status worx_gps_rec

# 5. Daten prüfen
ls -lah data/
tail -f data/maehvorgang_*.json

# 6. MQTT prüfung
mosquitto_sub -h localhost -t "worx/#" -v
```

### Optional: Web-Server auf Pi

Falls der Server auch auf dem Pi laufen soll:

```bash
python3 -m web_ui.webui
```

**Systemd Service für Web-Server:**

```ini
[Unit]
Description=Worx GPS WebUI
After=worx_gps_rec.service network.target

[Service]
Type=simple
User=nilsgollub
WorkingDirectory=/home/nilsgollub/Worx_GPS
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/nilsgollub/Worx_GPS/.venv/bin/python3 -m web_ui.webui
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 🎮 Verwendung

### 1. Starten Sie das System

```bash
# Auf Raspberry Pi
ssh nilsgollub@192.196.1.202
systemctl start worx_gps_rec

# Prüfen
systemctl status worx_gps_rec

# Logs ansehen
journalctl -u worx_gps_rec -f
```

### 2. Öffnen Sie das Web-Dashboard

```
http://192.196.1.202:5000
```

oder auf anderem Server:
```
http://<server-ip>:5000
```

### 3. Web UI Seiten

| Seite | URL | Funktion |
|-------|-----|----------|
| Dashboard | `/dashboard` | Live Status |
| Maps | `/maps` | Heatmaps & Historische Daten |
| Statistiken | `/stats` | Analysen & Trends |
| Einstellungen | `/config` | Konfiguration |

### 4. Echtzeitdaten über WebSocket

```javascript
// Browser Console
const ws = new WebSocket('ws://192.168.1.202:5001');
ws.onmessage = (event) => {
  console.log('Position Update:', JSON.parse(event.data));
};
```

---

## ⚙️ Konfiguration

### config.py (Zentrale Konfiguration)

```python
# MQTT
MQTT_CONFIG = {
    'host': '192.168.1.100',
    'port': 1883,
    'topic_gps': 'worx/gps',
    'topic_status': 'worx/status',
}

# Recorder
REC_CONFIG = {
    'test_mode': False,
    'baudrate': 115200,
    'storage_interval': 5,  # Sekunden
}

# Geo
GEO_CONFIG = {
    'map_center': (51.1657, 10.4515),
    'initial_zoom': 12,
}

# Heatmap
HEATMAP_CONFIG = {
    'radius': 10,
    'blur': 15,
    'generate_png': False,
}
```

### Umgebungsvariablen (.env)

```bash
# Pi Spezifisch
MQTT_HOST=192.168.1.100
MQTT_PORT=1883

# Logging
DEBUG_LOGGING=false
LOG_LEVEL=INFO

# Test Modus
TEST_MODE=false

# Performance
REC_STORAGE_INTERVAL=5
```

---

## 🔴 Troubleshooting

### Problem 1: Raspberry Pi antwortet nicht

```bash
# Testen ob Pi online ist
ping 192.168.1.202

# SSH Verbindung testen
ssh -v nilsgollub@192.196.1.202

# SSH über Port 22 testen
ssh -p 22 nilsgollub@192.196.1.202
```

### Problem 2: Worx_GPS_Rec läuft nicht

```bash
# Prozess prüfen
ps aux | grep Worx_GPS_Rec

# Systemd Status
systemctl status worx_gps_rec

# Manuell starten und Fehler sehen
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py

# Logs
journalctl -u worx_gps_rec -n 100 --no-pager
```

### Problem 3: MQTT Verbindung fehlerhaft

```bash
# MQTT Broker testen
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v

# Connection prüfen
nc -zv 192.168.1.100 1883

# Logs ansehen
tail -f /var/log/mosquitto/mosquitto.log
```

### Problem 4: Keine GPS-Daten

```bash
# Daten-Datei prüfen
ls -lah /home/nilsgollub/Worx_GPS/data/

# Letzte GPS-Daten
mosquitto_sub -h 192.168.1.100 -t "worx/gps" -C 1

# Größe prüfen
du -sh /home/nilsgollub/Worx_GPS/data/
```

### Problem 5: Web UI nicht erreichbar

```bash
# Port prüfen
netstat -tlnp | grep 5000

# Flask Server manuell starten
cd ~/Worx_GPS
python3 -m web_ui.webui

# Logs
tail -f logs/webui.log
```

---

## 📡 API Referenz

### GET /api/status

```bash
curl http://192.196.1.202:5000/api/status
```

**Response:**
```json
{
  "mower": {
    "status": "mowing",
    "battery": 80,
    "position": {
      "lat": 51.1657,
      "lon": 10.4515
    }
  },
  "system": {
    "cpu": 25.5,
    "memory": 45.2,
    "temperature": 52.5
  },
  "pi": {
    "temperature": 52.5,
    "uptime": 1234567,
    "disk_usage": 75.2
  },
  "mqtt_connected": true
}
```

### GET /api/stats

```bash
curl http://192.196.1.202:5000/api/stats
```

**Response:**
```json
{
  "stats": {
    "total_area": 1000,
    "total_time": 3600,
    "coverage": 85.5,
    "average_speed": 2.5
  },
  "problem_zones": [
    {
      "lat": 51.165,
      "lon": 10.451,
      "severity": "high",
      "description": "Blockage detected"
    }
  ],
  "mow_sessions": 42
}
```

### GET /api/heatmaps

```bash
curl http://192.196.1.202:5000/api/heatmaps
```

**Response:**
```json
{
  "heatmaps": [
    {
      "id": "heatmap_aktuell",
      "name": "Current Heatmap",
      "url": "/heatmaps/heatmap_aktuell.html"
    },
    {
      "id": "heatmap_10_maehvorgang",
      "name": "Last 10 Sessions",
      "url": "/heatmaps/heatmap_10.html"
    }
  ],
  "current_heatmap": "/heatmaps/heatmap_aktuell.html"
}
```

### GET /api/config

```bash
curl http://192.196.1.202:5000/api/config
```

**Response:**
```json
{
  "config": {
    "heatmap_radius": 10,
    "heatmap_blur": 15,
    "geo_zoom_start": 12,
    "test_mode": false
  },
  "info": {
    "version": "1.0",
    "last_updated": "2026-03-17"
  }
}
```

### POST /config/save

```bash
curl -X POST \
  -d "heatmap_radius=15&heatmap_blur=20" \
  http://192.168.1.202:5000/config/save
```

---

## 📊 Dateistruktur

```
Worx_GPS/
├── Worx_GPS_Rec.py              ⭐ [PI] Hauptprogramm
├── Worx_GPS.py                      Datenverarbeiter
├── config.py                        Zentrale Konfiguration
│
├── web_ui/
│   ├── webui.py                 ⭐ [SERVER] Flask App
│   ├── mqtt_service.py
│   ├── data_service.py
│   ├── status_manager.py
│   └── system_monitor.py
│
├── handlers/
│   ├── gps_handler.py           ⭐ [PI] GPS Parser
│   ├── mqtt_handler.py          ⭐ [PI] MQTT Client
│   └── data_recorder.py         ⭐ [PI] Speicherung
│
├── analysis/
│   ├── heatmap_generator.py
│   ├── problem_detection.py     ⭐ [PI] Anomalieerkennung
│   └── processing.py
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── dist/                    (build output)
│
├── data/                        ⭐ [PI] Gespeicherte Daten
│   ├── maehvorgang_*.json
│   └── problemzonen.json
│
├── heatmaps/                    ⭐ [SERVER] Generierte Karten
│   ├── heatmap_aktuell.html
│   └── ...
│
├── tests/
│   ├── test_servers.py          ✅ 23 Tests
│   └── test_server_startup_validation.py  ✅ 6 Tests
│
├── systemd/
│   └── worx_gps_rec.service
│
├── .env                         ⭐ Umgebungsvariablen
├── requirements.txt
└── README.md
```

⭐ = Kritisch für Pi-Betrieb

---

## 🚀 Deployment Checkliste

### Vor Inbetriebnahme

- [ ] MQTT Broker ist erreichbar und läuft
- [ ] Raspberry Pi hat Stromanschluss
- [ ] WiFi/Netzwerk Verbindung vorhanden
- [ ] Python 3.7+ installiert
- [ ] Virtual Environment erstellt
- [ ] Dependencies installiert (`pip install -r requirements.txt`)
- [ ] .env Datei mit korrekten Werten erstellt
- [ ] Systemd Service konfiguriert
- [ ] Tests laufen erfolgreich (`pytest -v`)

### Nach Inbetriebnahme

- [ ] Systemd Service läuft (`systemctl status worx_gps_rec`)
- [ ] GPS-Daten werden empfangen (Check MQTT Topics)
- [ ] Daten werden gespeichert (`ls -lah data/`)
- [ ] Web UI ist erreichbar
- [ ] Heatmaps werden generiert
- [ ] Problemzonen-Erkennung aktiv

### Monitoring

```bash
# Continuous Monitoring
watch -n 5 'systemctl status worx_gps_rec && echo "---" && ls -lah data/'
```

---

## 📞 Support & Weitere Ressourcen

### Logs Ansehen

```bash
# Systemd Logs (letzten 50 Zeilen)
journalctl -u worx_gps_rec -n 50 -f

# Application Logs
tail -f /home/nilsgollub/Worx_GPS/logs/*.log

# MQTT Logs
tail -f /var/log/mosquitto/mosquitto.log
```

### Debugging

```bash
# Test-Modus starten (keine echten Daten)
TEST_MODE=true python3 Worx_GPS_Rec.py

# Verbose Logging aktivieren
DEBUG_LOGGING=true python3 Worx_GPS_Rec.py

# MQTT Topics monitoren
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v
```

### Performance Monitoring

```bash
# CPU & Memory auf dem Pi
top -b -n 1 | head -15

# Disk Usage
df -h

# Prozess Details
ps aux | grep -E 'python|worx'
```

---

## 📝 Lizenz & Credits

- **Autor**: Nils Gollub
- **Projekt**: Worx_GPS
- **Status**: Produktionsreif
- **Version**: 1.0

---

**Letztes Update**: 2026-03-17  
**Status**: ✅ Vollständig dokumentiert und getestet
