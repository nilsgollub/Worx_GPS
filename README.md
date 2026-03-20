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
*   **Zentrale Datenhaltung:** Migration aller Flatfiles in die SQLite-DB `worx_gps.db`.
*   **GPS-Optimierung:** Kalman-Filter, HDOP-Validierung, Stillstands-Drift-Sperre (siehe [GPS_OPTIMIZATION_STRATEGY.md](GPS_OPTIMIZATION_STRATEGY.md)).
*   **Hardware-Tuning:** Aktivierung von Pedestrian-Mode und AssistNow Autonomous auf dem u-blox Modul.
*   **Architektur:** Saubere Trennung von Pi-Recorder, WebUI-DataService und Evaluierung.
*   **Service Starter:** Zentrales Skript für den parallelen Start aller Dienste.

### 🚀 In Arbeit
*   **Visueller Geofencing-Editor:** Zonen direkt auf der Karte einzeichnen.
*   **Live-Position & Path Prediction:** Echtzeit-Vektoren zur Bewegungs-Vorhersage.

### 📅 Geplant
*   **Wartungs-Dashboard:** Klingenwechsel-Erinnerung basierend auf GPS-Betriebsstunden.

---

