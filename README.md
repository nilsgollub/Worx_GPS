# Worx GPS Monitoring System

Dieses Projekt ermöglicht das präzise Tracking, die Analyse und die Visualisierung eines Worx Landroid Mähroboters. Es nutzt einen Raspberry Pi mit GPS-Modul im Mäher und eine zentrale Auswerte-Einheit am PC/Server.

---

## 🏗 1. System-Architektur

Das System besteht aus drei vernetzten Komponenten:

1.  **Mäher-Einheit (Raspberry Pi Zero/3/4):**
    *   Sammelt GPS-Daten (NMEA) und sendet sie via MQTT.
    *   **NEU:** Nutzt Hardware-Optimierungen (Pedestrian-Mode, AssistNow Autonomous).
    *   Läuft als Hintergrunddienst (`systemd`).

2.  **Daten-Management (WebUI / DataService am PC):**
    *   Wartet auf MQTT-Daten, filtert sie (Kalman-Filter + HDOP) und speichert sie als **einzige Quelle** in die SQLite-DB.

3.  **Auswerte-Zentrale & Visualisierung (Worx_GPS.py am PC):**
    *   Lädt Daten aus der DB und generiert Heatmaps und Qualitätsanalysen.
    *   **NEU:** Wendet eine Driftsperre bei Stillstand an für saubere Karten.

---

## 📁 2. Dateistruktur & Skripte

### Hauptkomponenten (Mäher)
*   `Worx_GPS_Rec.py`: Der Haupt-Recorder-Dienst auf dem Pi.
*   `gps_handler.py`: Modul für Hardware-Kommunikation und u-blox Konfiguration.
*   `enable_autonomous_gps.py`: Hilfsskript zur Aktivierung von AssistNow Autonomous.

### Hauptkomponenten (Auswertung)
*   `start_services.py`: Startet Backend und UI am PC gleichzeitig.
*   `Worx_GPS.py`: Haupt-Skript zur Generierung der Heatmaps aus DB-Daten.
*   `web_ui/data_service.py`: Logik für Datenempfang und Speicherung.

---

## 🔌 3. Hardware-Setup & Optimierung

Das System ist für den **u-blox NEO-7M** optimiert:
*   **Pedestrian Mode:** Optimiert für langsame Geschwindigkeiten.
*   **AssistNow Autonomous:** Der Chip berechnet seine eigenen Orbits (3 Tage voraus), kein Internet-Token für den Betrieb nötig.
*   **Elevation-Filter:** Satelliten unter 10° am Horizont werden zur Rausch-Reduzierung ignoriert.

### Diagnose-Befehle (auf dem Pi)
*   Port prüfen: `ls -la /dev/tty*`
*   Daten live sehen: `cat /dev/ttyACM0 | head -n 10`
*   Dienst-Status: `systemctl --user status worx_gps.service`

---

## ⚙️ 4. Konfiguration (.env)

Alle Zugangsdaten und Parameter werden in einer `.env` Datei verwaltet:

```bash
MQTT_HOST=homeassistant
MQTT_PORT=1883
GPS_SERIAL_PORT=/dev/ttyACM0
GPS_BAUDRATE=9600
ASSIST_NOW_ENABLED=True  # Gilt für den autonomen Modus und Online-Fallbacks
```

---

## 🗺 5. Projekt-Roadmap

### ✅ Erledigt
*   **Visueller Geofencing-Editor:** Zonen direkt auf der Karte einzeichnen (Erlaubt/Verboten).
*   **Präzise Punkt-Editierung:** Kleine Circle-Dots für maximale Übersicht, Draggable Markers und Löschen von Eckpunkten per Rechtsklick.
*   **Simulator mit Geocfence:** Simulator (Chaos-Prinzip) beachtet Geofences (Mow & Forbidden Areas) und stoppt automatisch nach 10 Minuten.
*   **Simulator UI-Steuerung:** Start/Stop und Echtzeit-Statusanzeige (Pulsierendes Badge/Overlay) direkt im Dashboard und auf der Live-Karte.
*   **Live-Position & Path Prediction:** Echtzeit-Anzeige der Position und Bewegungs-Vorhersage (Pfad-Vektor).
*   **Zweistufige Filterung:** Kombination aus schnellem Bounds-Check und präzisem Polygon-Check (Ray-Casting).
*   **Zentrale Datenhaltung:** Migration aller Flatfiles in die SQLite-DB `worx_gps.db`.
*   **GPS-Optimierung:** Kalman-Filter, HDOP-Validierung, Stillstands-Drift-Sperre (siehe [GPS_OPTIMIZATION_STRATEGY.md](GPS_OPTIMIZATION_STRATEGY.md)).
*   **Hardware-Tuning:** Aktivierung von Pedestrian-Mode und AssistNow Autonomous auf dem u-blox Modul.
*   **Architektur:** Saubere Trennung von Pi-Recorder, WebUI-DataService und Evaluierung.
*   **Home Assistant Integration:** Automatischer Autopilot-Wachhund, GPS-Tracker (`device_tracker`) und Dashboard-Integration (Map Card).
*   **Heatmap-Revolution:** Gewichtete Heatmaps für WiFi-Signalstärke und GPS-Qualität (Red-Yellow-Green Skala).

### 🚀 In Arbeit
*   **Automatisierte Exclusion:** Automatisches Ausblenden von Punkten in Verbotszonen (Teiche, Beete) in der Heatmap-Generierung.

### 📅 Geplant
*   **Wartungs-Dashboard:** Klingenwechsel-Erinnerung basierend auf GPS-Betriebsstunden.

---

## 📐 6. Geofencing System

Das System nutzt eine kombinierte Filter-Logik (`processing.py` / `utils.py`):
1.  **Mow Areas (Blau):** Der Mäher MUSS in mindestens einer dieser Zonen liegen.
2.  **Forbidden Areas (Rot):** Der Mäher darf in KEINER dieser Zonen liegen.

**Editor-Funktionen:**
*   **Polygon-Drawing:** Punkte per Klick auf der Karte setzen.
*   **Vertex-Dragging:** Jeden Punkt einer bestehenden Zone einzeln verschieben (präzise Circle-Dots).
*   **Point-Deletion:** Eckpunkte per Rechtsklick aus bestehenden Zonen entfernen.
*   **Type-Switch:** Bestehende Zonen jederzeit zwischen Erlaubt/Verboten umschalten.
*   **Echtzeit-Anwendung:** Geofences werden sofort auf den MQTT-Statusstream und die Heatmap-Generierung angewendet.

---

## 🏠 7. Home Assistant Integration

Das System lässt sich nahtlos in Home Assistant (HA) integrieren:
*   **HA-Wachhund (Autopilot):** Der Backend-Dienst pollt den Status des Landroids in HA (`lawn_mower.m`) und steuert den Recorder vollautomatisch (Start bei `mowing`, Stop bei `docked` / `rain delay`).
*   **MQTT GPS Tracker:** Sendet Position, Koordinaten, Satellitenanzahl und WiFi-dBm als `device_tracker` und `sensor` an HA.
*   **Präsenz-Check:** Ein spezieller Wachhund-Loop sorgt dafür, dass der Mäher auch im Ruhezustand auf der HA-Karte sichtbar bleibt (erzwungene Positions-Updates).

## 📊 8. Heatmaps & Signalstärke

Die Visualisierung bietet spezialisierte Karten für die Garten-Diagnose:
*   **Kumulierte Heatmap:** Zeigt die Mähdichte über alle Sessions (Wo wurde wie oft gemäht?).
*   **WiFi-Signalstärke:** Eine gewichtete Heatmap visualisiert Funklöcher (dBm-Werte von -90 bis -30).
*   **GPS-Qualität:** Zeigt die Satellitenabdeckung und HDOP-Präzision im Garten.
