# 🔧 Hardware-Dokumentation

> Komponenten, Verkabelung und GPS-Konfiguration des Worx GPS Monitoring Systems.

---

## Komponentenliste

Getestet auf einem **Worx Landroid M500+ (WR165E)**, kompatibel mit allen S/M/L-Modellen.

| Komponente | Empfehlung | Funktion |
|:-----------|:-----------|:---------|
| **Recheneinheit** | Raspberry Pi Zero 2 W | WLAN-Anbindung, MQTT-Client, GPS-Parsing |
| **GPS-Modul** | u-blox NEO-7M (oder M8N/M9N) | Positionserfassung via NMEA über UART |
| **Stromversorgung** | DC-DC Step-Down (12V/20V → 5V) | Anschluss an den Landroid-Akku (intern) |
| **Antenne** | Aktive Patch-Antenne | Empfang unter der Kunststoffhaube |
| **Optional** | IMU (MPU6050) | Für physisches Dead Reckoning (aktuell via Cloud-Yaw) |

---

## Verkabelung (UART)

Der GPS-Empfänger wird über die serielle Schnittstelle des Raspberry Pi angeschlossen:

| NEO-7M Pin | RPi GPIO Pin | Funktion |
|:-----------|:-------------|:---------|
| **VCC** | Pin 2 oder 4 (5V) | Stromversorgung |
| **GND** | Pin 6 (GND) | Masse |
| **TX** | GPIO 15 (RX / Pin 10) | Daten vom GPS zum Pi |
| **RX** | GPIO 14 (TX / Pin 8) | Befehle vom Pi zum GPS |

> [!IMPORTANT]
> Auf dem Raspberry Pi muss die **serielle Konsole deaktiviert**, aber die **serielle Schnittstelle aktiviert** sein:  
> `sudo raspi-config` → Interface Options → Serial Port → Login Shell: **Nein**, Hardware: **Ja**

---

## GPS-Modul Konfiguration (u-blox)

Das System konfiguriert das Modul beim Start automatisch per UBX-Befehlen (siehe `gps_handler.py`):

### Pedestrian Mode
GPS-Module sind standardmäßig für Autos optimiert. Der `Pedestrian Mode` (DynModel 3) verhindert, dass kleine Mäher-Bewegungen als Rauschen weggefiltert werden.

### GNSS-Modus (NEO-7M)
Der NEO-7M kann nicht alle Satellitensysteme gleichzeitig nutzen. Umschaltbar über die WebUI:

| Modus | Vorteile |
|-------|----------|
| **GPS + SBAS (EGNOS)** | Europäische Korrektursatelliten, hohe Präzision bei freiem Himmel |
| **GPS + GLONASS** | +6-10 zusätzliche Satelliten, stabiler bei Hindernissen (Bäume, Mauern) |

### AssistNow Autonomous (AOP)
Orbit-Vorhersage für 3 Tage → extrem schneller Fix (TTFF) nach Mähpausen, ohne Internet.

---

## Home Assistant Entitäten

Das Add-on stellt via **MQTT Auto-Discovery** bereit (v2.4.0+):

| Entität | Beschreibung |
|---------|-------------|
| `lawn_mower.worx_gps_monitor` | Start/Stop/Pause/Home/EdgeCut |
| `sensor.worx_battery` | Akkustand (%) |
| `sensor.worx_status` | Aktueller Status |
| `sensor.worx_rssi` | WLAN-Stärke (dBm) |
| `sensor.worx_gps_quality` | Fix-Typ, Satellitenanzahl |
| `sensor.worx_pitch/roll/yaw` | Neigung und Ausrichtung |

Kompatibel mit der [landroid-card](https://github.com/Barma-lej/landroid-card).

---

## Diagnose (auf dem Pi)

**SSH-Zugang:**
- **IP/Host:** `192.168.1.202` (oder `pizero.local`)
- **Benutzer:** `nilsgollub`
- **Arbeitsverzeichnis:** `~/Documents/GitHub/Worx_GPS`

```bash
ls -la /dev/tty*                          # Seriellen Port prüfen
cat /dev/ttyACM0 | head -n 10            # NMEA-Daten live ansehen
systemctl status worx_gps_rec.service     # Dienst-Status prüfen
journalctl -u worx_gps_rec -f             # Live-Log ansehen
```
