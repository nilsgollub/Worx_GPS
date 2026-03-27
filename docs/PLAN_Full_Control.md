# Worx Cloud API — Referenz

> Dokumentation der Worx Cloud Integration via `pyworxcloud`.  
> Implementierung abgeschlossen in v2.4.0 (`worx_cloud_service.py`).

---

## Architektur

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

Direkter Cloud-Zugriff (1 Hop) statt HA-Polling (4 Hops, 30s Verzögerung).

---

## API-Endpunkte (WebUI)

| Route | Methode | Beschreibung |
|-------|---------|-------------|
| `/api/mower/status` | GET | Voller Cloud-Status (Batterie, IMU, RSSI, Zeitplan) |
| `/api/mower/command` | POST | Befehle: `start`, `stop`, `home`, `pause`, `edgecut`, `restart`, `ots`, `lock`, `torque`, `raindelay`, `setzone`, `raw` |
| `/api/mower/schedule` | GET | Zeitplan abrufen |
| `/api/mower/autopilot` | POST | Autopilot ein/aus |

---

## Verfügbare Befehle

### Mäher-Steuerung
| Befehl | Beschreibung |
|--------|-------------|
| `start` | Mähen starten |
| `stop` / `home` | Zurück zur Box |
| `pause` | Pausieren |
| `edgecut` | Kantenschnitt |
| `ots(boundary, runtime)` | Einmal-Mähplan |
| `setzone(zone)` | Zone 1-4 wählen |
| `restart` | Baseboard neustarten |

### Einstellungen
| Befehl | Beschreibung |
|--------|-------------|
| `lock(state)` | Sperren/Entsperren |
| `torque(%)` | Drehmoment (-50 bis +50%) |
| `raindelay(min)` | Regenverzögerung |
| `toggle_schedule(bool)` | Zeitplan ein/aus |
| `time_extension(%)` | Zeitverlängerung (-100 bis +100%) |
| `raw(json)` | Beliebigen JSON-Befehl senden |

---

## Cloud-Payload Struktur

### `dat` — Echtzeit-Sensordaten

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `dmp` | `[pitch, roll, yaw]` | IMU-Orientierung |
| `bt.p` | int | Batterie (%) |
| `bt.t` | int | Batterie-Temperatur |
| `bt.v` | float | Batterie-Spannung |
| `bt.nr` | int | Ladezyklen |
| `rsi` | int | WiFi RSSI (dBm) |
| `ls` | int | Status-Code |
| `le` | int | Error-Code |
| `lz` | int | Aktuelle Zone |
| `st.b` | int | Laufzeit Messer (Min.) |
| `st.d` | int | Gesamtstrecke (m) |
| `st.wt` | int | Gesamtlaufzeit (Min.) |
| `rain.s` | int | Regensensor (0/1) |

### `cfg` — Konfiguration

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `sc` | dict | Zeitplan (Slots, Pause, OTS) |
| `rd` | int | Regenverzögerung |
| `tq` | int | Drehmoment (%) |
| `mz` | list | Zonen-Startpunkte |
| `modules.EA.h` | int | Schnitthöhe (mm) |

---

## Fernziel: Custom Mäher

Langzeitprojekt: Ausgedienten Worx Mäher als Plattform für custom Roboter nutzen.

- [ ] Hardware-Analyse & Reverse Engineering (Motoren, Elektronik, PWM)
- [ ] Custom Firmware mit direkter Motor-Steuerung
- [ ] Erweiterte Sensorik (Kamera, Lidar, Encoder)
- [ ] Autonome Navigation (SLAM, Pfadplanung)

**Status:** Fernziel — erst nach Ausnutzung des bestehenden Systems.

---

## Referenzen

- [pyworxcloud](https://github.com/MTrab/pyworxcloud) — Python Worx Cloud Client
- [AvaDeskApp](https://github.com/EishaV/Avalonia-Desktop-App) — Desktop-Referenz
- [Roboter-Forum](https://www.roboter-forum.com/threads/alternative-app-fuer-worx-kress-und-landxcape.67392)
