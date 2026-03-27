# Worx GPS Monitor - Home Assistant Add-on
**Aktuelle Version:** 2.5.8 (Remote Management Update)

Lokales Add-on für Home Assistant OS. Bietet Echtzeit-Tracking, Heatmaps und Geofencing-Editor direkt im HA-Panel.

---

### Installation

1. Samba-Share oder SSH zum HA-Pi verbinden
2. Ordner `/addons/local/worx_gps_monitor` erstellen
3. Inhalt von `ha-addon/` dorthin kopieren
4. In HA: **Einstellungen** → **Add-ons** → **Add-on Store** → Drei-Punkte-Menü → **Nach Updates suchen**
5. **Worx GPS Monitor** installieren und starten

> **WICHTIG:** Beim Synchronisieren von Root nach `ha-addon/` niemals `robocopy /MIR` nutzen! Da `Dockerfile`, `config.yaml` und `run.sh` nur im Add-on-Ordner existieren, würden sie gelöscht. Nutze stattdessen `/E`.

---

## Konfiguration

Im Add-on-Reiter **Konfiguration** die MQTT-Daten eintragen:

| Parameter | Standard | Beschreibung |
|---|---|---|
| `mqtt_host` | `core-mosquitto` | HA-interner Broker |
| `mqtt_port` | `1883` | MQTT-Port |
| `mqtt_user` | (leer) | MQTT-Benutzer |
| `mqtt_password` | (leer) | MQTT-Passwort |
| `worx_email` | (leer) | Deine Worx Cloud Email |
| `worx_password` | (leer) | Dein Worx Cloud Passwort |
| `worx_cloud_type` | `worx` | 'worx' (EU) oder 'landroid' (US/CN) |
| `debug_logging` | `false` | Ausführliche Logs |

---

## Features

- **Ingress-UI** - Direkt im HA-Panel erreichbar ("Benutzeroberfläche öffnen")
- **Dashboard** - Mäher-Status, GPS-Qualität, Simulator-Steuerung
- **Live-Karte** - Echtzeit-Position auf Satelliten-/OSM-Layer mit Worx-Icon
- **Remote Pi Management** — Git Pull, Service Neustart, Reboot und Buffer Wipe für den Pi Zero direkt aus den Einstellungen.
- **Live Feedback** — Echtzeit-Statusmeldungen vom Pi Zero (Success/Error) als farbige Alerts in der UI.
- **Auto-Heatmaps** — 3 Karten werden nach jeder Session automatisch generiert
- **Erweiterte UI-Einstellungen** — Steuerung der GPS-Filterung (Moving Average, HDOP, Kalman Noise) sowie Hardware-Einstellungen direkt in der App.
- **Full Control** — Start, Pause, Home und Kantenschnitt direkt aus dem Dashboard
- **Zentrales Logging** — Live-Logs von WebUI und Pi mit Filterung
- **Direkt-Autopilot** — Nutzt Echtzeit-Events der Cloud (MQTT) statt Polling

---

## Autopilot

Der Autopilot nutzt die Echtzeit-MQTT-Verbindung zur Worx Cloud. Sobald der Mäher den Status auf "Mäht" oder "Startet" ändert, wird die GPS-Aufnahme auf dem Raspberry Pi automatisch gestartet.

**Voraussetzung:** Deine Worx-Zugangsdaten müssen in der Konfiguration hinterlegt sein.

| Mäher-Kategorie | Aktion | Beschreibung |
|---|---|---|
| `mowing`, `starting` | ▶️ START_REC | Aufnahme beginnt |
| `idle`, `home`, `paused` | ⏹️ STOP_REC | Aufnahme wird abgeschlossen |
| `error` | ⚠️ PROBLEM | Markierung in der Problem-Heatmap |

---

## Zentrales Logging

Das Logging-System sammelt Logs von WebUI und Pi Zero an einem Ort:

- **WebUI → Logs** Seite mit Live-Anzeige und Auto-Refresh
- **Filterung** nach Quelle (`webui`, `pi_gps_rec`) und Level (INFO, WARNING, ERROR)
- **Pi-Fehler** (GPS-Probleme, Exceptions) werden automatisch per MQTT gesendet
- **API:** `/api/logs` und `/api/logs/sources`

---

## Technische Details

### Architektur

- **Backend:** Flask (Port 5001) mit WSGI-Middleware für Ingress-Pfad-Korrektur
- **Frontend:** React SPA (Vite, `base: './'`) mit `HashRouter` für Ingress-Kompatibilität
- **API:** REST-Endpunkte unter `/api/` (live_config, status, geofences, simulator)
- **Echtzeit:** Socket.IO für Live-Updates

### Daten-Persistenz

Die Datenbank und Heatmaps werden im persistenten HA-Ordner `/data` gespeichert. Bei Add-on-Updates bleiben alle Daten erhalten.

### GPS-Processing-Pipeline

Eingehende GPS-Daten durchlaufen automatisch 5 Filterstufen:
1. HDOP-Filter (Threshold 2.5)
2. Geofence-Filter
3. Drift-Sperre bei Stillstand
4. Speed-Outlier-Erkennung
5. Kalman-Filter zur Glättung

---

## Troubleshooting

### UI lädt nicht / 404

1. **Hard Refresh:** `STRG + F5` im Browser
2. **Neu erstellen:** Nach `config.yaml`-Änderungen das Add-on **neu bauen** (nicht nur neustarten)
3. **Frontend-Build prüfen:** `frontend/dist/` muss im Add-on-Ordner vorhanden sein

### MIME-Type Error in Browser-Konsole

Die `IngressMiddleware` in `webui.py` korrigiert automatisch den `SCRIPT_NAME` basierend auf dem `X-Ingress-Path`-Header. Stelle sicher, dass die neueste `webui.py` deployed ist.

---

## Update / Redeployment

Vom Entwicklungs-PC aus:

```bash
# Frontend bauen
cd frontend && npm run build

# Dateien zum Add-on kopieren
robocopy frontend/dist ha-addon/frontend/dist /MIR
copy web_ui\webui.py ha-addon\web_ui\
copy web_ui\data_service.py ha-addon\web_ui\

# Zum HA deployen (192.168.1.155)
# WICHTIG: Nutze /E statt /MIR, um Add-on-Dateien (run.sh etc.) zu schützen!
robocopy ha-addon \\<HA-IP>\addons\worx_gps_monitor /E /XD node_modules __pycache__ /XF .env

# In HA: Add-on neu erstellen und starten
```
