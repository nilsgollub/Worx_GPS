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

**1. Mäher-Einheit (Raspberry Pi)** — Erfasst GPS via NMEA, sendet per MQTT. Nutzt den *Pedestrian Mode* und optional *Dead Reckoning* für maximale Genauigkeit.

**2. Add-on / Backend (Flask + React)** — Empfängt GPS-Daten und integriert sich direkt mit der **Worx Cloud API** via `pyworxcloud`. Verarbeitet Daten durch eine 6-stufige Pipeline (inkl. IMU/Dead Reckoning Fusion).

**3. Frontend (React + Leaflet)** — Dashboard mit Live-Status (inkl. 3D-Orientierung), Karte mit Satellitenansicht, Zonen-Editor und voller Mäher-Fernsteuerung.
**4. Home Assistant** — Automatische Erstellung von 15 Entitäten via **MQTT Auto-Discovery** (kompatibel mit landroid-card).

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

### Hardware-Dokumentation

Eine detaillierte Übersicht aller Komponenten, Verkabelung und u-blox Einstellungen findest du in der [HARDWARE.md](docs/HARDWARE.md).

Die wichtigsten Optimierungen:
- **Pedestrian Mode** — `UBX-CFG-NAV5` DynModel 3, optimiert für <5 km/h.
- **GNSS Umschaltung** — Wahlweise **GPS+SBAS/EGNOS** (Korrekturdaten) oder **GPS+GLONASS** (mehr Satelliten).
- **Dead Reckoning** — Fusion der GPS-Position mit Orientierungsdaten (Yaw) zur Spurtreue in Kurven.
- **AssistNow Autonomous (AOP)** — Orbit-Vorhersage für schnellen Fix.
- **Elevation-Filter** — Unterdrückt Multipath-Fehler durch Horizont-Filterung (10°).

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
3. **Drift-Sperre** — Unterdrückt Zappeln bei Stillstand
4. **Speed-Outlier** — Entfernt Sprünge > 1.5 m/s
5. **Dead Reckoning** — Fusion der GPS-Geschwindigkeit mit dem aktuellen Yaw (IMU) zur Kursstabilisierung.
6. **Kalman-Filter** — Glättet den Gesamtweg basierend auf gelerntem Rauschen.

Alle Parameter (Kalman Noise, HDOP, GNSS-Mode, Dead Reckoning) lassen sich **direkt über das WebUI "Einstellungen"** anpassen und werden persistent in `/data/.env` gespeichert.

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

Die wesentlichen Processing- und Hardware-Parameter (wie Kalman Noise, HDOP Threshold, Serial Port, Baud-Rate) lassen sich **direkt über das WebUI im Tab "Einstellungen"** (unter "GPS Filterung" und "Hardware & System") komfortabel anpassen. Diese Änderungen werden automatisch in der `.env`-Datei gespeichert und beim nächsten Start übernommen.
Alternativ wird auf die Default-Werte aus der `config.py` zurückgegriffen:

```python
POST_PROCESSING_CONFIG = {
    "method": "kalman",
    "hdop_threshold": float(os.getenv("HDOP_THRESHOLD", 2.5)),
    "max_speed_mps": float(os.getenv("MAX_SPEED_MPS", 1.5)),
    "kalman_measurement_noise": float(os.getenv("KALMAN_MEASUREMENT_NOISE", 5.0)),
    "kalman_process_noise": float(os.getenv("KALMAN_PROCESS_NOISE", 0.05)),
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
1.  Samba-Share oder SSH zum HA-Pi verbinden
2.  Ordner `/addons/local/worx_gps_monitor` erstellen
3.  Inhalt von `ha-addon/` dorthin kopieren
4.  In HA: **Einstellungen** → **Add-ons** → **Add-on Store** → Drei-Punkte-Menü → **Nach Updates suchen**
5.  **Worx GPS Monitor** installieren und starten

### Features

-   **Ingress-UI** — Direkt im HA-Panel erreichbar (React SPA mit HashRouter)
-   **Live-Karte** — Echtzeit-Position auf Satellitenansicht mit Worx-Icon
-   **Zonen-Editor** — Mähzonen und Verbotszonen per Klick zeichnen
-   **Full Control** — Start, Pause, Home und Kantenschnitt direkt aus dem Dashboard.
-   **Remote Pi Management** — Git Pull, Service Neustart, Reboot und Buffer Wipe für den Pi Zero direkt aus den Einstellungen.
-   **Live Feedback** — Echtzeit-Statusmeldungen vom Pi Zero (Success/Error) als farbige Alerts in der UI.
-   **Simulator** — ChaosSimulator zum Testen (Start/Stop im Dashboard)
-   **Zentrales Logging** — Live-Logs von WebUI und Pi mit Filterung
-   **Auto-Heatmaps** — Nach jeder Session werden automatisch 3 Karten generiert:
    -   Aktueller Mähvorgang
    -   Letzte 10 Sessions
    -   Alle Sessions kumuliert
-   **Direkt-Autopilot** — Nutzt Echtzeit-Events der Worx-Cloud (MQTT), um die Aufnahme ohne Polling-Verzögerung zu steuern.
-   **Vollsteuerung** — Befehle (Start, Stop, Home, EdgeCut) und Einstellungen (Zeitplan, Torque, etc.) im Ingress-Dashboard.

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
-   **Thread-sicherer Log-Collector** mit 200 Einträgen im RAM
-   **Live-Logs** mit Auto-Refresh in der WebUI
-   **Filterung** nach Quelle (webui, pi_gps_rec) und Level (INFO, WARNING, ERROR)
-   **MQTT-Integration** für Pi-Logs (Warnings/Errors werden automatisch gesendet)
-   **Persistente Daten** in HA Add-on `/data` Verzeichnis

**Log-Quellen:**
-   **WebUI**: System-Logs, API-Aufrufe, Fehler
-   **Pi GPS Rec**: GPS-Verbindungsprobleme, NMEA-Parsing-Fehler, kritische Exceptions
-   **MQTT**: Kommunikationsfehler, Verbindungstatus

**Zugriff:**
-   WebUI → Logs Seite mit Live-Anzeige
-   API: `/api/logs` und `/api/logs/sources`
-   Auto-Refresh alle 5 Sekunden optional

---

## Geofencing

Kombinierte Filter-Logik in `processing.py` / `utils.py`:

**Wichtige Deployment-Warnung:** Beim Synchronisieren von Root nach `ha-addon/` niemals `robocopy /MIR` nutzen! Da `Dockerfile`, `config.yaml` und `run.sh` nur im Add-on-Ordner existieren, würden sie gelöscht. Nutze stattdessen `/E`.
-   **Mow Areas (Blau)** — Punkt muss in mindestens einer erlaubten Zone liegen
-   **Forbidden Areas (Rot)** — Punkt darf in keiner Verbotszone liegen

**Editor-Funktionen:** Polygon zeichnen per Klick, Vertices per Drag verschieben, Punkte per Rechtsklick löschen, Zonentyp umschalten.

---

## 📅 Status & Roadmap

**Aktuelle Version:** 2.6.0 (Remote Management Update)

Alle Kern-Features inkl. Fernsteuerung des Pi Zero sind implementiert. Details zum Changelog findest du in der [OBSERVATIONS_AND_TODO.md](docs/OBSERVATIONS_AND_TODO.md).

---

## Heatmaps

-   **Mähdichte** — Kumulierte Heatmap über alle Sessions
-   **WiFi-Signalstärke** — Funkloch-Visualisierung (dBm -90 bis -30)
-   **GPS-Qualität** — Satellitenabdeckung und HDOP im Garten
-   **Problemzonen** — Stellen wo der Mäher steckenbleibt

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
# ACHTUNG: Nutze /E statt /MIR für den ha-addon Ordner, um Dockerfile/run.sh nicht zu löschen!
robocopy . .\ha-addon\ /E /XD .git .idea .pytest_cache .venv __pycache__ data heatmaps recordings ha-addon old tests docs frontend /XF .env worx_gps.db *.log *.tmp

# Zum HA deployen (192.168.1.155)
# WICHTIG: Nutze /E statt /MIR, um Add-on-Dateien (run.sh etc.) zu schützen!
robocopy ha-addon \\<HA-IP>\addons\worx_gps_monitor /E /XD node_modules __pycache__ /XF .env

# In HA: Add-on neu erstellen und starten

### Abhängigkeiten

-   **Python 3.11+** — Flask, Paho-MQTT, Folium, Pandas, NumPy, pyserial, pynmea2
-   **Node 18+** — React, Vite, Leaflet, Bootstrap, Axios
```
