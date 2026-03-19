# Worx GPS Monitoring System

Dieses Projekt ermöglicht das präzise Tracking, die Analyse und die Visualisierung eines Worx Landroid Mähroboters. Es nutzt einen Raspberry Pi mit GPS-Modul im Mäher und eine zentrale Auswerte-Einheit am PC/Server.

---

## 🏗 1. System-Architektur

Das System besteht aus drei vernetzten Komponenten:

1.  **Mäher-Einheit (Raspberry Pi Zero/3/4):**
    *   Liest GPS-Daten (NMEA) via Serial/USB.
    *   Überträgt Positionen und Status via MQTT.
    *   Überwacht interne Parameter (Temperatur).
    *   Läuft als robuster Hintergrunddienst (`systemd`).

2.  **MQTT-Broker (z.B. Home Assistant / Mosquitto):**
    *   Zentraler Hub für die Echtzeit-Kommunikation.
    *   Topics: `worx/gps`, `worx/status`, `worx/control`, `worx/pi_status`.

3.  **Auswerte-Zentrale (PC / Server):**
    *   Verarbeitet eintreffende GPS-Daten.
    *   Generiert interaktive Heatmaps und Qualitätsanalysen.
    *   Stellt ein Web-Dashboard (Flask & React) bereit.

---

## 📁 2. Dateistruktur & Skripte

### Hauptkomponenten (Mäher)
*   `Worx_GPS_Rec.py`: Der Haupt-Recorder-Dienst auf dem Pi.
*   `gps_handler.py`: Modul zum Auslesen und Parsen der GPS-Hardware.
*   `mqtt_handler.py`: Verwaltet die Kommunikation mit dem Broker.

### Hauptkomponenten (Auswertung)
*   `start_services.py`: Startet Backend und UI am PC gleichzeitig.
*   `web_ui/`: Flask-Webserver und React-Frontend-Source.
*   `heatmap_generator.py`: Erstellt die visuellen Karten in `heatmaps/`.

---

## 🔌 3. Hardware-Setup (GPS-Modul)

Das System nutzt ein externes GPS-Modul (typisch: **u-blox NEO-6M/7M/8N**), das per USB oder Serial an den Pi angeschlossen ist.

### Anschluss am Pi Zero (GPIO)
*   **VCC (5V)** → Pin 4
*   **GND** → Pin 6
*   **TX (Modul)** → Pin 10 (RX/GPIO15)
*   **RX (Modul)** → Pin 8 (TX/GPIO14)

### Anschluss via USB
*   Einfach in einen USB-Port einstecken. Der Port ist meist `/dev/ttyACM0` oder `/dev/ttyUSB0`.

### Diagnose-Befehle (auf dem Pi)
*   Port prüfen: `ls -la /dev/tty*`
*   Daten live sehen: `cat /dev/ttyACM0 | head -n 10`
*   Dienst-Status: `systemctl --user status worx_gps.service`

---

## ⚙️ 4. Konfiguration (.env)

Alle Zugangsdaten und Parameter werden in einer `.env` Datei verwaltet:

```bash
MQTT_HOST=192.168.1.117
MQTT_PORT=1883
GPS_SERIAL_PORT=/dev/ttyACM0
GPS_BAUDRATE=9600
ASSIST_NOW_TOKEN=dein_ublox_token_hier
```

---

## 🗺 5. Projekt-Roadmap

### ✅ Erledigt
*   **SQLite-Migration:** Datenhaltung in `worx_gps.db` statt Flatfiles.
*   **Abdeckungsanalyse:** Automatische Grid-Berechnung der gemähten Fläche.
*   **Service Starter:** Zentrales Start-Skript für die Auswertung.

### 🚀 In Arbeit
*   **Visueller Geofencing-Editor:** Zonen direkt auf der Karte einzeichnen.
*   **Live-Position & Path Prediction:** Echtzeit-Vektoren zur Bewegungs-Vorhersage.

### 📅 Geplant
*   **Filterbare Heatmaps:** Auswahl spezifischer Zeiträume/Sessions.
*   **Wartungs-Dashboard:** Klingenwechsel-Erinnerung basierend auf GPS-Betriebsstunden.

---

## 🆘 Troubleshooting

*   **Kein GPS-Fix:** Das Modul braucht im Freien ca. 3-5 Minuten für den ersten Fix. Die LED am Modul sollte blinken.
*   **MQTT Disconnected:** WiFi-Empfang am Mäher prüfen oder Broker-IP in der `.env` abgleichen.
*   **Doppelte Prozesse:** Sicherstellen, dass der Service nur einmal (entweder systemweit ODER als User-Dienst) aktiviert ist.
