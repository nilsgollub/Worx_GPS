# Worx GPS Monitoring System

Echtzeit-Tracking, Analyse und Visualisierung eines Worx Landroid Mähroboters. Ein Raspberry Pi mit GPS-Modul im Mäher erfasst Positionsdaten, die über MQTT an eine zentrale Auswertung gesendet und als Heatmaps visualisiert werden. Das System läuft als **Home Assistant Add-on** oder standalone.

---

## System-Architektur

```
┌─────────────────────┐     MQTT      ┌──────────────────────────────┐
│  Raspberry Pi Zero  │──────────────▶│  Home Assistant Add-on       │
│  + u-blox NEO-7M    │  worx/gps     │  (Flask + React Frontend)    │
│                     │  worx/status   │                              │
│  Worx_GPS_Rec.py    │◀──────────────│  webui.py (Backend)          │
│  gps_handler.py     │  worx/imu      │  data_service.py (Pipeline)  │
│  data_recorder.py   │  worx/control  │  worx_cloud_service.py       │
└─────────────────────┘               └──────────────────────────────┘
```

**1. Mäher-Einheit (Raspberry Pi)** — Erfasst GPS via NMEA, sendet per MQTT. Nutzt den *Pedestrian Mode* für maximale Genauigkeit bei niedrigen Geschwindigkeiten.

**2. Add-on / Backend (Flask + React)** — Empfängt GPS-Daten und integriert sich direkt mit der **Worx Cloud API** via `pyworxcloud`. Verarbeitet Daten durch eine 5-stufige Pipeline (inkl. IMU Sensor-Fusion).

**3. Frontend (React + Leaflet)** — Dashboard mit Live-Status (inkl. 3D-Orientierung), Karte mit Satellitenansicht, Zonen-Editor und voller Mäher-Fernsteuerung.

---

## Projektstruktur

```
Worx_GPS/
├── Worx_GPS.py              # Standalone-Heatmap-Generierung
├── Worx_GPS_Rec.py          # GPS-Recorder (Pi-Dienst)
├── gps_handler.py           # u-blox Kommunikation & Konfiguration
├── data_recorder.py         # Aufzeichnungslogik
├── mqtt_handler.py          # MQTT-Client (Paho)
├── config.py                # Zentrale Konfiguration
├── processing.py            # GPS-Processing-Pipeline
├── heatmap_generator.py     # Folium-Heatmap-Erstellung
├── kalman_filter.py         # GPS-Kalman-Filter
├── problem_detection.py     # Problemzonen-Erkennung
├── data_manager.py          # SQLite-Datenzugriff
├── utils.py                 # Hilfsfunktionen (Geofencing, etc.)
├── requirements.txt         # Python-Abhängigkeiten
├── .env.example             # Vorlage für Umgebungsvariablen
│
├── web_ui/                  # Flask-Backend
│   ├── webui.py             # Haupt-App + API-Endpunkte
│   ├── data_service.py      # Datenempfang, Filterung, Heatmap-Trigger
│   ├── mqtt_service.py      # MQTT-Wrapper für WebUI
│   ├── status_manager.py    # Mäher-Status-Verwaltung
│   ├── simulator.py         # ChaosSimulator
│   ├── worx_cloud_service.py # Direkter Worx-Cloud Client (MQTT/Websocket)
│   └── system_monitor.py    # Pi-Systeminfo (CPU, Temp)
│
├── frontend/                # React-App (Vite + Bootstrap + Leaflet)
│   ├── src/pages/           # Dashboard, Live, ZoneEditor, Simulator, ...
│   ├── src/components/      # LiveMapWidget, etc.
│   └── dist/                # Build-Output
│
├── ha-addon/                # Home Assistant Add-on (deploy-fertig)
│   ├── Dockerfile
│   ├── config.yaml
│   ├── run.sh
│   └── ...                  # Kopien aller Backend-/Frontend-Dateien
│
├── tests/                   # Unit- und Integrationstests
├── docs/                    # Planungsdokumente & Notizen
├── old/                     # Archivierte/veraltete Skripte
└── start_services.py        # Standalone-Starter (Backend + UI)
```

---

## Hardware-Setup

Das System ist für den **u-blox NEO-7M** am Raspberry Pi optimiert:

- **Pedestrian Mode** — `UBX-CFG-NAV5` mit DynModel 3, optimiert für langsame Bewegungen (<5 km/h)
- **SBAS/EGNOS** — `UBX-CFG-SBAS` aktiviert europäische Korrektursatelliten (PRN 120-126) für ~1-2m Genauigkeit
- **AssistNow Autonomous (AOP)** — On-Chip Orbit-Vorhersage (3 Tage), kein Internet nötig
- **Elevation-Filter** — Satelliten unter 10° ignoriert (Multipath-Reduktion)

### Diagnose (auf dem Pi)

```bash
ls -la /dev/tty*                              # Port prüfen
cat /dev/ttyACM0 | head -n 10                 # NMEA-Daten live
systemctl --user status worx_gps.service      # Dienst-Status
```

---

## GPS-Processing-Pipeline

Die zentrale Funktion `process_gps_data()` in `processing.py` verarbeitet Rohdaten in 5 Stufen:

1. **HDOP-Filter** — Verwirft Punkte mit HDOP > 2.5 (schlechte Satellitengeometrie)
2. **Geofence-Filter** — Nur Punkte in erlaubten Zonen, keine in Verbotszonen
3. **Drift-Sperre** — Unterdrückt Zappeln bei Stillstand (< 0.4m Bewegung)
4. **Speed-Outlier** — Entfernt Sprünge > 1.5 m/s (unrealistisch für Mäher)
5. **Sensor-Fusion & Kalman-Filter** — Glättet den Pfad und nutzt Cloud-IMU-Daten (Yaw) zur Richtungsstabilisierung.

---

## Konfiguration

Kopiere `.env.example` nach `.env` und passe die Werte an:

```bash
MQTT_HOST=homeassistant       # MQTT-Broker (HA-Hostname oder IP)
MQTT_PORT=1883
MQTT_USER=dein_user
MQTT_PASSWORD=dein_passwort
GPS_SERIAL_PORT=/dev/ttyACM0  # Nur auf dem Pi relevant
WORX_EMAIL=dein@email.com      # Für WebUI / Add-on
WORX_PASSWORD=dein_passwort   # Für WebUI / Add-on
WORX_CLOUD_TYPE=worx          # 'worx' (EU) oder 'landroid' (US/CN)
TEST_MODE=FALSE               # TRUE = Fake-GPS für Entwicklung
```

Die Processing-Parameter werden in `config.py` unter `POST_PROCESSING_CONFIG` konfiguriert:

```python
POST_PROCESSING_CONFIG = {
    "method": "kalman",
    "hdop_threshold": 2.5,
    "max_speed_mps": 1.5,
    "kalman_measurement_noise": 5.0,
    "kalman_process_noise": 0.05,
}
```

---

## Home Assistant Add-on

### Installation

1. Samba-Share oder SSH zum HA-Pi verbinden
2. Ordner `/addons/local/worx_gps_monitor` erstellen
3. Inhalt von `ha-addon/` dorthin kopieren
4. In HA: **Einstellungen** → **Add-ons** → **Add-on Store** → Drei-Punkte-Menü → **Nach Updates suchen**
5. **Worx GPS Monitor** installieren und starten

### Features

- **Ingress-UI** — Direkt im HA-Panel erreichbar (React SPA mit HashRouter)
- **Live-Karte** — Echtzeit-Position auf Satellitenansicht mit Worx-Icon
- **Zonen-Editor** — Mähzonen und Verbotszonen per Klick zeichnen
- **Simulator** — ChaosSimulator zum Testen (Start/Stop im Dashboard)
- **Zentrales Logging** — Live-Logs von WebUI und Pi mit Filterung
- **Auto-Heatmaps** — Nach jeder Session werden automatisch 3 Karten generiert:
  - Aktueller Mähvorgang
  - Letzte 10 Sessions
  - Alle Sessions kumuliert
- **Direkt-Autopilot** — Nutzt Echtzeit-Events der Worx-Cloud (MQTT), um die Aufnahme ohne Polling-Verzögerung zu steuern.
- **Vollsteuerung** — Befehle (Start, Stop, Home, EdgeCut) und Einstellungen (Zeitplan, Torque, etc.) im Ingress-Dashboard.

### Konfiguration im Add-on

MQTT-Daten werden im Add-on-Reiter **Konfiguration** eingetragen:

```yaml
mqtt_host: "core-mosquitto"   # HA-interner Broker
mqtt_port: 1883
mqtt_user: ""
mqtt_password: ""
```

---

## 🔍 Centralized Logging

Das neue Logging-System sammelt Logs von allen Komponenten an einem Ort:

**Features:**
- **Thread-sicherer Log-Collector** mit 200 Einträgen im RAM
- **Live-Logs** mit Auto-Refresh in der WebUI
- **Filterung** nach Quelle (webui, pi_gps_rec) und Level (INFO, WARNING, ERROR)
- **MQTT-Integration** für Pi-Logs (Warnings/Errors werden automatisch gesendet)
- **Persistente Daten** in HA Add-on `/data` Verzeichnis

**Log-Quellen:**
- **WebUI**: System-Logs, API-Aufrufe, Fehler
- **Pi GPS Rec**: GPS-Verbindungsprobleme, NMEA-Parsing-Fehler, kritische Exceptions
- **MQTT**: Kommunikationsfehler, Verbindungstatus

**Zugriff:**
- WebUI → Logs Seite mit Live-Anzeige
- API: `/api/logs` und `/api/logs/sources`
- Auto-Refresh alle 5 Sekunden optional

---

## Geofencing

Kombinierte Filter-Logik in `processing.py` / `utils.py`:

- **Mow Areas (Blau)** — Punkt muss in mindestens einer erlaubten Zone liegen
- **Forbidden Areas (Rot)** — Punkt darf in keiner Verbotszone liegen

**Editor-Funktionen:** Polygon zeichnen per Klick, Vertices per Drag verschieben, Punkte per Rechtsklick löschen, Zonentyp umschalten.

---

## Heatmaps

- **Mähdichte** — Kumulierte Heatmap über alle Sessions
- **WiFi-Signalstärke** — Funkloch-Visualisierung (dBm -90 bis -30)
- **GPS-Qualität** — Satellitenabdeckung und HDOP im Garten
- **Problemzonen** — Stellen wo der Mäher steckenbleibt

---

## Entwicklung

```bash
# Backend starten (standalone)
python start_services.py

# Frontend entwickeln
cd frontend
npm install
npm run dev

# Frontend bauen
npm run build

# Zum Add-on deployen
robocopy ha-addon \\<HA-IP>\addons\worx_gps_monitor /MIR /XD node_modules __pycache__ /XF .env
```

### Abhängigkeiten

- **Python 3.11+** — Flask, Paho-MQTT, Folium, Pandas, NumPy, pyserial, pynmea2
- **Node 18+** — React, Vite, Leaflet, Bootstrap, Axios
