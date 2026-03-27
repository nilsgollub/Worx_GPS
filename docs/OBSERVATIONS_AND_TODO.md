# 📝 Changelog, Bekannte Fehler & Roadmap

> **Version:** 2.5.8 | **Stand:** 2026-03-27

---

## 🐛 Bekannte Fehler (Known Issues)

*(Aktuell keine kritischen Fehler bekannt)*

---

## 💡 Roadmap (Geplante Features)

  - [x] **Remote Automation:** Git Pull, Service Restart, Reboot und Buffer Wipe direkt aus der WebUI (config.html) möglich.
  - [x] **Live-Feedback:** MQTT-Bestätigungen (SUCCESS/FAILED) werden als farbige Alerts in der UI angezeigt.
  - [x] **Hardware-Sync:** GNSS-Umschaltung (SBAS/GLONASS) persistent in .env und remote wirksam.

### Statistische Langzeitanalyse (Chart)
- **Ziel:** Visualisierung der Empfangsqualität (HDOP, Satelliten) über Wochen.
- **Status:** Basis-Tabelle im Datenbank-Manager implementiert.

### Custom Mäher (Fernziel)
- Hardware-Analyse & Reverse Engineering des Worx Chassis
- Eigenes Firmware mit Motor-Steuerung und erweiterter Sensorik

---

## 🛠️ Best Practices & Deployment

### HA-Addon Sync (WICHTIG)
- **Problem:** `robocopy /MIR` löscht Dateien im Ziel, die nicht in der Quelle (Root) existieren. Da `run.sh`, `Dockerfile` und `config.yaml` nur im `ha-addon/` Ordner liegen, werden sie bei `/MIR` gelöscht.
- **Lösung:** Immer `/E` statt `/MIR` nutzen für den Sync von Root nach `ha-addon/`.
- **Korrektes Kommando:**
  `robocopy . .\ha-addon\ /E /XD .git .idea .pytest_cache .venv __pycache__ data heatmaps recordings ha-addon old tests docs frontend /XF .env worx_gps.db *.log *.tmp`

---

## ✅ Changelog (abgeschlossene Arbeiten)

### v2.5.8 (2026-03-27)
- **Remote Pi Management:** Buttons für Git Pull, Restart Service, Reboot und Buffer Wipe in WebUI (Einstellungen) integriert.
- **UI-Feedback System:** Pi-Rückmeldungen via MQTT werden als Live-Alerts in der WebUI angezeigt.
- **Global Toast/Alerts:** Benachrichtigungen von index.html nach layout.html verschoben, um seitenübergreifend sichtbar zu sein.
- **Coverage Stats:** Gesamtabdeckung (kumuliert) und Session-Abdeckung in Statistiken ergänzt.

### v2.5.7 (2026-03-27)
- **Verbesserter Hot-Reload:** Das System erkennt nun präzise, welche Einstellungen (z.B. GNSS-Modus) einen Neustart erfordern und welche sofort übernommen werden.
- **Hot-Reload für GNSS:** Der `GPS_GNSS_MODE` wird nun sofort in die In-Memory Konfiguration übernommen.

### v2.5.6 (2026-03-27)
- **Fix: GNSS Mode Persistence:**
  - Die Einstellung für den GNSS-Modus (SBAS/GLONASS) wird nun zuverlässig aus `/data/worx_gps/.env` gelesen.
- **UI-Verbesserung:**
  - GNSS-Modus Auswahl von Textbox auf Dropdown-Menü umgestellt.

### v2.5.5 (2026-03-27)
- **Add-on Version Cleanup:** Vorbereitung für stabilen Release und Samba-Sync Tests.

### v2.5.4 (2026-03-26)
- **Intelligentes Session-Management:**
  - Automatischer Session-Split bei Zeitlücken (> 1h) im Puffer. Verhindert das "Zusammenkleben" von Mähvorgängen bei Verbindungsabbrüchen.
  - Puffer-Reset bei Add-on Start zur Vermeidung von Geister-Sessions.
- **Multi-Session Layering für Qualität:**
  - WiFi- und GPS-Qualitätskarten unterstützen jetzt Layer-Auswahl (einzelne Sessions ein-/ausblendbar) wie in der normalen Fahrten-Karte.
  - Optimierte Legende (Fixed Index) für stabilere Visualisierung.
- **WebUI Dual-Mode Support:** Korrekte Asset-Pfad-Auflösung sowohl für Home Assistant Ingress als auch für direkten IP-Zugriff.
- **Deployment-Fix:** `run.sh` Zeilenumbrüche für Linux (LF) korrigiert.

### v2.5.3 (2026-03-25)
- **Bugfix Multi-Lap (Doppelte Messdaten):** Das Problem der mehrfach gezeichneten, überlappenden Runden desselben Mähvorgangs wurde an der Wurzel behoben:
  - Strikte Deduplizierung anhand von exakten Zeitstempeln beim Einlesen der CSV-Puffer (`utils.py`).
  - Robusteres Leeren der Pufferdatei auf dem Pi (`data_recorder.py`), auch bei Verbindungsfehlern zum MQTT-Broker, um endloses Ansammeln und wiederholtes Senden desselben Puffers zu verhindern.

### v2.5.2 (2026-03-25)
- **Bugfix Multi-Lap:** Karte zeigte nach einem Mähvorgang mehrere überlappende Runden. Ursache: `flatten_data()` statt echter Multi-Session-Struktur. Fix: Liste-von-Listen an `create_heatmap` übergeben.
- **Bugfix Kumulierte Qualität/WiFi:** `quality_kumuliert` und `wifi_kumuliert` Karten fehlten. `_generate_all_heatmaps()` Parameter optional gemacht + fehlende Aufrufe in `Worx_GPS.py` ergänzt.

### v2.5.1
- **Bugfix Kumulierte Karten:** TypeError bei Colormap-Berechnung behoben (`float()`-Konvertierung).
- **Bugfix Puffer-Sync:** Interne GPS-Puffer werden nach Session-Löschung sofort aktualisiert (`reload_buffers()`).
- **Bugfix Filternachverfolgung:** Filter-Parameter als JSON-Snapshot pro Session gespeichert.

### v2.5.0
- **Web-UI Datenbank-Manager:** React-Seite `/database` mit Session-Übersicht, Detail-Ansicht, CSV/JSON-Export, Einzellöschung und DB-Info.
- **Sessions-Metadaten (Aufnahme-DNA):** Snapshot der aktiven Filter-Parameter pro Session (Kalman, HDOP, Dead Reckoning, Outlier Detection).
- **Qualitäts-Analyse:** Langzeit-Statistik (Ø Satelliten, Ø/Min/Max HDOP, Coverage, DR-Status) im Datenbank-Manager.
- **Hot-Reload Config:** Post-Processing-Einstellungen werden nach dem Speichern sofort in-memory übernommen.

### v2.4.0
- **Worx Cloud Integration (Phase 1-3):** `WorxCloudService` ersetzt HA-Polling. Direkter Cloud-Zugriff via `pyworxcloud`.
- **Mower Control UI:** React-Seite zur vollständigen Mäher-Steuerung (Start, Stop, Zonen, Zeitplan, Expert-Modus, Raw MQTT Monitor).
- **HA MQTT Auto-Discovery:** Automatische Bereitstellung von 15 Entitäten für Home Assistant.
- **Sensor-Fusion (Phase 4):** Cloud-IMU (Yaw) + Pi-GPS für Dead Reckoning.
- **Zentrales Logging:** Live-Logs von WebUI und Pi mit Filterung.

### v2.3.0
- **Dead Reckoning:** Fusion von GPS und IMU-Yaw für bessere Kurven.
- **GNSS Toggle:** Umschaltung zwischen SBAS (EGNOS) und GLONASS.
- **Persistente Config:** Änderungen über WebUI werden in `/data/.env` gespeichert.
- **Legacy Route Cleanup:** Flask-Routen durch React-SPA ersetzt.

### v2.0.0
- **GPS-Processing-Pipeline:** 6-stufige Filterung (HDOP, Geofence, Drift, Speed, Dead Reckoning, Kalman).
- **Adaptiver Kalman-Filter:** HDOP-gewichtete Messunsicherheit.
- **AssistNow Autonomous:** 3-Tage Orbit-Vorhersage für schnellen Fix.
- **Pedestrian Mode:** Optimiert für Geschwindigkeiten < 5 km/h.
- **Geofencing:** Mähzonen und Verbotszonen über interaktiven Editor.
