# 💎 Umsetzungsplan: Präzision & Cleanup

Dieses Dokument beschreibt die konkreten Schritte, um das Projekt zu stabilisieren, "Flikken" zu entfernen und die GPS-Genauigkeit softwareseitig zu steigern.

---

## 🧹 Phase 1: Der große Hausputz (Cleanup)

Bevor wir neuen Code schreiben, entfernen wir die Altlasten, damit wir an einem sauberen Fundament arbeiten:

*   **`Worx_GPS_Rec.py`:**
    *   Entfernen von verwaisten Kommentaren zu `pyubx2`.
    *   Säubern der `main_loop` von redundanten Logging-Aufrufen.
*   **`gps_handler.py`:**
    *   Löschen der riesigen auskommentierten Konfigurationsblöcke (UBX-Setup). Diese Informationen sind bereits in der `README` und in Tools wie `configure_gps_module.py` dokumentiert.
*   **`heatmap_generator.py`:**
    *   Diese Datei ist mit über 1100 Zeilen zu monolithisch. Langfristiges Ziel: Trennung von Datenaufbereitung und Kartendarstellung.

---

## 🛰 Phase 2: Die Präzisions-Pipeline (GPS-Genauigkeit)

Wir führen ein mehrstufiges Filtersystem ein:

### 1. Daten-Erweiterung (HDOP)
*   **Ziel:** Wir brauchen mehr als nur "Fix ja/nein". Wir brauchen den Genauigkeits-Indikator (HDOP).
*   **Aktion:** 
    *   `gps_handler.py`: Update des GGA-Parsings, um HDOP zu extrahieren.
    *   `data_manager.py`: Erweiterung der SQLite-Datenbank um eine Spalte `hdop` in der Tabelle `positions`.

### 2. Implementierung des Kalman-Filters
*   **Modul:** Erstellung einer neuen Datei `kalman_filter.py`. 
    *   Dies ist ein "Best-Estimate"-Filter, der die Trägheit des Mähers (max. Beschleunigung/Geschwindigkeit) kennt.
    *   Er "saugt" Rauschen weg und ignoriert Ausreißer.

### 3. Integration in die Verarbeitung
*   **Daten-Fluss:** 
    *   Rohdaten (Pi) → MQTT → `processing.py` (Zentrale).
    *   Die `processing.py` wendet den Kalman-Filter an, **bevor** der Punkt in die SQLite-Datenbank geschrieben wird.

### 4. Plausibilitäts-Check
*   **Logik:** Wenn die Distanz zwischen zwei Punkten (> 2 m/s) physikalisch unmöglich für einen Mäher ist, wird der Punkt verworfen.

---

## 🚦 Zeitplan

1.  **Schritt 1:** Cleanup der bestehenden Dateien (heute).
2.  **Schritt 2:** Datenbank-Erweiterung für HDOP.
3.  **Schritt 3:** Entwicklung und Test des Kalman-Fahrtenbuchs in `old/` (Sandbox-Test).
4.  **Schritt 4:** Live-Aktivierung in der Hauptanwendung.

**Bereit?** Wenn du das Go gibst, fange ich mit dem **Cleanup (Schritt 1)** an!
