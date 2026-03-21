# GPS-Präzisions-Optimierung (Worx-GPS)

Dieses Dokument analysiert die Möglichkeiten zur Steigerung der Genauigkeit unter Verwendung des **U-BLOX NEO-7M** Moduls am Raspberry Pi Zero W.

## 1. Aktueller Status (Software-Basis)
Wir haben bereits eine starke Grundlage geschaffen:
*   **Adaptiver Kalman-Filter:** Nutzt den HDOP-Wert (Horizontal Dilution of Precision) als dynamisches Maß für die Messunsicherheit. Bei schlechtem Signal vertraut der Filter der Bewegungsvorhersage mehr als dem Sensor.
*   **AssistNow Autonomous (Hardware-basiert):** Die NEO-7M Hardware wurde so konfiguriert, dass sie Satelliten-Orbits für bis zu 3 Tage selbst vorausberechnet. Damit entfällt die Abhängigkeit von kostenpflichtigen u-blox Cloud-Diensten bei gleichzeitig schnellem Start (TTFF).
*   **Outlier-Detection:** Punkte mit physikalisch unmöglichen Geschwindigkeiten (> 1.5 m/s) werden bereits vor der Filterung verworfen.

## 2. Softwareseitige Optimierungsmöglichkeiten

### A. Dynamische Aggregation bei Stillstand
Der NEO-7M neigt im Stillstand zum "Driften" (GPS-Rauschen). 
*   **Konzept:** Wenn die berechnete Geschwindigkeit über mehrere Sekunden < 0.1 m/s liegt, wird kein neuer Pfadpunkt gezeichnet, sondern der Mittelwert der letzten 5 Sekunden als "Präzisions-Punkt" fixiert.
*   **Vorteil:** Verhindert das lästige "Zittern" der Heatmap an Stellen, wo der Mäher wendet oder feststeckt.

### B. Geofence-Constraint (Map Matching)
Wir wissen, wo der Rasen aufhört.
*   **Konzept:** Wenn die Filter-Vorhersage einen Punkt außerhalb des Geofences (Grundstücksgrenzen) platziert, kann der Kalman-Filter diesen Punkt "bestrafen" (höhere Gewichtung der Geometrie).
*   **Vorteil:** Der Pfad bleibt "innerhalb" der Rasenfläche, auch wenn das GPS-Rauschen ihn nach draußen ziehen will.

### C. Signal-Gating (HDOP Hard-Limit)
Momentan verarbeiten wir fast alles.
*   **Konzept:** Einführung eines Schwellwerts (z. B. HDOP > 4.0). Punkte oberhalb dieses Werts werden nicht nur schwach gewichtet, sondern komplett ignoriert, bis das Signal wieder besser wird.

## 3. Hardwareseitige Optimierung (Low-Budget)

Da der NEO-7M ein Single-Band Modul ist, ist die **Antennenplatzierung** entscheidend:
1.  **Ground Plane:** GPS-Antennen funktionieren massiv besser, wenn sie auf einer Metallplatte (ca. 10x10 cm, z. B. einfaches Alublech) montiert sind. Dies schirmt Reflexionen vom Boden (Multipath) ab.
2.  **Abschirmung:** Der Raspberry Pi Zero erzeugt elektromagnetische Störungen. Ein kleiner Abstand (10-15 cm) zwischen Pi und GPS-Antenne oder eine Abschirmfolie bewirkt oft Wunder.

## 4. Hardware-Upgrade (Optionaler Ausblick)
Falls die Software-Tricks nicht reichen, wäre ein Umstieg auf ein **U-BLOX NEO-M8N** oder (für Profi-Ansprüche) ein **F9P (RTK)** denkbar. Der M8N kann GPS und GLONASS parallel empfangen, was die Anzahl der Satelliten fast verdoppelt und die Stabilität massiv erhöht.

---
### Nächste Schritte (Vorschlag)
1.  **Testlauf Phase 2:** Beobachten des neuen Kalman-Filters im Realbetrieb.
2.  **Implementierung Geofencing-Editor:** Um die Geofence-Constraint Logik nutzen zu können.
3.  **Feintuning der Kalman-Parameter:** Justierung der Meter-Varianz in der `config.py`.
