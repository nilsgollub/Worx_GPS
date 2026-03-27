# Hardware Documentation

Dieses Dokument beschreibt die Hardware-Komponenten und den Aufbau des Worx GPS Monitoring Systems.

## 📋 Komponentenliste

Das System ist auf einem **Worx Landroid M500+ (WR165E)** getestet, funktioniert aber mit allen Modellen der S, M und L Serie.

| Komponente | Empfehlung | Funktion |
| :--- | :--- | :--- |
| **Recheneinheit** | Raspberry Pi Zero 2 W | Hauptsteuerung, WLAN-Anbindung, MQTT-Client |
| **GPS-Modul** | u-blox NEO-7M (oder M8N/M9N) | Positionserfassung via NMEA |
| **Stromversorgung** | DC-DC Step-Down (12V/20V -> 5V) | Anschluss an den Landroid-Akku (intern) |
| **Antenne** | Aktive Patch-Antenne | Guter Empfang unter der Kunststoffhaube |
| **Zusatz (Optional)** | IMU (MPU6050) | Für noch genaueres Dead Reckoning (momentan via Cloud-Yaw) |

## 🔌 Verkabelung (Wiring)

Der GPS-Empfänger wird über die serielle Schnittstelle (UART) des Raspberry Pi angeschlossen.

| NEO-7M Pin | RPi GPIO Pin | Funktion |
| :--- | :--- | :--- |
| **VCC** | Pin 2 oder 4 (5V) | Stromversorgung |
| **GND** | Pin 6 (GND) | Masse |
| **TX** | GPIO 15 (RX / Pin 10) | Daten vom GPS zum Pi |
| **RX** | GPIO 14 (TX / Pin 8) | Befehle vom Pi zum GPS |

> [!IMPORTANT]
> Achte darauf, dass auf dem Raspberry Pi die serielle Konsole deaktiviert, aber die serielle Schnittstelle aktiviert ist (`raspi-config` -> Interface Options -> Serial Port).

## 🛰️ GPS-Modul Konfiguration (u-blox)

Das System konfiguriert das Modul beim Start automatisch mit spezifischen **UBX-Befehlen**:

### 🚶 Pedestrian Mode (Fussgänger)
Standardmäßig sind GPS-Module für Autos (High Dynamics) optimiert. Da der Mäher langsam fährt, nutzen wir den `Pedestrian Mode` (DynModel 3). Dies verhindert, dass kleine Bewegungen als Rauschen weggefiltert werden.

### 🌓 GNSS-Modus (NEO-7M Limitierung)
Der NEO-7M ist ein älteres Modul und kann nicht alle Satellitensysteme gleichzeitig nutzen. Du hast in der Web-UI die Wahl:
- **GPS + SBAS (EGNOS):** Nutzt GPS-Satelliten plus europäische Korrektursatelliten. Gut für hohe Präzision bei freiem Himmel.
- **GPS + GLONASS:** Deaktiviert SBAS, schaltet aber das russische GLONASS-System frei. Dies erhöht die Anzahl sichtbarer Satelliten um ca. 6-10, was bei Hindernissen (Bäume, Mauern) für eine stabilere Position sorgt.

### 📅 AssistNow Autonomous (AOP)
Das System aktiviert `AOP`. Dabei berechnet das Modul die Bahndaten der Satelliten für die nächsten 3 Tage im Voraus. Das sorgt für einen extrem schnellen Fix (TTFF) nach kurzen Mäh-Pausen, auch ohne Internetverbindung.

## 🏠 Home Assistant Integration

Das Add-on stellt folgende Entitäten via **MQTT Auto-Discovery** bereit (v2.2.0+):

- **lawn_mower.worx_gps_monitor**: Start/Stop/Pause/Home/EdgeCut Befehle.
- **sensor.worx_battery**: Akkustand in %.
- **sensor.worx_status**: Aktueller Status (Mowing, Charging, etc.).
- **sensor.worx_rssi**: WLAN-Stärke des Mähers.
- **sensor.worx_gps_quality**: Fix-Typ und Anzahl Satelliten.
- **sensor.worx_pitch / roll / yaw**: Neigung und Ausrichtung (aus IMU-Fusion).

Die Entitäten sind kompatibel mit der [landroid-card](https://github.com/Barma-lej/landroid-card).
