# Plan: Full Control — Worx Cloud API Integration

## Ziel
Volle Steuerung des Worx Landroid direkt aus der WebUI, wie die AvaDeskApp (EishaV/Avalonia-Desktop-App) es bietet — aber als Web-Oberfläche im HA Add-on. **Zusätzlich: Cloud-Sensordaten zur Verbesserung der Ortungsgenauigkeit nutzen (Sensor-Fusion).**

## Hintergrund

### AvaDeskApp
- C#/.NET Desktop-App mit Avalonia UI und MQTTnet
- Verbindet sich direkt mit der **Worx Cloud API** (nicht lokaler MQTT-Broker)
- Authentifizierung über Worx-Account (Email + Passwort)
- Steuerung über Cloud-MQTT-Broker von Worx (AWS IoT)
- Unterstützt: Worx Landroid, Kress Mission, Landxcape, Ferrex
- GPL-3.0 Lizenz

### pyworxcloud (MTrab/pyworxcloud)
- **Python** PyPI-Modul — passt perfekt zu unserem Stack
- Gleiche API wie AvaDeskApp, aktiv maintained (126 Releases)
- Wird von der offiziellen HA Landroid-Integration genutzt
- Async-first (asyncio), aber sync-Kompatibilität vorhanden
- `pip install pyworxcloud`

---

## Verfügbare Befehle (via pyworxcloud)

### Mäher-Steuerung
| Methode | Beschreibung |
|---|---|
| `start(serial)` | Mähen starten |
| `home(serial)` | Zurück zur Box (Messer an) |
| `safehome(serial)` | Zurück zur Box (Messer aus) |
| `pause(serial)` | Mähen pausieren |
| `edgecut(serial)` | Kantenschnitt starten |
| `ots(serial, boundary, runtime)` | Einmal-Mähplan (mit/ohne Kante, X Min.) |
| `setzone(serial, zone)` | Zone auswählen (1-4) |
| `zonetraining(serial)` | Zonen-Training starten |
| `restart(serial)` | Baseboard neustarten |

### Einstellungen
| Methode | Beschreibung |
|---|---|
| `set_lock(serial, state)` | Gerät sperren/entsperren |
| `set_pause_mode(serial, state)` | Pause-Modus ein/aus |
| `raindelay(serial, minutes)` | Regenverzögerung setzen |
| `toggle_schedule(serial, enable)` | Zeitplan ein/aus |
| `set_time_extension(serial, %)` | Zeitplan-Verlängerung (-100 bis +100%) |
| `set_torque(serial, %)` | Rad-Drehmoment (-50 bis +50%) |
| `set_cutting_height(serial, mm)` | Schnitthöhe |
| `set_acs(serial, state)` | ACS-Modul ein/aus |
| `set_offlimits(serial, state)` | Off-Limits Modul ein/aus |
| `send(serial, json)` | Raw JSON-Befehl senden |

### Zeitplan-CRUD
| Methode | Beschreibung |
|---|---|
| `get_schedule(serial)` | Zeitplan abrufen |
| `set_schedule(serial, model)` | Zeitplan setzen |
| `add_schedule_entry(serial, entry)` | Eintrag hinzufügen |
| `update_schedule_entry(serial, id, entry)` | Eintrag ändern |
| `delete_schedule_entry(serial, id)` | Eintrag löschen |

### Zähler
| Methode | Beschreibung |
|---|---|
| `reset_blade_counter(serial)` | Messer-Zähler zurücksetzen |
| `reset_charge_cycle_counter(serial)` | Ladezyklen zurücksetzen |

### Device-Attribute (lesend)
- Batterie (Prozent, Zyklen, Temperatur, Laden)
- Messer (Betriebsstunden, Zyklen)
- GPS-Position, Orientierung
- Fehlercodes, Status, Firmware-Version
- Zonen-Konfiguration, Zeitplan
- Modul-Status (ACS, Off-Limits)
- Online/Offline, Gesperrt

---

## Architektur-Vereinfachung durch pyworxcloud

### Bisherige Architektur (VORHER)

```
┌──────────────┐  lokaler MQTT  ┌───────────────┐
│  Pi Zero     │───────────────→│ Worx_GPS.py   │
│  GPS-Rec     │ GPS + Control  │ (Heatmaps)    │
└──────┬───────┘                └───────┬───────┘
       ↑ START/STOP_REC                 │
       │                       ┌────────▼────────┐
       │ lokaler MQTT          │  webui.py        │
       └───────────────────────│  MqttService     │←── lokaler MQTT (Pi ↔ WebUI)
                               │  HA-Service      │←── HTTP Poll HA API (30s)
                               │  ha_polling_loop │←── Thread: HA → Status → MQTT
                               │  StatusManager   │←── State-String-Mapping
                               └─────────────────┘
                                        ↕
                               ┌─────────────────┐
                               │ Home Assistant   │
                               │ Supervisor API   │←── pollt Worx Cloud intern
                               │ lawn_mower.m     │
                               └─────────────────┘
```

**Problem**: 4 Hops für Mäher-Status (Worx Cloud → HA → Supervisor API → WebUI → Autopilot)
- 30 Sekunden Polling-Verzögerung
- Funktioniert NUR im HA-Container (SUPERVISOR_TOKEN)
- Keine Mäher-Steuerung möglich, nur Status lesen

### Neue Architektur (NACHHER)

```
┌──────────────┐  lokaler MQTT  ┌───────────────┐
│  Pi Zero     │───────────────→│ Worx_GPS.py   │
│  GPS-Rec     │ GPS + Control  │ (Heatmaps)    │
└──────┬───────┘                └───────┬───────┘
       ↑ START/STOP_REC                 │
       │                       ┌────────▼────────┐
       │ lokaler MQTT          │  webui.py        │
       └───────────────────────│  MqttService     │←── lokaler MQTT (Pi ↔ WebUI)
                               │  WorxCloudSvc    │←── Worx Cloud DIREKT
                               │  (pyworxcloud)   │    (Echtzeit-Events)
                               └─────────────────┘
```

**Vorteil**: 1 Hop (Worx Cloud → WebUI direkt), Echtzeit statt 30s-Polling

### Was WEGFÄLLT

| Datei/Komponente | Zeilen | Grund |
|---|---|---|
| `home_assistant_service.py` | 106 | **Komplett ersetzt** — pyworxcloud liefert Status direkt |
| `ha_polling_loop` in `webui.py` | ~60 | **Ersetzt durch Cloud-Events** — `DATA_RECEIVED` Callback |
| Status-Mapping in `status_manager.py` | ~40 | **Vereinfacht** — `device.status.id` + `.description` statt String-Matching |
| HA-Config in `run.sh` | ~10 | **Vereinfacht** — kein `HA_URL/TOKEN/ENTITY` mehr für Autopilot |
| `ha_mower_entity` in `config.yaml` | ~5 | **Vereinfacht** — durch `worx_email`/`worx_password` ersetzt |
| **Gesamt** | **~220** | **Zeilen weniger + weniger Komplexität** |

### Was BLEIBT (nicht ersetzbar)

| Komponente | Grund |
|---|---|
| **Pi Zero + `Worx_GPS_Rec.py`** | Physische u-blox GPS-Hardware, serielle Verbindung |
| **Lokaler MQTT** (Pi ↔ WebUI) | GPS-Datentransfer, Aufnahme-Steuerung |
| **`Worx_GPS.py`** (Heatmaps) | GPS-Datenverarbeitung, Kartenvisualisierung |
| **`mqtt_handler.py`** | Lokaler MQTT-Client für Pi-Kommunikation |
| **`mqtt_service.py`** | WebUI-seitiger lokaler MQTT (GPS-Empfang, Befehle an Pi) |
| **`data_service.py`** / DB | Datenpersistenz, Heatmap-Speicherung |
| **`gps_handler.py`** | u-blox GPS, NMEA-Parsing, AssistNow |
| **React Frontend** | Bleibt, wird mit MowerControl-Seite erweitert |

### Was NEU dazukommt (bisher unmöglich)

| Feature | Beschreibung |
|---|---|
| **Volle Mäher-Steuerung** | Start, Stop, Home, Pause, Edgecut direkt aus WebUI |
| **Zeitplan-Editor** | CRUD für Mäh-Zeitpläne |
| **Einstellungen** | Schnitthöhe, Torque, Regenverzögerung, Lock, ACS |
| **Live-Sensordaten** | IMU (Pitch/Roll/Yaw), Batterie, RSSI, Regensensor |
| **Echtzeit-Status** | Sofort statt 30s Verzögerung |
| **HA-unabhängig** | Funktioniert auch ohne Home Assistant |

---

## Getestete Geräte-Daten (API-Test 2025-03-22)

| Feld | Wert |
|---|---|
| Modell | **Landroid M500 (WR165E)** |
| Serial | 20223026720800657897 |
| Protocol | 0 |
| Firmware | 3.36.0+1 |
| Online | ✅ |
| GPS-Modul | ❌ (kein 4G) |
| IMU | ✅ Pitch: -1.1, Roll: 0.3, Yaw: 343.5 |
| Batterie | 85%, 17.8°C, 19.71V, lädt |
| Ladezyklen | 645 |
| WiFi RSSI | -89 dBm |
| Laufzeit | 59.632 Min (~994h) |
| Strecke | 880.623 m (~881 km) |
| Zeitplan | 14 Slots, Mi+Do 15:00-17:24 |

### Verfügbare `dat` Keys
`mac, fw, fwb, ls, le, conn, bt, dmp, st, act, rsi, lk, tr, lz, rain, modules`

### Verfügbare `cfg` Keys
`id, sn, dt, tm, lg, cmd, sc, mz, mzv, mzk, rd, al, tq, modules`

---

## Implementierungsplan

### Phase 1: Backend — WorxCloudService (ersetzt HA-Service + Autopilot)
1. **`pyworxcloud` als Dependency** in `requirements.txt` / Dockerfile hinzufügen
2. **Neuer Service `web_ui/worx_cloud_service.py`** erstellen:
   - Klasse `WorxCloudService` die `pyworxcloud.WorxCloud` kapselt
   - Eigener asyncio-Event-Loop in Daemon-Thread
   - Synchrone Wrapper für Flask-Routen
   - `DATA_RECEIVED` Event → Autopilot (ersetzt `ha_polling_loop`)
   - Device-Caching, Connection-Management
3. **Config erweitern** (`config.yaml`, `run.sh`):
   - `worx_email` — Worx-Account Email
   - `worx_password` — Worx-Account Passwort
   - `worx_cloud_type` — `worx` / `kress` / `landxcape` (Default: `worx`)
4. **Entfernen**: `home_assistant_service.py` Import + `ha_polling_loop` aus `webui.py`

### Phase 2: API-Endpunkte
5. **REST-API Endpunkte** in `webui.py` hinzufügen:
   - `GET /api/mower/status` — Voller Mäher-Status aus der Cloud
   - `POST /api/mower/command` — Befehle senden (start, stop, home, edgecut, ...)
   - `GET /api/mower/schedule` — Zeitplan abrufen
   - `POST /api/mower/schedule` — Zeitplan ändern
   - `POST /api/mower/settings` — Einstellungen ändern (torque, rain delay, etc.)
   - `GET /api/mower/statistics` — Batterie, Messer, Laufzeit Statistiken

### Phase 3: Frontend — Control Panel
6. **Neue React-Seite `MowerControl.jsx`**:
   - **Quick Actions**: Start, Stop, Home, Pause, Edgecut (große Buttons)
   - **Status-Anzeige**: Batterie, Messer, WiFi, Online/Offline, IMU
   - **Einstellungen**: Schnitthöhe, Drehmoment, Regenverzögerung (Slider/Inputs)
   - **Zeitplan-Editor**: Wochentag-Grid mit Start/Dauer/Kante
   - **Zonen-Steuerung**: Zone auswählen, Training starten
   - **One-Time-Schedule**: Einmal-Mähen mit Dauer und Kanten-Option
   - **Statistiken**: Batterie-History, Messer-Zyklen, Laufzeit
7. **Dashboard erweitern**: Quick-Control Buttons auf der Hauptseite

### Phase 4: Cleanup & Integration
8. **`home_assistant_service.py` entfernen** (Mäher-Status kommt jetzt aus Cloud)
9. **`ha_polling_loop` entfernen** (Autopilot läuft über Cloud-Events)
10. **`status_manager.py` vereinfachen** (numerische Status-Codes statt String-Matching)
11. **Fehlerbehandlung**: Offline-Mäher, Token-Ablauf, Rate-Limiting
12. **Logging**: Cloud-Events ins zentrale Logging einbinden

---

---

## Cloud-Sensordaten (Payload-Struktur)

Die Worx Cloud sendet über MQTT ein JSON-Payload mit `dat` (Echtzeit) und `cfg` (Konfiguration):

### `dat` — Echtzeit-Sensordaten

| Feld | Typ | Beschreibung |
|---|---|---|
| `dat.dmp` | `[pitch, roll, yaw]` | **Orientierung** (Neigung, Rolle, Gierwinkel) — 3-Achsen IMU |
| `dat.modules.4G.gps.coo` | `[lat, lon]` | **Cloud-GPS-Position** (vom Mäher-internen GPS) |
| `dat.bt.t` | int | Batterie-Temperatur |
| `dat.bt.v` | float | Batterie-Spannung |
| `dat.bt.p` | int | Batterie-Prozent |
| `dat.bt.c` | int | Lade-Status (0=nicht, 1=laden, 2=fehler) |
| `dat.bt.nr` | int | Ladezyklen gesamt |
| `dat.st.b` | int | Laufzeit Messer an (Minuten) |
| `dat.st.d` | int | Gesamtstrecke (Meter) |
| `dat.st.wt` | int | Gesamtlaufzeit (Minuten) |
| `dat.ls` | int | Status-Code (Mäher-Zustand) |
| `dat.le` | int | Error-Code |
| `dat.lz` | int | Aktuelle Zone |
| `dat.lk` | bool | Gesperrt |
| `dat.rsi` | int | WiFi RSSI (Signalstärke) |
| `dat.act` | int | Letzte Aktivität |
| `dat.rain.s` | int | Regensensor ausgelöst (0/1) |
| `dat.rain.cnt` | int | Regenverzögerung verbleibend (Min.) |
| `dat.tm` | string | Zeitstempel (ISO) |

### `cfg` — Konfigurationsdaten

| Feld | Typ | Beschreibung |
|---|---|---|
| `cfg.sc` | dict | Zeitplan (Slots, Pause-Modus, OTS) |
| `cfg.rd` | int | Regenverzögerung (konfiguriert) |
| `cfg.tq` | int | Drehmoment (-50 bis +50%) |
| `cfg.mz` | list | Zonen-Startpunkte (Meter) |
| `cfg.mzv` | list | Zonen-Reihenfolge |
| `cfg.modules.DF` | dict | Off-Limits Modul |
| `cfg.modules.US` | dict | ACS (Kollisionssensor) |
| `cfg.modules.EA.h` | int | Schnitthöhe (mm) |
| `cfg.tz` | string | Zeitzone |

---

## Sensor-Fusion: Cloud-Daten + Pi-GPS

### Konzept
Der Pi Zero liefert hochpräzise GPS-Daten (u-blox mit AssistNow). Die Cloud liefert zusätzlich:
- **IMU-Daten** (pitch, roll, yaw) → Bewegungsrichtung, Neigungserkennung
- **Cloud-GPS** (weniger präzise, aber als Fallback/Plausibilitätscheck)
- **Gesamtstrecke** (`dat.st.d`) → Odometrie-Vergleich
- **WiFi RSSI** → Näherungsindikator zur Basisstation

### Fusion-Strategien

1. **IMU-unterstützter Kalman-Filter**
   - Pi-GPS als primäre Quelle (hohe Genauigkeit)
   - Cloud-IMU (pitch/roll/yaw) als Bewegungsmodell im Kalman-Filter
   - Zwischen GPS-Punkten: Dead-Reckoning mit IMU-Daten interpolieren
   - Ergebnis: Glattere Tracks, weniger Drift bei GPS-Aussetzern

2. **Cloud-GPS als Plausibilitätscheck**
   - Wenn Pi-GPS und Cloud-GPS >X Meter auseinander → Pi-GPS-Punkt als Outlier markieren
   - Cloud-GPS als Fallback wenn Pi-GPS keine Fix hat

3. **Orientierungsbasierte Filterung**
   - Yaw (Gierwinkel) = Fahrtrichtung → GPS-Punkte die gegen die Fahrtrichtung liegen filtern
   - Pitch/Roll = Gelände → Stillstandserkennung verbessern

4. **RSSI-basierte Zonenerkennung**
   - WiFi-Signalstärke korreliert mit Entfernung zur Basisstation
   - Kann helfen bei "at home" vs "mowing" Erkennung

### Implementierung

```python
# Neuer Service: worx_sensor_fusion.py
class SensorFusionService:
    def __init__(self, cloud_service, gps_pipeline):
        self.cloud = cloud_service  # pyworxcloud
        self.gps = gps_pipeline     # Bestehende GPS-Pipeline

    def fused_position(self, pi_gps_point, cloud_data):
        """Kombiniert Pi-GPS mit Cloud-Sensordaten."""
        # 1. IMU-Daten extrahieren
        orientation = cloud_data.orientation  # pitch, roll, yaw

        # 2. Cloud-GPS als Referenz
        cloud_gps = cloud_data.gps  # lat, lon

        # 3. Kalman-Filter mit IMU als Bewegungsmodell
        fused = self.kalman.update(
            measurement=pi_gps_point,
            motion_model=orientation,
            reference=cloud_gps
        )
        return fused
```

## Implementation Phases

### Phase 1: Backend Wrapper (WorxCloudService) ✅ COMPLETED
**Goal:** Replace HomeAssistantService + ha_polling_loop with direct Worx Cloud integration.

#### Phase 1a: Create WorxCloudService ✅
- [x] Create `web_ui/worx_cloud_service.py` — thread-sicherer Wrapper um pyworxcloud
- [x] Async background thread for pyworxcloud (Event-Loop in Daemon-Thread)
- [x] Synchronous wrapper methods for Flask routes (start, stop, pause, home, etc.)
- [x] Event callbacks for real-time updates (LandroidEvent.DATA_RECEIVED)
- [x] Autopilot logic (START_REC/STOP_REC/PROBLEM) basierend auf Cloud-Status-Kategorien

#### Phase 1b: Dependencies ✅
- [x] Add `pyworxcloud>=6.1` to `requirements.txt`
- [ ] Update Dockerfile (HA add-on) — später

#### Phase 1c: Integration ✅
- [x] Import and instantiate WorxCloudService in `webui.py`
- [x] Replace ha_polling_loop startup mit WorxCloudService.start()
- [x] Add API routes `/api/mower/status`, `/api/mower/command`, `/api/mower/schedule`, `/api/mower/autopilot`
- [x] Wire callbacks to StatusManager (Frontend-Display) and MQTT (Autopilot-Commands)
- [x] Remove HA polling thread and HomeAssistantService usage (ersetzt durch Cloud-Events)

#### Phase 1d: Local Test ✅
- [x] WebUI lokal gestartet (localhost:5001)
- [x] `/api/mower/status` liefert vollständigen Cloud-Status (Batterie, IMU, RSSI, Statistik, Fehler, Zeitplan)
- [x] Befehle funktionieren: start → "Mäht", home → "Zurück zur Ladestation"
- [x] Echtzeit-Updates: Status ändert sich live (z.B. "Sucht Draht" → "Zurück zur Ladestation")
- [x] Autopilot aktiv: Cloud-Status-Kategorien steuern START_REC/STOP_REC/PROBLEM über MQTT

### Phase 2: Frontend MowerControl Page + Manual Control ✅ COMPLETED
**Goal:** React-Komponente für vollständige Mäher-Steuerung via Cloud-API.
- [x] React-Komponente `MowerControl.jsx`
- [x] Status-Anzeige (Batterie, IMU, RSSI, Fehler)
- [x] Steuer-Buttons (Start, Stop, Pause, Home, SafeHome, EdgeCut, Restart)
- [x] Erweiterte Controls (Lock, Torque, RainDelay, Zone, TimeExtension, OTS)
- [x] Zeitplan-Anzeige und -Bearbeitung
- [x] Autopilot-Schalter und Status-Log
- [x] Live-IMU-Visualisierung (3D-Kompass)
- [x] **Manuelle JSON-Befehle** (Expert-Modus für Protokoll-Tests)
- [x] **Befehl-Vorlagen** und Command-History
- [x] **Raw MQTT Monitor** (eingehende Payloads anzeigen)

### Phase 3: Cleanup & HA Add-on ✅ COMPLETED
**Goal:** Alten HA-Code entfernen und Add-on anpassen.
- [x] Remove `home_assistant_service.py` und `ha_polling_loop`
- [x] Simplify `status_manager.py` (numeric Cloud-Status statt HA-Text)
- [x] Update HA add-on `config.yaml` (Worx credentials)
- [x] Update HA add-on `run.sh` (export Worx env vars)
- [x] Update HA add-on `Dockerfile` (install pyworxcloud)

### Phase 4: Sensor-Fusion (optional) ✅ COMPLETED
**Goal:** Cloud-IMU mit Pi-GPS für höhere Genauigkeit.
- [x] Cloud-Daten Polling: Echtzeit `dat`-Payload über pyworxcloud Events empfangen
- [x] IMU-Daten Pipeline: Orientation-Daten in bestehende GPS-Pipeline einfügen
- [x] Erweiterter Kalman-Filter: Bestehenden Kalman um IMU-Bewegungsmodell erweitern
- [x] Cloud-GPS Fallback: Automatischer Wechsel wenn Pi-GPS ausfällt (Infrastruktur vorhanden)
- [x] Dashboard: IMU-Visualisierung (3D-Orientierung), Fusion-Qualitätsanzeige

---

## Fernziele: Custom Mäher auf Worx-Basis

### Langzeit-Projekt: Eigenbau Mäher mit Worx-Hardware
**Ziel:** Ausgedienten Worx Mäher als Plattform für voll custom Roboter nutzen.

#### Phase 1: Hardware-Analyse & Reverse Engineering
- [ ] Worx Chassis dokumentieren (Motoren, Elektronik, Sensoren)
- [ ] Firmware dumpen und analysieren
- [ ] MQTT-Protokoll vollständig reverse engineeren
- [ ] Motor-Treiber Pinouts und PWM-Steuerung finden

#### Phase 2: Custom Firmware Entwicklung
- [ ] Eigenes Firmware mit direkter Motor-Steuerung
- [ ] MQTT-Interface beibehalten für Kompatibilität
- [ ] Sicherheits-Features implementieren
- [ ] Sensor-Fusion (IMU + GPS + Encoder)

#### Phase 3: Hardware-Erweiterungen
- [ ] Zusätzliche Sensoren (Kamera, Lidar, Ultraschall)
- [ ] Bessere CPU (ESP32/Raspberry Pi)
- [ ] Erweiterte Aktoren (Klappmechanismus, Zäune)
- [ ] Autonome Navigation (SLAM, Pfadplanung)

#### Potentielle Einsparungen
| Komponente | Original | Custom | Einsparung |
|---|---|---|---|
| Chassis | 300€ | 0€ | 300€ |
| Motoren | 150€ | 0€ | 150€ |
| Elektronik | 200€ | 50€ | 150€ |
| **Gesamt** | **650€** | **50€** | **600€ |

#### Risiken und Herausforderungen
- **Firmware-Schutz**: Bootloader-Zugang finden
- **Hardware-Kompatibilität**: 24V Systeme verstehen
- **Sicherheit**: Not-Aus und Schutzfunktionen nachbauen
- **Legalität**: CE-Konformität bei Umbauten

**Status:** Fernziel — erst nach vollständiger Ausnutzung des bestehenden Systems angehen.

---

## Offene Fragen
- [x] ~~Worx-Account-Daten~~: Add-on Config (`.env` / `config.yaml`)
- [x] ~~Hat dein Landroid ein 4G/GPS-Modul?~~ → **Nein** (WR165E, kein 4G). Cloud-GPS entfällt.
- [x] ~~Soll HA-Autopilot parallel laufen?~~ → **Nein**, wird komplett durch Cloud-Events ersetzt
- [x] ~~Update-Rate der Cloud-Daten: Wie oft sendet der Mäher neue `dat`-Payloads?~~ → **Testen!** (Echtzeit-Events, ca. alle 1-3s bei Statusänderungen)
- [ ] Sensor-Fusion Priorität: Nach Phase 1-4 oder parallel?

---

## Referenzen
- **AvaDeskApp**: https://github.com/EishaV/Avalonia-Desktop-App
- **pyworxcloud**: https://github.com/MTrab/pyworxcloud
- **pyworxcloud Wiki**: https://github.com/MTrab/pyworxcloud/wiki
- **Roboter-Forum Thread**: https://www.roboter-forum.com/threads/alternative-app-fuer-worx-kress-und-landxcape.67392
