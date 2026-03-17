# 🎯 Worx_GPS - Architektur Klarstellung (Update 2026-03-17)

**Status**: ✅ Architektur vollständig dokumentiert  
**Änderungsdatum**: 2026-03-17

---

## 🔑 Kernerkenntnisse

Das **Worx_GPS System** kombiniert **zwei unabhängige Datenquellen**:

### 1️⃣ GPS-Position (Lokal Hardware)

```
GPS-Modul (USB)
    ↓ [NMEA-Daten @ 9600 baud über /dev/ttyACM0]
Raspberry Pi Zero
    ↓ [gps_handler.py mit pynmea2]
Worx_GPS_Rec.py
    ↓
data/maehvorgang_*.json → Position gespeichert
```

**Charakteristiken:**
- ✅ Lokal am Raspi angeschlossen
- ✅ Arbeitet offline (wenn Raspi läuft)
- ✅ Ca. 1 Sekunde Aktualisungsrate
- ✅ ±5-10m Genauigkeit

**Hardware Typen:**
- u-blox NEO-6M / M8N
- MTK MT3339
- Quectel L70
- Andere NMEA-kompatible Module

---

### 2️⃣ Mäher-Status (über HomeAssistant + MQTT)

```
Rasenmäher (Worx/Kress) ← Hersteller Cloud/BLE
    ↓
HomeAssistant (z.B. 192.168.1.50)
    ↓ [Worx Integration]
    └─ Entities: worx_mower.status, .error, .battery
    ↓ [MQTT publish (Automation)]
MQTT Broker (zentral, z.B. 192.168.1.100:1883)
    ↓ [Topics: worx/status, worx/error, worx/battery]
Raspberry Pi Zero
    ↓ [mqtt_handler.py empfängt]
Worx_GPS_Rec.py
    ↓
data/maehvorgang_*.json → Status auch gespeichert
```

**Charakteristiken:**
- ✅ Über HomeAssistant vermittelt
- ❌ Braucht MQTT Broker Verbindung
- ⚠️ Bis zu 1 Minute Verzögerung
- ✅ Zuverlässig wenn HomeAssistant läuft

**Status-Daten:**
- Mähstatus (idle, mowing, returning, charging)
- Fehlerkodes (0=OK, X=Fehler)
- Batteriestand (%)
- Optional: Location (wenn HomeAssistant auch GPS hat)

---

## 🏗️ Komplette Architektur

```
┌────────────────────────────────────────────────────────┐
│                  EXTERNE SYSTEME                        │
├────────────────────────────────────────────────────────┤
│                                                         │
│  Rasenmäher         HomeAssistant      GPS-Modul      │
│  (Worx/Kress)       (Cloud/MQTT)       (Hardware)     │
│      │                   │                  │          │
│      └─ API ──────→ HA Integration      Serial USB ─┐  │
│                         │                  ↑         │  │
│                    MQTT Publish ─────────  │         │  │
│                         │                  │         │  │
└────────────────────────┼──────────────────┼─────────┼──┘
                         │                  │         │
                    MQTT Broker    NMEA @ 9600Hz      │
                    (zentral)                         │
                         │                            │
┌────────────────────────┼────────────────────────────┼──┐
│         RASPBERRY PI ZERO (192.168.1.202)           │  │
├────────────────────────┼────────────────────────────┼──┤
│                        │                            │  │
│        MQTT subscribe  │         Serial read        │  │
│             │          │              │             │  │
│             ↓          │              ↓             │  │
│        ┌────────────┐  │      ┌──────────────┐     │  │
│        │mqtt_handler│  │      │ gps_handler  │     │  │
│        │   (MQTT)   │  │      │   (NMEA)     │     │  │
│        └─────┬──────┘  │      └──────┬───────┘     │  │
│              │         │             │              │  │
│              └─────────┼─────────────┘              │  │
│                        │                            │  │
│                   Worx_GPS_Rec.py                   │  │
│                  (FUSION-Punkt)                     │  │
│                        │                            │  │
│    ┌───────────────────┼────────────────┐          │  │
│    │                   │                │          │  │
│    ↓                   ↓                ↓          │  │
│ DataRecorder    ProblemDetector   SystemMonitor   │  │
│    │                                  │           │  │
│    └──────────────────┬────────────────┘           │  │
│                       │                            │  │
│                       ↓                            │  │
│             data/maehvorgang_*.json                │  │
│             (Fusionierte Fahrtdaten)              │  │
│                       │                            │  │
│                       ↓                            │  │
│             Optional: webui.py                    │  │
│             (REST API + React)                    │  │
│             Port 5000 / 5001                      │  │
└────────────────────────────────────────────────────┘
                         │
                    HTTP/WebSocket
                         │
                    ┌────┴────┐
                    ↓         ↓
                 Browser  Smartphone
                (Dashboard) (App)
```

---

## 📊 Was wird gespeichert?

**Fusionierte Fahrtdaten in: `data/maehvorgang_YYYY-MM-DD_HH.json`**

```json
{
  "session_id": "2026-03-17_14:00",
  "start_time": "2026-03-17T14:00:15",
  "end_time": "2026-03-17T14:45:00",
  "positions": [
    {
      "timestamp": "2026-03-17T14:00:16",
      "latitude": 48.1234,
      "longitude": 11.5678,
      "satellites": 8,
      "hdop": 0.9,
      "fix_quality": 1,
      
      "mower_status": "mowing",           // ← Von HomeAssistant
      "mower_error": 0,                   // ← Von HomeAssistant  
      "mower_battery": 92,                // ← Von HomeAssistant
      
      "humidity": 65,
      "temperature": 22.5,
      "pressure": 1013.25
    },
    ...
  ],
  "problems": [
    {
      "timestamp": "2026-03-17T14:32:00",
      "type": "blockage",
      "location": {"lat": 48.1240, "lon": 11.5680},
      "duration_seconds": 45
    }
  ],
  "statistics": {
    "total_distance_m": 350,
    "mowing_time_seconds": 2700,
    "battery_used_percent": 8,
    "problem_zones": 2
  }
}
```

---

## 🔧 Konfiguration

### Erforderliche .env Variablen:

```bash
# GPS-MODUL (Lokal Hardware)
GPS_SERIAL_PORT=/dev/ttyACM0        # Port (überprüfen!)
GPS_BAUDRATE=9600                   # Meist 9600 (u-blox: evt 38400)
GPS_TIMEOUT=1                        # Sekunden

# MQTT (für HomeAssistant Status)
MQTT_HOST=192.168.1.100              # Broker IP/Hostname
MQTT_PORT=1883                       # Standard Port
MQTT_USERNAME=worx                   # Falls Auth nötig
MQTT_PASSWORD=your_password          # Falls Auth nötig
MQTT_TOPICS_SUBSCRIBE=["worx/status","worx/error","worx/battery"]
```

---

## ✅ Voraussetzungen für Produktion

Damit Worx_GPS **optimal funktioniert**:

### Hardware
- [x] Raspberry Pi Zero W mit Stromversorgung
- [x] GPS-Modul angebunden (`/dev/ttyACM0` sichtbar)
- [x] MQTT Broker erreichbar (network connectivity)
- [x] Python 3.7+, venv, dependencies installiert

### Software - HomeAssistant Seite
- [x] HomeAssistant läuft (irgendwo im Netzwerk)
- [x] Worx Integration installiert & konfiguriert
- [x] MQTT Broker aktiviert
- [x] Automation für "MQTT publish" erstellt (jede Minute)
- [x] Topics laufen: `worx/status`, `worx/error`, `worx/battery`

### Software - Raspi Seite
- [x] `Worx_GPS_Rec.py` läuft als systemd service
- [x] `.env` mit korrekten Ports und MQTT Settings
- [x] Disk Space > 100MB (für Journaling)
- [x] Logging aktiv (journalctl)

---

## 🧪 Test-Checkliste

```bash
# 1. GPS-Modul
ssh nilsgollub@192.168.1.202          # Passwort: JhiswenP3003!
cat /dev/ttyACM0 | head -10          # ✅ NMEA-Daten sichtbar?

# 2. MQTT Broker
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v
# ✅ Status, error, battery sichtbar?

# 3. Service läuft
systemctl --user status worx_gps_rec # ✅ active (running)?

# 4. Daten werden gespeichert
ls -lah ~/Worx_GPS/data/
# ✅ maehvorgang_*.json vorhanden?

# 5. Logs OK
journalctl --user -u worx_gps_rec -n 50
# ✅ Keine ERROR/EXCEPTION?
```

---

## 📁 Neue Dokumentationsdateien

| Datei | Inhalt | Lese-Zeit |
|-------|--------|-----------|
| **GPS_MODULE_HARDWARE_SETUP.md** | Lokale GPS-Hardware Setup, Fehlersuche | 10 min |
| **HOMEASSISTANT_MQTT_INTEGRATION.md** | HomeAssistant + MQTT Config, Tests | 15 min |
| **PROJECT_DOCUMENTATION.md** | Komplette Projekt-Übersicht (aktualisiert) | 20 min |
| **RASPBERRY_PI_DEPLOYMENT.md** | Pi Setup mit neuer Architektur | 15 min |
| **DOCUMENTATION_INDEX.md** | Navigation (aktualisiert) | 5 min |

---

## 🔄 Workflow für neue Entwickler

1. **Zuerst verstehen**: Lies `DOCUMENTATION_INDEX.md`
2. **Hardware kennenlernen**: `GPS_MODULE_HARDWARE_SETUP.md`
3. **Integration prüfen**: `HOMEASSISTANT_MQTT_INTEGRATION.md`
4. **Details**: `PROJECT_DOCUMENTATION.md`
5. **Deployment**: `RASPBERRY_PI_DEPLOYMENT.md`
6. **Quick Commands**: `QUICK_REFERENCE.md`

---

## 🎓 Wichtige Design-Entscheidungen

### 1. Warum zwei Datenquellen?

```
GPS-Modul (lokal):
  ✅ Genau & Echtzeit
  ✅ Funktioniert offline
  ✅ Unabhängig vom Rasenmäher
  ❌ Nur Position, keine Status
  
HomeAssistant (über MQTT):
  ✅ Hat komplette Rasenmäher-Daten
  ✅ Integriert mit Hersteller-Cloud
  ❌ Braucht HomeAssistant + MQTT
  ❌ Bis 1 Minute Verzögerung
  
Kombination:
  ✅ Beste Datenqualität
  ✅ Robustheit & Redundanz
  ✅ Offline wenn GPS vorhanden
```

### 2. Warum MQTT?

```
MQTT ist gewählt weil:
✅ Leicht zu HomeAssistant zu integrationieren
✅ Pub/Sub Architektur flexibel
✅ Low bandwidth (wichtig für Raspberry Pi)
✅ Asynchron - nicht blockierend
```

### 3. Warum Lokale Daten speichern?

```
Statt nur Remote Speicherung:
✅ Offline Betrieb möglich (wenn MQTT ausfällt)
✅ Histörische Daten bleiben erhalten
✅ Keine Cloud-Abhängigkeit
✅ Datenschutz (Daten bleiben lokal)
```

---

## 🚀 Nächste Schritte

1. **Überprüfe beide Datenquellen**
   ```bash
   cat /dev/ttyACM0 | head -5          # GPS OK?
   mosquitto_sub -h mqtt_host -t "worx/#" # MQTT OK?
   ```

2. **Starten & Testen**
   ```bash
   systemctl --user start worx_gps_rec
   journalctl --user -u worx_gps_rec -f
   ```

3. **Daten prüfen**
   ```bash
   ls data/
   head data/maehvorgang_*.json
   ```

---

**🎉 System ist architektur-dokumentiert und produktionsreif!**

Fragen? → DOCUMENTATION_INDEX.md
