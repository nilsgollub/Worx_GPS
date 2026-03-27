# 📝 Beobachtungen, Fehler & Roadmap (v2.5.1+)

Dieses Dokument hält den aktuellen Status der Software fest, inklusive bekannter Probleme und gewünschter Erweiterungen (Feature Requests).

## 🐛 Bekannte Fehler (Known Issues)

| Fehler | Status | Beschreibung |
| :--- | :--- | :--- |
| **Kumulierte Karten** | ✅ Behoben | TypeError bei Colormap-Berechnung behoben (`float()`-Konvertierung in `heatmap_generator.py`). |
| **Puffer-Synchronisierung** | ✅ Behoben | Interne GPS-Puffer (Letzte 10) werden jetzt nach dem Löschen von Sessions in der DB sofort aktualisiert (`DataService.reload_buffers()`). |
| **Filternachverfolgung** | ✅ Behoben | Filter-Parameter werden jetzt als JSON-Snapshot (`filter_config`) in jeder Session gespeichert und im Datenbank-Manager angezeigt. |
| **Multi-Lap Darstellung** | ✅ Behoben | Karte zeigte nach einem einzigen Mähvorgang mehrere überlappende Runden. Ursache: `flatten_data()` wurde fälschlich für Multi-Session Maps verwendet, wodurch alle Punkte als ein einziger Pfad gezeichnet wurden. Fix: Übergabe der echten Liste-von-Listen-Struktur. |
| **Kumulierte Qualitäts-/WiFi-Karten** | ✅ Behoben | `quality_kumuliert` und `wifi_kumuliert` Karten wurden nicht angezeigt. Zwei Ursachen: (1) `_generate_all_heatmaps()` crashte mit TypeError bei Reset/Delete da `current_session_data` Pflichtparameter war. (2) `Worx_GPS.py` fehlten die Aufrufe für diese Karten komplett. |


## 💡 Feature Requests (Wunschliste)

### 1. Worx Cloud Protokoll Analyse (Phase 2)
- **Ziel:** Volle Kontrolle und Verständnis des Worx Cloud MQTT Protokolls.
- **Funktionen:**
  - Manuelle JSON-Befehle über das Frontend senden (Expert-Modus).
  - Raw MQTT Payloads (`dat` und `cfg`) live im Frontend monitoren.
  - Befehls-Historie und Templates für systematische Tests.

### 2. Statistische Langzeitanalyse (erweitert)
- **Ziel:** Visualisierung, wie sich die Empfangsqualität (HDOP/Satelliten) über die Wochen verändert (z.B. durch Belaubung der Bäume).
- **Status:** Basis-Tabelle im Datenbank-Manager implementiert (Qualitäts-Analyse Button). Chart-Visualisierung noch offen.

### 3. Remote Recorder-Steuerung (Pi Management)
- **Ziel:** Den Raspberry Pi Zero 2 W (Recorder) direkt über die WebUI verwalten.
- **Funktionen:**
  - **Reboot:** Den Pi über MQTT-Befehl neu starten.
  - **Flush/Clear:** Den lokalen CSV-Puffer auf dem Pi manuell löschen.
  - **Status-Monitor:** CPU-Temperatur und Dienst-Status live in der UI.


---

## ✅ Erledigt

- [x] **Worx Cloud Backend (Phase 1):** `WorxCloudService` ersetzt HA-Wachhund.
- [x] **Mower Control UI:** Neue React-Seite zur Steuerung (Start, Stop, Zonen etc.).
- [x] **Dead Reckoning:** Fusion von GPS und IMU-Yaw für bessere Kurven.
- [x] **GNSS Toggle:** Umschaltung zwischen SBAS (EGNOS) und GLONASS (NEO-7M Support).
- [x] **Persistente Config:** Änderungen in der Web-UI werden in `/data/.env` gespeichert.
- [x] **HA Discovery:** Automatische Bereitstellung von 15 Entitäten für Home Assistant.
- [x] **Legacy Route Cleanup:** Entfernen der alten Flask-Routen zugunsten der React-SPA.
- [x] **Phase 2a – MowerControl:** React-Komponente zur Mäher-Steuerung (Start, Stop, Zonen, Zeitplan).
- [x] **Phase 2b – Expert-Modus:** Manuelle JSON-Befehle über das Frontend senden.
- [x] **Phase 2c – Raw MQTT Monitor:** Live-Anzeige der rohen `dat`/`cfg` MQTT-Payloads im Frontend.
- [x] **Bugfix Kumulierte Karten:** TypeError in `heatmap_generator.py` bei `float()`-Konvertierung behoben.
- [x] **Hot-Reload Config:** Post-Processing-Einstellungen (Dead Reckoning, Kalman, HDOP etc.) werden nach dem Speichern sofort in-memory übernommen – kein Neustart mehr nötig.
- [x] **Web-UI Datenbank-Manager:** Neue React-Seite `/database` mit Session-Übersicht, Detail-Ansicht, CSV/JSON-Export, Einzellöschung und DB-Info (Größe, Tabellen, Punktanzahl).
- [x] **Sessions-Metadaten (Aufnahme-DNA):** Jede Session speichert einen Snapshot der aktiven Filter-Parameter (`filter_config` JSON) inkl. Kalman-Noise, HDOP-Schwelle, Dead Reckoning, Outlier Detection.
- [x] **Qualitäts-Analyse:** Langzeit-Statistik über alle Sessions (Ø Satelliten, Ø/Min/Max HDOP, Coverage, Dead Reckoning Status) im Datenbank-Manager.
- [x] **Bugfix DB-Sync:** Interne GPS-Puffer (Letzte 10) werden jetzt nach dem Löschen von Sessions in der DB sofort aktualisiert (Reload-Mechanismus).
- [x] **Bugfix Multi-Lap:** Karte zeigte mehrere überlappende Runden statt eines Pfads. `flatten_data()` entfernt, korrekte Liste-von-Listen-Struktur an Multi-Session Maps übergeben.
- [x] **Bugfix Kumulierte Qualität/WiFi:** `quality_kumuliert`/`wifi_kumuliert` Karten fehlten. `_generate_all_heatmaps()` Parameter optional gemacht + fehlende Aufrufe in `Worx_GPS.py` ergänzt.

