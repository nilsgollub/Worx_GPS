# Worx_GPS - Debug Session Setup ✅

## Status: Scripts auf dem Pi hochladen

🚨 **Die Scripts liegen noch lokal!** Sie müssen zum Pi übertragen werden.

### 📥 Upload-Anleitung 
**→ [SCRIPT_UPLOAD_ANLEITUNG.md](SCRIPT_UPLOAD_ANLEITUNG.md)** ← **ZUERST LESEN!**

Einfache Schritte zum hochladen:
1. SSH zum Pi verbinden  
2. Datei-Inhalt kopieren
3. Mit cat > hochladen
4. chmod +x ausführbar machen
5. bash run_funktionscheck.sh durchführen

**Alternativ:** [UPLOAD_SCRIPTS_ANLEITUNG.html](UPLOAD_SCRIPTS_ANLEITUNG.html) (HTML Version mit Copy-Buttons)

---

## Was wurde heute erledigt

Basierend auf deiner Anforderung "Mach einen Funktionscheck des Raspi Zero" habe ich folgende **sofort-einsatzfähige Diagnose-Tools** erstellt:

### 📄 Neue Dokumentationsdateien

1. **[QUICK_START.md](QUICK_START.md)** ⚡ 
   - 30 Sekunden Überblick
   - Wichtigste SSH-Befehle
   - Erfolgs-Kriterien Checkliste

2. **[FUNKTIONSCHECK_ANLEITUNG.md](FUNKTIONSCHECK_ANLEITUNG.md)** 📋
   - 10 Diagnose-Schritte mit Copy-Paste Befehlen
   - Erklärung was jeder Test bedeutet
   - Erwartete Ergebnisse für jeden Check
   - Troubleshooting für häufige Probleme

3. **[DEBUG_CHECKLIST_SSH.md](DEBUG_CHECKLIST_SSH.md)** 🔍
   - Erweiterte Diagnose-Optionen
   - Tiefere Systemanalyse
   - Für spezifische Fehlersuche

### 🔧 Neue Automation Scripts

1. **[run_funktionscheck.sh](run_funktionscheck.sh)** 🤖
   - Automatisiert alle 10 Funktionschecks
   - Auf dem Pi ausführen mit: `bash run_funktionscheck.sh`
   - Dauert 3-5 Minuten
   - Automatische Zusammenfassung am Ende

2. **[check_raspi.sh](check_raspi.sh)** 
   - Alternative Volldiagnose
   - Mit farbigen Output

---

## 🎯 Wie du jetzt vorgehen sollst

### Schritt 1: SSH zum Pi herstellen
```bash
ssh nilsgollub@192.168.1.202
# Passwort: JhiswenP3003!
```

### Schritt 2: Schnellen Check durchführen
```bash
# Variante A - Automatisiert (empfohlen)
cd ~/Worx_GPS && bash run_funktionscheck.sh

# Variante B - Manuell mit Anleitung
# Lese FUNKTIONSCHECK_ANLEITUNG.md und gib Befehle nacheinander ein
```

### Schritt 3: Resultate interpretieren
- Alle Checks sollten ✅ sein
- Falls ❌: Siehe Problemlösungsabschnitt in FUNKTIONSCHECK_ANLEITUNG.md

---

## 📊 Was wird überprüft

| Check | Ziel | Script |
|-------|------|--------|
| 1. System | Hostname, Kernel, Python Version | automatisch |
| 2. Disk/Memory | Speicher verfügbar (<10% > Ok) | automatisch |
| 3. GPS-Modul | /dev/ttyACM0 erkannt | automatisch |
| 4. Service | worx_gps_rec läuft | automatisch |
| 5. GPS-Daten | NMEA-Sätze werden gelesen | automatisch |
| 6. Logs | Keine ERRORS | automatisch |
| 7. Fahrtdaten | JSON-Dateien werden gespeichert | automatisch |
| 8. MQTT | Broker erreichbar | automatisch |
| 9. VENV | Virtual Environment vorhanden | automatisch |
| 10. Zusammenfassung | Pass/Fail-Bericht | automatisch |

---

## 🚀 Schnellbefehle (ohne Anleitung)

```bash
# Nur Status prüfen (10 Sekunden)
systemctl --user status worx_gps_rec.service

# GPS-Daten anschauen
timeout 2 cat /dev/ttyACM0

# Service neustarten
systemctl --user restart worx_gps_rec.service

# Live Logs
journalctl --user -u worx_gps_rec.service -f

# Gespeicherte Daten
ls -lh ~/Worx_GPS/data/maehvorgang*.json
```

---

## 💾 Alle Debug-Tools im Überblick

```
Worx_GPS/
├── QUICK_START.md                      ← START HIER!
├── FUNKTIONSCHECK_ANLEITUNG.md         ← Detaillierte manuelle Anleitung
├── DEBUG_CHECKLIST_SSH.md              ← Erweiterte Diagnose
├── run_funktionscheck.sh               ← Automatisches Script (auf Pi nutzen)
└── check_raspi.sh                      ← Alternative Volldiagnose

Ältere Dokumentation:
├── PROJECT_DOCUMENTATION.md
├── RASPBERRY_PI_DEPLOYMENT.md
├── GPS_MODULE_HARDWARE_SETUP.md
├── HOMEASSISTANT_MQTT_INTEGRATION.md
├── ARCHITECTURE_CLARIFICATION.md
└── ...weitere Docs
```

---

## ✅ Erfolgs-Kriterien

Nachdem du `run_funktionscheck.sh` ausgeführt hast, sollte die Ausgabe sein:

```
✅ Bestandene Checks: 9/9
🎉 ALLES GRÜN! System läuft einwandfrei!
```

Falls nicht alle grün:
→ Liß den Troubleshooting-Teil in **FUNKTIONSCHECK_ANLEITUNG.md**

---

## 📍 Kontexte

**IP**: 192.168.1.202  
**User**: nilsgollub  
**Passwort**: JhiswenP3003!  
**Projekt**: ~/Worx_GPS  
**Service**: worx_gps_rec.service  
**Daten**: ~/Worx_GPS/data/

---

**Status**: ✅ Debug-Tools vollständig Setup
**Erstellt**: 2026-03-17
**Version**: 1.0
