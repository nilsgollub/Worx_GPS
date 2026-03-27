# 🛰️ GPS-Optimierung — Referenz

> Dieses Dokument fasst die **umgesetzten** Strategien zur GPS-Genauigkeit zusammen.  
> Alle hier beschriebenen Maßnahmen sind in `processing.py` und `gps_handler.py` aktiv.

---

## Processing-Pipeline (`processing.py`)

Die zentrale Funktion `process_gps_data()` verarbeitet Rohdaten in 6 Stufen:

```
Rohdaten (Pi) → MQTT → processing.py → SQLite → Heatmap
```

| # | Stufe | Beschreibung | Konfiguration |
|---|-------|-------------|---------------|
| 1 | **HDOP-Filter** | Verwirft Punkte mit schlechter Satellitengeometrie | `hdop_threshold` (Default: 2.5) |
| 2 | **Geofence-Filter** | Nur Punkte in erlaubten Zonen, keine in Verbotszonen | Zonen-Editor in der WebUI |
| 3 | **Drift-Sperre** | Unterdrückt GPS-Zappeln bei Stillstand (< 0.1 m/s) | Intern |
| 4 | **Speed-Outlier** | Entfernt physikalisch unmögliche Sprünge | `max_speed_mps` (Default: 1.5) |
| 5 | **Dead Reckoning** | Fusion von GPS-Geschwindigkeit mit IMU-Yaw zur Kursstabilisierung | `dead_reckoning_enabled` |
| 6 | **Kalman-Filter** | Adaptives Glätten basierend auf HDOP-gewichteter Messunsicherheit | `kalman_measurement_noise`, `kalman_process_noise` |

Alle Parameter lassen sich **live über die WebUI** ändern (Hot-Reload, kein Neustart nötig).

---

## Hardware-Konfiguration (`gps_handler.py`)

Das u-blox NEO-7M Modul wird beim Start automatisch konfiguriert:

| Einstellung | UBX-Befehl | Beschreibung |
|-------------|-----------|--------------|
| **Pedestrian Mode** | `UBX-CFG-NAV5` (DynModel 3) | Optimiert für < 5 km/h, verhindert Unterdrückung kleiner Bewegungen |
| **AssistNow Autonomous** | `UBX-CFG-NAVX5` (aopCfg=1) | Orbit-Vorhersage für 3 Tage → schneller Fix nach Pausen |
| **Elevation Mask** | `UBX-CFG-NAV5` (10°) | Unterdrückt Multipath-Fehler durch Horizont-Filterung |
| **GNSS-Modus** | `UBX-CFG-GNSS` | Umschaltbar: GPS+SBAS (Präzision) oder GPS+GLONASS (mehr Satelliten) |

---

## Mögliche zukünftige Optimierungen

| Idee | Aufwand | Nutzen |
|------|---------|--------|
| **Spline-Interpolation** (Post-Processing) | Gering | Organischere Pfade für die Visualisierung |
| **Ground Plane** (10×10 cm Alublech unter GPS-Antenne) | Hardware | Weniger Multipath-Reflexionen |
| **u-blox NEO-M8N Upgrade** | Hardware | GPS+GLONASS parallel, mehr Satelliten |
| **RTK (u-blox F9P)** | Hardware (teuer) | cm-Genauigkeit |
