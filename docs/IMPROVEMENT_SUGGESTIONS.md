# 🛠 Projekt-Audit & GPS-Optimierungsstrategie

Dieses Dokument analysiert den aktuellen Zustand der Software und zeigt Wege auf, wie die Genauigkeit der GPS-Tracking-Daten ohne Hardware-Änderungen signifikant verbessert werden kann.

---

## 🔍 1. Code-Audit: Ist es ein Flickenteppich?

**Urteil: Teilweise.** Die Architektur ist solide, aber es gibt "tote Winkel".

*   **Positiv:** 
    *   Klare Trennung zwischen Recorder (Pi) und Auswertung (PC).
    *   Zentrale Konfiguration in `config.py` wird durchgängig genutzt.
    *   Module wie `data_manager.py` und `mqtt_handler.py` sind stabil und spezialisiert.
*   **Negativ:**
    *   **Inaktive Konfiguration:** In der `config.py` vorbereitete Parameter (z.B. `kalman_enabled`) haben im Code keine Funktion. Sie sind "Versprechen", die noch nicht eingelöst wurden.
    *   **Komplexität:** Der `heatmap_generator.py` ist mit über 1100 Zeilen zu groß. Er übernimmt zu viele Aufgaben (Datenaufbereitung, Karten-Rendering, PNG-Export).
    *   **Fehlende Validierung:** GPS-Punkte werden gespeichert, sobald ein Fix vorhanden ist. Es findet keine Prüfung auf "Ausreißer" oder physikalische Plausibilität statt.

---

## 🛰 2. GPS-Genauigkeit: Softwarebasierte Lösungen

Da die Hardware-Abdeckung gut ist, liegen die Ungenauigkeiten meist an Reflexionen (Multipath) oder atmosphärischen Störungen. Hier sind die Hebel:

### A. Aktive Filterung (Kalman-Filter)
Der effektivste Weg. Ein Kalman-Filter kombiniert die GPS-Position mit einem Bewegungsmodell (konstante Geschwindigkeit/Beschleunigung).
*   **Nutzen:** Er "glättet" die Kurven und ignoriert kurze seitliche Sprünge.
*   **Status:** Muss in `processing.py` implementiert werden, bevor die Daten in die Datenbank fließen.

### B. HDOP/PDOP-Filterung
Momentan prüfen wir nur, ob Satelliten sichtbar sind. Ein GGA-Datensatz liefert aber auch den **HDOP**-Wert (Horizontal Dilution of Precision).
*   **Maßnahme:** Punkte mit einem HDOP > 2.0 (oder einem konfigurierbaren Schwellenwert) sollten ignoriert oder in der Heatmap schwächer gewichtet werden.

### C. Statische Drift-Unterdrückung (Zero-Velocity-Update)
Wenn der Mäher steht (z.B. beim Laden oder Feststecken), "wandert" die GPS-Position oft in einem kleinen Radius umher.
*   **Maßnahme:** Wenn sich die Position um weniger als X cm in Y Sekunden bewegt, wird der Punkt als "statisch" markiert und nicht als Bewegung gewertet.

### D. Physikalische Plausibilität
Ein Mähroboter kann sich nur mit einer begrenzten Geschwindigkeit bewegen (z.B. max. 0.5 m/s).
*   **Maßnahme:** Wenn ein neuer Punkt impliziert, dass der Mäher gerade mit 10 km/h gefahren ist, ist dies ein Messfehler und muss verworfen werden.

### E. Spline-Interpolation (Post-Processing)
Für die Pfad-Darstellung (Pfeile) können die Punkte durch eine kubische Spline-Kurve verbunden werden.
*   **Nutzen:** Der Pfad wirkt organischer und folgt eher der realen Fahrtroute als das "Zick-Zack" der Rohdaten.

---

## 📋 3. Nächste Schritte (Empfehlung)

1.  **Code-Cleanup:** Entfernen der alten `pyubx2`-Leichen und Konsolidierung der `stop_recording`-Logik.
2.  **Modularisierung:** Auslagern der Post-Processing-Logik aus dem `heatmap_generator.py` in eine dedizierte `filter_engine.py`.
3.  **Implementierung Kalman-Filter:** Nutzung von `filterpy` oder einer kompakten Eigenimplementierung in `processing.py`.
4.  **HDOP-Integration:** Erweiterung des `gps_handler.py`, um den HDOP-Wert mit zu übertragen und in der Datenbank zu speichern.

**Möchtest du, dass ich einen dieser Punkte (z.B. den Kalman-Filter) detaillierter plane oder direkt mit dem Cleanup beginne?**
