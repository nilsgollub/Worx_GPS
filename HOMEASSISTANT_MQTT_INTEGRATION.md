# HomeAssistant + MQTT Integration für Worx_GPS

**Status**: Externe System Setup Dokumentation  
**Datum**: 2026-03-17

---

## 🏛️ Übersicht

**Worx_GPS** bezieht Mäher-Status-Daten aus **HomeAssistant** über **MQTT**:

```
Rasenmäher (Worx/Kress)
    ↓ [Worx Integrationen Plugin]
HomeAssistant
    ├─ Entity: worx_mower.status
    ├─ Entity: worx_mower.error_code
    ├─ Entity: worx_mower.battery_level
    └─ Entity: worx_mower.location
    ↓ [MQTT publish]
MQTT Broker (zentral)
    ├─ Topic: homeassistant/sensor/worx_status
    ├─ Topic: homeassistant/sensor/worx_error
    ├─ Topic: homeassistant/sensor/worx_battery
    └─ Topic: homeassistant/sensor/worx_location
    ↓ [Worx_GPS subscribet]
Raspberry Pi Zero
    ├─ mqtt_handler.py (empfängt die Daten)
    └─ Worx_GPS_Rec.py (speichert fusioniert mit GPS)
```

---

## 🛠️ Voraussetzungen

Damit Worx_GPS Daten von HomeAssistant bekommt:

1. **HomeAssistant muss laufen** (irgendwo im Netzwerk)
2. **Worx Integration** in HomeAssistant installiert
3. **MQTT Broker** muss aktiv sein (z.B. Mosquitto)
4. **MQTT Publish enabled** in HomeAssistant

---

## 🔧 HomeAssistant Setup

### Schritt 1: MQTT Broker aktivieren (in HomeAssistant)

**HomeAssistant UI:**
```
Settings → Devices & Services → MQTT
→ Configure → Broker settings

Broker address: 192.168.1.100 (oder localhost)
Port: 1883
Username: (optional)
Password: (optional)
```

### Schritt 2: Worx Integration installieren

**HomeAssistant UI:**
```
Settings → Devices & Services → Create Automation
→ Search "Worx"
→ Install Worx Landroid/Kress Integration

[Folge Setup-Wizard für Worx-Anmeldedaten]
```

### Schritt 3: MQTT Publish aktivieren

**In HomeAssistant Automations/Scripts:**

Erstelle eine **Automation** für MQTT Publish (z.B. jede Minute):

```yaml
# configuration.yaml oder via UI
automation:
  - alias: "Worx Status to MQTT"
    trigger:
      platform: time_pattern
      minutes: "/1"  # Jede Minute
    action:
      - service: mqtt.publish
        data:
          topic: "worx/status"
          payload: "{{ states('sensor.worx_status') }}"
      - service: mqtt.publish
        data:
          topic: "worx/error"
          payload: "{{ states('sensor.worx_error_code') | default('0') }}"
      - service: mqtt.publish
        data:
          topic: "worx/battery"
          payload: "{{ states('sensor.worx_battery') | default('0') }}"
      - service: mqtt.publish
        data:
          topic: "worx/location"
          payload: "{{ state_attr('sensor.worx_location', 'latitude') }},{{ state_attr('sensor.worx_location', 'longitude') }}"
```

**Oder:** Via HomeAssistant UI (einfacher):
```
Settings → Automations & Scenes → Create Automation
→ Trigger: Time Pattern (every minute)
→ Action: MQTT Publish
→ Topic: worx/status
→ Payload: {{ states('sensor.worx_status') }}
```

---

## 📡 MQTT Topics & Format

### Topics die HomeAssistant publiziert (Worx_GPS empfängt):

| Topic | Format | Beispiel | Beschreibung |
|-------|--------|---------|-------------|
| `worx/status` | String | `mowing` / `staying` / `returning` / `charging` | Mähstatus |
| `worx/error` | Integer | `0` / `1` / `2` / `20` | Fehlerkode (0=OK) |
| `worx/battery` | Integer (%) | `75` / `100` / `45` | Batteriestand |
| `worx/location` | "lat,lon" | "48.1234,11.5678" | GPS von HomeAssistant (optional) |

### Typische Mähstatus-Werte

```
idle       = Standby (nicht im Einsatz)
mowing     = Aktives Mähen
returning  = Rückkehr zur Basis
charging   = Laden
```

### Typische Fehlerkodes

```
0  = Kein Fehler
1  = Grenze nicht definiert
2  = Mower nicht angehängt
8  = Schlinge blockiert
9  = Kantensensor-Fehler
20 = Mähmotor fehler
...
```

---

## 💾 Raspberry Pi Empfangs-Setup

### .env Konfiguration

```bash
# MQTT für Mäher-Status (von HomeAssistant)
MQTT_HOST=192.168.1.100              # Wo läuft der MQTT Broker?
MQTT_PORT=1883                        # Standard Port
MQTT_USERNAME=user                    # Falls Auth nötig
MQTT_PASSWORD=your_password           # Falls Auth nötig

# Topics zu subscriben (optional, Defaults unten)
MQTT_TOPICS_SUBSCRIBE=["worx/status", "worx/error", "worx/battery", "worx/location"]

# GPS-Modul (lokal)
GPS_SERIAL_PORT=/dev/ttyACM0
GPS_BAUDRATE=9600
```

### mqtt_handler.py Konfiguration

**Default Topics** (in Code definiert):

```python
# mqtt_handler.py
TOPICS_TO_SUBSCRIBE = {
    "worx/status": "mower_status",
    "worx/error": "error_code", 
    "worx/battery": "battery_level",
    "worx/location": "ha_location"  # Falls HomeAssistant auch GPS hat
}
```

---

## 🧪 Test: Verbindung überprüfen

### Test 1: MQTT Broker erreichbar?

```bash
# SSH zum Raspi
ssh nilsgollub@192.196.1.202

# MQTT Broker testen
nc -zv 192.168.1.100 1883
# Output: successful = Verbindung OK

# Oder mit mosquitto Tools:
mosquitto_pub -h 192.168.1.100 -t "test" -m "hello"
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v
```

### Test 2: HomeAssistant publiziert?

```bash
# Topics ansehen (live)
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v

# Sollte sehen:
# worx/status mowing
# worx/battery 85
# worx/error 0
```

### Test 3: Worx_GPS_Rec.py empfängt?

```bash
# Service starten
systemctl --user start worx_gps_rec.service

# Logs ansehen (sollte MQTT messages zeigen)
journalctl --user -u worx_gps_rec -f | grep -i mqtt

# Output sollte zeigen:
# INFO - MQTT Connected
# INFO - Status update: mowing
# INFO - Battery: 85%
```

---

## 🔍 Troubleshooting

### Problem: "MQTT connection refused"

```
ERROR: [Errno 111] Connection refused
```

**Lösungen:**
1. Broker läuft? → `systemctl status mosquitto` (am Server)
2. IP richtig? → `ping 192.168.1.100`
3. Port richtig? → `nc -zv 192.168.1.100 1883`
4. Firewall? → `sudo ufw allow 1883`

---

### Problem: Status-Updates kommen nicht an

**Checkliste:**

1. HomeAssistant läuft?
   ```bash
   curl -I http://homeassistant.local:8123
   ```

2. Worx Integration aktiv?
   - HomeAssistant UI → Settings → Devices & Services → Worx
   - Sollte grün = Connected sein

3. MQTT Publish Automation läuft?
   - HomeAssistant UI → Settings → Automations
   - "Worx Status to MQTT" sollte aktiv sein
   - Prüfe letzte Ausführung

4. Topics korrekt?
   ```bash
   mosquitto_sub -h 192.168.1.100 -t "worx/#" -v
   # Sollte sehen: worx/status mowing
   ```

5. mqtt_handler.py subscribet die richtigen Topics?
   ```bash
   grep -i "TOPICS_TO_SUBSCRIBE" gps_handler.py
   ```

---

### Problem: Falsche Daten empfangen

**Beispiel:** Status ist "mowing" aber sollte "charging" sein

1. HomeAssistant Status prüfen:
   ```
   HomeAssistant UI → Developer Tools → States
   → Suche "sensor.worx_status"
   → Was sagt HomeAssistant wirklich?
   ```

2. MQTT Topic Value prüfen:
   ```bash
   mosquitto_sub -h 192.168.1.100 -t "worx/status" -v
   # Und gleichzeitig Rasenmäher beobachten
   # Zeitverzögerung normal? (bis 1 Minute)
   ```

3. Payload Format prüfen:
   - String sollte sein: `mowing` (nicht `{"status": "mowing"}`)
   - Integer sollte sein: `85` (nicht `"85"`)

---

## 📊 Datenfluss Übersicht

```
QUELLE: HomeAssistant (externe Hardware)
└─ Empfängt von: Worx Rasenmäher (Cloud API / BLE)
   └─ Status: Mähvorgang, Fehler, Batterie, Location

TRANSPORT: MQTT Broker (zentral)
└─ Republiziert unter Topics:
   ├─ worx/status      (z.B. "mowing")
   ├─ worx/error       (z.B. "0")
   ├─ worx/battery     (z.B. "85")
   └─ worx/location    (optional)

KONSUMER: Worx_GPS (Raspberry Pi)
└─ mqtt_handler.py
   └─ Subscribet Topics
      └─ Daten speichern + kombinieren mit GPS

FUSION:
   ├─ GPS-Position (vom Modul)
   ├─ Zeitstempel
   ├─ Mähstatus (von HomeAssistant)
   ├─ Fehlerkodes
   └─ Batteriestand
   
OUTPUT:
   data/maehvorgang_YYYY-MM-DD_HH.json
```

---

## 🎓 Wichtige Punkte

### 1. **Redundanz**

Worx_GPS funktioniert **unabhängig**:

```
❌ Wenn HomeAssistant ausfällt
   → Worx_GPS läuft weiter
   → GPS-Daten sind weiterhin verfügbar
   → Nur Mäher-Status wird nicht aktualisiert

✅ Wenn Raspi ausfällt
   → GPS wird nicht getracked
   → HomeAssistant funktioniert noch normal
```

### 2. **Zeitverzögerung**

HomeAssistant → MQTT Update braucht bis zu **1 Minute**:

```
10:00:00 - Mäher startet Mähvorgang (HomeAssistant sieht sofort)
10:00:10 - HomeAssistant Automation läuft (jede Minute)
10:01:00 - MQTT publish zu "worx/status: mowing"
10:01:02 - Raspi empfängt & speichert Update
```

Das ist OK, nicht kritisch.

### 3. **Offline-Betrieb**

Wenn **nur GPS-Modul** aktiv ist (HomeAssistant offline):

```
✅ GPS-Daten: Funktioniert
   Raspi liest vom Modul

❌ Mäher-Status: Fehlt
   Worx_GPS_Rec speichert None/0 für Status
   
→ Nachher: Heatmaps zeigen "Position ohne Status"
→ Lücken in der Datenhistorie
```

---

## 🚀 Production Empfehlungen

1. **MQTT Broker in Homeassistant integrieren**
   - ✅ Einfach zu handhaben
   - ✅ Automatischer Restart mit HomeAssistant
   - ✅ Built-in Authentifizierung

2. **Regelmäßige Backup der Worx_GPS Daten**
   ```bash
   # Tägliches Backup (im Cronjob)
   tar czf /backup/worx_gps_$(date +%Y%m%d).tar.gz ~/Worx_GPS/data
   ```

3. **Monitoring**
   ```bash
   # Alert wenn MQTT Update > 5 Minuten ausfällt
   journalctl -u worx_gps_rec -S "5 minutes ago" | grep -c "MQTT"
   # Sollte >0 sein
   ```

4. **Topics dokumentieren**
   - Speichere die Topic-Liste in HomeAssistant
   - Halte sie synchron mit mqtt_handler.py

---

## 📚 Weitere Ressourcen

- **HomeAssistant Doku**: https://www.home-assistant.io/
- **MQTT Doku**: https://mqtt.org/
- **Worx Integration**: https://github.com/[worx-integration]
- **mosquitto CLI Tools**: `man mosquitto_pub`, `man mosquitto_sub`

---

**Fragen? Siehe DOCUMENTATION_INDEX.md oder kontaktiere den Admin.**
