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

## Implementierungsplan

### Phase 1: Backend — Worx Cloud Service
1. **`pyworxcloud` als Dependency** in `requirements.txt` / Dockerfile hinzufügen
2. **Neuer Service `web_ui/worx_cloud_service.py`** erstellen:
   - Klasse `WorxCloudService` die `pyworxcloud.WorxCloud` kapselt
   - Authentifizierung mit Worx-Account (Email + Passwort aus Add-on Config)
   - Async-Wrapper für alle Befehle
   - Device-Caching und Event-Handling
   - Connection-Management (reconnect, token refresh)
3. **Config erweitern** (`config.yaml`, `run.sh`):
   - `worx_email` — Worx-Account Email
   - `worx_password` — Worx-Account Passwort
   - `worx_cloud_type` — `worx` / `kress` / `landxcape` (Default: `worx`)

### Phase 2: API-Endpunkte
4. **REST-API Endpunkte** in `webui.py` hinzufügen:
   - `GET /api/mower/status` — Voller Mäher-Status aus der Cloud
   - `POST /api/mower/command` — Befehle senden (start, stop, home, edgecut, ...)
   - `GET /api/mower/schedule` — Zeitplan abrufen
   - `POST /api/mower/schedule` — Zeitplan ändern
   - `POST /api/mower/settings` — Einstellungen ändern (torque, rain delay, etc.)
   - `GET /api/mower/statistics` — Batterie, Messer, Laufzeit Statistiken

### Phase 3: Frontend — Control Panel
5. **Neue React-Seite `MowerControl.jsx`**:
   - **Quick Actions**: Start, Stop, Home, Pause, Edgecut (große Buttons)
   - **Status-Anzeige**: Batterie, Messer, WiFi, GPS, Online/Offline
   - **Einstellungen**: Schnitthöhe, Drehmoment, Regenverzögerung (Slider/Inputs)
   - **Zeitplan-Editor**: Wochentag-Grid mit Start/Dauer/Kante
   - **Zonen-Steuerung**: Zone auswählen, Training starten
   - **One-Time-Schedule**: Einmal-Mähen mit Dauer und Kanten-Option
   - **Statistiken**: Batterie-History, Messer-Zyklen, Laufzeit
6. **Dashboard erweitern**: Quick-Control Buttons auf der Hauptseite

### Phase 4: Integration & Polish
7. **Autopilot erweitern**: Cloud-Status als alternative/ergänzende Quelle zum HA-Polling
8. **Fehlerbehandlung**: Offline-Mäher, Token-Ablauf, Rate-Limiting
9. **Logging**: Cloud-Events ins zentrale Logging einbinden
10. **Sicherheit**: Worx-Credentials verschlüsselt speichern

---

## Architektur

```
┌─────────────────────────────────────────────┐
│  React Frontend (MowerControl.jsx)          │
│  Quick Actions / Schedule / Settings        │
└───────────────┬─────────────────────────────┘
                │ REST API
┌───────────────▼─────────────────────────────┐
│  Flask WebUI (webui.py)                     │
│  /api/mower/* Endpunkte                     │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│  WorxCloudService (worx_cloud_service.py)   │
│  Wrapper um pyworxcloud.WorxCloud           │
└───────────────┬─────────────────────────────┘
                │ MQTT (AWS IoT) + REST API
┌───────────────▼─────────────────────────────┐
│  Worx Cloud (api.worxlandroid.com)          │
│  Cloud-MQTT-Broker                          │
└─────────────────────────────────────────────┘
```

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

### Phase 5: Sensor-Fusion (zusätzlich zu Phase 1-4)
11. **Cloud-Daten Polling**: Echtzeit `dat`-Payload über pyworxcloud Events empfangen
12. **IMU-Daten Pipeline**: Orientation-Daten in bestehende GPS-Pipeline einfügen
13. **Erweiterter Kalman-Filter**: Bestehenden Kalman um IMU-Bewegungsmodell erweitern
14. **Cloud-GPS Fallback**: Automatischer Wechsel wenn Pi-GPS ausfällt
15. **Dashboard**: IMU-Visualisierung (3D-Orientierung), Fusion-Qualitätsanzeige

---

## Offene Fragen
- [ ] Worx-Account-Daten: Separates Login in der UI oder nur per Add-on Config?
- [ ] Soll der lokale MQTT-Autopilot parallel zur Cloud-Steuerung laufen?
- [ ] Welche Features haben Priorität? (Steuerung > Zeitplan > Statistiken > Sensor-Fusion?)
- [ ] Update-Rate der Cloud-Daten: Wie oft sendet der Mäher neue `dat`-Payloads?
- [ ] Hat dein Landroid ein 4G/GPS-Modul eingebaut? (Nicht alle Modelle haben `modules.4G.gps`)

---

## Referenzen
- **AvaDeskApp**: https://github.com/EishaV/Avalonia-Desktop-App
- **pyworxcloud**: https://github.com/MTrab/pyworxcloud
- **pyworxcloud Wiki**: https://github.com/MTrab/pyworxcloud/wiki
- **Roboter-Forum Thread**: https://www.roboter-forum.com/threads/alternative-app-fuer-worx-kress-und-landxcape.67392
