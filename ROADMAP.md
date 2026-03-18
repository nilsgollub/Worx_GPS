# 🗺 Worx GPS - Projekt Roadmap

Dieses Dokument beschreibt den aktuellen Status und die zukünftige Entwicklung des Worx GPS Tracking & Monitoring Systems.

---

## ✅ Erledigt (Meilensteine)

### 1. SQLite Datenbank-Migration (März 2026)
*   **Status:** Abgeschlossen
*   **Details:** Umstellung von JSON/CSV Flatfiles auf eine strukturierte SQLite-Datenbank (`worx_gps.db`).
*   **Vorteile:** Ultraschneller Datenzugriff, SD-Karten-schonendes Schreiben, einfache Abfragen für Statistiken.

### 2. Automatische Abdeckungsanalyse
*   **Status:** Abgeschlossen
*   **Details:** Grid-basierte Berechnung der gemähten Fläche pro Session.
*   **Feature:** Prozentuale Anzeige der Abdeckung direkt in der WebUI (gespeichert in DB).

### 3. Integrated Service Starter
*   **Status:** Abgeschlossen
*   **Details:** Zentrales [start_services.py](cci:7://file:///c:/Users/gollu/Documents/GitHub/Worx_GPS/start_services.py:0:0-0:0) zum gleichzeitigen Starten von Logik und UI mit farbigem Logging.

---

## 🚀 In Arbeit / Nächste Schritte

### 4. Visueller Geofencing-Editor (Priorität: Hoch)
*   **Ziel:** Definition von Mäh-Zonen direkt per Mausklick auf der Karte.
*   **Details:**
    *   Polygon-Tool in der Leaflet/React Map.
    *   Speichern der Koordinaten in der Datenbank.
    *   Visueller Alarm in der UI, wenn der Mäher die Zone verlässt.

### 5. Live-Position mit Path Prediction
*   **Ziel:** Vorhersage der Bewegung für die nächsten 5-10 Sekunden.
*   **Feature:**
    *   Anzeige des Mähers als Grafik (`worx.png`) in Fahrtrichtung.
    *   Transparenter Vektor (Pfeil/Pfad), der die wahrscheinliche Richtung anzeigt.
    *   Interpolation zwischen GPS-Fixes für flüssige Animation.

---

## 📅 Geplante Features (Zukunft)



### 6. Filterbare Heatmaps
*   **Ziel:** Auswahl spezifischer Mähvorgänge für die kumulierte Ansicht.
*   **Feature:** Checkboxen/Multiselect in der UI, um nur bestimmte Tage oder Sessions in der Heatmap anzuzeigen.

### 7. Wartungs-Dashboard
*   **Ziel:** Tracking der Mähstunden und Klingenwechsel-Erinnerungen basierend auf den realen GPS-Betriebsstunden.

### 8. Konfigurationsoberfläche
*   **Ziel:** Möglichst viele Parameter sollen über die UI gesteuert werden können.


---

*Zuletzt aktualisiert: 18. März 2026*
