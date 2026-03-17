# 📚 Worx_GPS Dokumentation - Übersicht & Navigation

**Projekt**: Worx GPS Tracking & Monitoring System  
**Status**: ✅ Vollständig dokumentiert  
**Letzte Aktualisierung**: 2026-03-17

---

## 🔴 DEBUGGING / PROBLEM-LÖSUNG

**→ [FUNKTIONSCHECK_ANLEITUNG.md](FUNKTIONSCHECK_ANLEITUNG.md)** ← **ZUERST LESEN! Schnelle Diagnose**

Diese Anleitung zeigt Copy-Paste-Befehle für sofortigen Funktionscheck:
- Schritt-für-Schritt Diagnose
- Erwartete Ergebnisse für jeden Check
- Sofort-Behebung häufiger Probleme
- Erfolgs-Kriterien Checkliste

**Danach:**
→ **[DEBUG_CHECKLIST_SSH.md](DEBUG_CHECKLIST_SSH.md)** - Wenn detailliertere Diag. nötig

---

## ⚠️ WICHTIG: Datenquellen verstehen

Das System nutzt **ZWEI unabhängige Datenquellen**:

→ **[GPS_MODULE_HARDWARE_SETUP.md](GPS_MODULE_HARDWARE_SETUP.md)** ← Lokale GPS
→ **[HOMEASSISTANT_MQTT_INTEGRATION.md](HOMEASSISTANT_MQTT_INTEGRATION.md)** ← Mäher-Status

**GPS-Position**: Vom GPS-Modul (lokal am Raspi angeschlossen)
**Mäher-Status**: Von HomeAssistant (über MQTT publiziert)

Das System **kombiniert beide** und speichert zusammen ab.

---

## 🎯 Nach Rolle / Aufgabe

## 🚀 Ich möchte SOFORT testen, ob alles läuft

**WICHTIG: Scripts müssen zuerst auf den Pi hochgeladen werden!**

**Schritt 1:**  
→ **[SCRIPT_UPLOAD_ANLEITUNG.md](SCRIPT_UPLOAD_ANLEITUNG.md)** - Upload-Anleitung (5 Min)

**Schritt 2:**  
→ **[QUICK_START.md](QUICK_START.md)** - Nach Upload: Schnelltest durchführen

**Komplette Anleitung mit all Befehlen:**  
→ **[FUNKTIONSCHECK_ANLEITUNG.md](FUNKTIONSCHECK_ANLEITUNG.md)** - Detaillierte Schritt-für-Schritt

---

## 🎯 Dokumentation auswählen (Nach Rolle/Aufgabe)

### 👨‍💼 **Ich bin Projektmanager**
> Verstehe ich das Projekt richtig?

**Lesen Sie in dieser Reihenfolge:**

1. **[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)** - Komplette Projektübersicht
   - 📊 Architektur
   - 🎯 Kernfunktionalität
   - 🔧 Alle Komponenten erklärt

2. **[RASPBERRY_PI_DEPLOYMENT.md](RASPBERRY_PI_DEPLOYMENT.md)** - Hardware Setup
   - Was läuft wo
   - Komponenten-Verantwortung
   - Betriebskosten (minimal)

3. **Starten Sie mit schweren Fragen beantwortet:**
   - "Was ist das System?" → PROJECT_DOCUMENTATION.md
   - "Was kostet es?" → system requirements
   - "Wie zuverlässig ist es?" → error handling section

---

### 👨‍💻 **Ich bin Developer/Deployer**
> Ich muss das System in Produktion nehmen

**Schnelle Checkliste:**

```bash
# VORBEREITUNG: Zwei Dinge müssen funktionieren!

# 1️⃣ GPS-Modul (lokal Hardware)
ssh nilsgollub@192.168.1.202        # Passwort: JhiswenP3003!
cat /dev/ttyACM0 | head -5           # Muss NMEA-Daten zeigen!

# 2️⃣ HomeAssistant + MQTT (externe Datenquelle)
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v
# Sollte Status, Battery, Error sehen

# DANN: Installation
- RASPBERRY_PI_DEPLOYMENT.md (Sections: Installation, Setup)
- GPS_MODULE_HARDWARE_SETUP.md (bei GPS-Problemen)
- HOMEASSISTANT_MQTT_INTEGRATION.md (bei MQTT-Problemen)

# DANN: Konfigurieren
nano .env
# GPS_SERIAL_PORT=/dev/ttyACM0
# MQTT_HOST=192.168.1.100
# MQTT_PORT=1883
# MQTT_USERNAME/PASSWORD (optional)

# DANN: Starten
systemctl --user start worx_gps_rec
journalctl --user -u worx_gps_rec -f
```

**Dokumentation nach Aufgabe:**

| Aufgabe | Datei | Sektion |
|---------|-------|---------|
| GPS-Modul Fehler | GPS_MODULE_HARDWARE_SETUP.md | Fehlerbehebung |
| MQTT Fehler | HOMEASSISTANT_MQTT_INTEGRATION.md | Troubleshooting |
| Installation auf Pi | RASPBERRY_PI_DEPLOYMENT.md | Installation auf Pi Zero |
| Service Setup | RASPBERRY_PI_DEPLOYMENT.md | Systemd Service |
| Troubleshooting | RASPBERRY_PI_DEPLOYMENT.md | Fehlerbehandlung |
| Web UI deployen | PROJECT_DOCUMENTATION.md | Web-Server Sektion |
| Tests durchführen | SERVER_TEST_REPORT.md | Test Ausführung |

---

### 🔧 **Ich muss Probleme beheben**
> Es funktioniert nicht!

**Gehen Sie so vor:**

```
1. Problem beschreiben
   ↓
2. "Troubleshooting" Sektion in RASPBERRY_PI_DEPLOYMENT.md lesen
   ↓
3. Befehl ausführen
   ↓
4. Logs prüfen: journalctl --user -u worx_gps_rec -f
   ↓
5. QUICK_REFERENCE.md für häufige Befehle nutzen
```

**Häufige Probleme:**

- MQTT Fehler → [RASPBERRY_PI_DEPLOYMENT.md#symptom-mqtt-connection-failed](RASPBERRY_PI_DEPLOYMENT.md)
- Service läuft nicht → [RASPBERRY_PI_DEPLOYMENT.md#symptom-service-bleibt-nicht-aktiv](RASPBERRY_PI_DEPLOYMENT.md)
- Keine GPS-Daten → [RASPBERRY_PI_DEPLOYMENT.md#symptom-keine-neuen-daten](RASPBERRY_PI_DEPLOYMENT.md)
- Pi wird heiß → [RASPBERRY_PI_DEPLOYMENT.md#symptom-pi-wird-heiß](RASPBERRY_PI_DEPLOYMENT.md)

---

### 🚀 **Ich will nur schnell anfangen**
> 5-Minuten Setup, keine Details

**Spickzettel:**

```bash
ssh nilsgollub@192.196.1.202
systemctl --user start worx_gps_rec.service
systemctl --user status worx_gps_rec.service
journalctl --user -u worx_gps_rec.service -f
```

[→ Weitere Schnell-Befehle in QUICK_REFERENCE.md](QUICK_REFERENCE.md)

---

## 📖 Alle Dokumentationsdateien

### Komplette Dokumentation

| Datei | Umfang | Zielgruppe | Inhalt |
|-------|--------|-----------|--------|
| **PROJECT_DOCUMENTATION.md** | 600 Zeilen | Alle | Gesamtübersicht, Architektur, APIs, Deployment |
| **RASPBERRY_PI_DEPLOYMENT.md** | 500 Zeilen | Developer/Ops | Pi Setup, Systemd, Troubleshooting |
| **QUICK_REFERENCE.md** | 300 Zeilen | schnelle Referenz | Cheat Sheet, häufige Befehle |
| **SERVER_TEST_REPORT.md** | 100 Zeilen | QA/Testing | Test-Ergebnisse, 29/29 Tests ✅ |
| **TESTING_GUIDE.md** | 150 Zeilen | Testing | Wie Tests laufen, Coverage |
| **TEST_STRUCTURE.md** | 200 Zeilen | Test-Architekten | Test-Organisation, Patterns |
| **TESTING_SUMMARY.md** | 200 Zeilen | Executive | Test Zusammenfassung |

### Konfigurationsdateien

| Datei | Zweck | Verwendung |
|-------|-------|-----------|
| **systemd_worx_gps_rec.service** | Systemd Service | Copy to `~/.config/systemd/user/` |
| **.env** | Environment-Variablen | Erstellen & ausfüllen |
| **config.py** | Python-Konfiguration | Im Projekt enthalten |
| **requirements.txt** | Python Dependencies | `pip install -r requirements.txt` |

---

## 🔍 Nach Thema suchen

### Installation & Setup
- [Voraussetzungen](PROJECT_DOCUMENTATION.md#voraussetzungen)
- [Installation auf Pi](PROJECT_DOCUMENTATION.md#installation-auf-raspberry-pi)
- [Systemd Service](RASPBERRY_PI_DEPLOYMENT.md#schritt-5-systemd-service-autostart)

### Verwendung & Betrieb
- [Dashboard öffnen](PROJECT_DOCUMENTATION.md#2-öffnen-sie-das-web-dashboard)
- [API Endpoints](PROJECT_DOCUMENTATION.md#-api-referenz)
- [Systemd Commands](QUICK_REFERENCE.md#-systemd-service)

### Überwachung & Monitoring
- [Status prüfen](RASPBERRY_PI_DEPLOYMENT.md#-überprüfung---läuft-alles)
- [Logs ansehen](RASPBERRY_PI_DEPLOYMENT.md#test-2-logs-ansehen)
- [Daten prüfen](RASPBERRY_PI_DEPLOYMENT.md#test-3-daten-werden-gespeichert)

### Fehlerbehandlung
- [Troubleshooting](RASPBERRY_PI_DEPLOYMENT.md#-fehlerbehandlung)
- [MQTT Fehler](RASPBERRY_PI_DEPLOYMENT.md#symptom-mqtt-connection-failed)
- [Service Fehler](RASPBERRY_PI_DEPLOYMENT.md#symptom-service-bleibt-nicht-aktiv)

### Entwicklung & Testing
- [Tests laufen](SERVER_TEST_REPORT.md)
- [Test-Strukturen](TEST_STRUCTURE.md)
- [API testen](QUICK_REFERENCE.md#-testing--debugging)

---

## 🏗️ Projektstruktur

```
Worx_GPS/
│
├─ 📚 DOKUMENTATION (Sie sind hier!)
│  ├─ PROJECT_DOCUMENTATION.md      ← Komplette Projektübersicht
│  ├─ RASPBERRY_PI_DEPLOYMENT.md    ← Pi Setup & Betrieb
│  ├─ QUICK_REFERENCE.md            ← Schnelle Referenz
│  ├─ SERVER_TEST_REPORT.md         ← Test-Ergebnisse
│  ├─ TESTING_GUIDE.md              ← Test-Ausführung
│  └─ ...weitere Test-Docs
│
├─ ⚙️ KONFIGURATION
│  ├─ systemd_worx_gps_rec.service  ← Systemd Service
│  ├─ .env                          ← Umgebungsvariablen
│  ├─ config.py                     ← Python Config
│  └─ requirements.txt              ← Dependencies
│
├─ 🔴 RASPBERRY PI CODE (Main)
│  ├─ Worx_GPS_Rec.py               ← Hauptprogramm (MUSS auf Pi)
│  ├─ gps_handler.py                ← GPS Parser
│  ├─ mqtt_handler.py               ← MQTT Client
│  ├─ data_recorder.py              ← Speicherung
│  └─ problem_detection.py          ← Anomalieerkennung
│
├─ 🌐 WEB SERVER CODE (Optional auf Pi)
│  ├─ web_ui/webui.py               ← Flask Server
│  ├─ live_gps_map_server.py        ← Live Maps
│  └─ web_ui/*.py                   ← Services
│
├─ 💾 DATA (Auf Pi)
│  ├─ data/maehvorgang_*.json       ← Fahrtdaten
│  └─ data/problemzonen.json        ← Probleme
│
├─ 🗺️ OUTPUT (Server)
│  └─ heatmaps/                     ← Generierte Karten
│
├─ 🧪 TESTS
│  ├─ test_servers.py               ← 23 Tests
│  └─ test_server_startup_validation.py ← 6 Tests
│
└─ 🎨 FRONTEND
   └─ frontend/                     ← React App
```

---

## ⚡ Schnelle Navigation

### Ich brauche nur EINES:

**Schnelle Lösung**
```
→ QUICK_REFERENCE.md
```

**Komplette Erklärung**
```
→ PROJECT_DOCUMENTATION.md
```

**Pi einrichten**
```
→ RASPBERRY_PI_DEPLOYMENT.md
```

**Probleme beheben**
```
→ RASPBERRY_PI_DEPLOYMENT.md → Troubleshooting
```

**Tests prüfen**
```
→ SERVER_TEST_REPORT.md
```

---

## 🎓 Lernpfade

### Anfänger (30 Minuten)
1. PROJECT_DOCUMENTATION.md (Abschnitte: Übersicht, Architektur)
2. QUICK_REFERENCE.md (Systemd Service)
3. RASPBERRY_PI_DEPLOYMENT.md (Schnelstart)

### Fortgeschrittene (1 Stunde)
1. PROJECT_DOCUMENTATION.md (alles)
2. RASPBERRY_PI_DEPLOYMENT.md (alles)
3. TEST Structure (TEST_STRUCTURE.md)
4. CODE Review (im IDE)

### Experte (2 Stunden)
1. Alle Dokumentationen durchlesen
2. Tests durchführen (test_servers.py)
3. Code durchgehen
4. Deployment simulieren

---

## 🔗 Externe Links

### Dokumentationen
- [Flask Dokumentation](https://flask.palletsprojects.com/)
- [MQTT Protokoll](https://mqtt.org/)
- [React Dokumentation](https://react.dev/)
- [Systemd Dokumentation](https://www.freedesktop.org/wiki/Software/systemd/)

### Tools
- [Mosquitto MQTT](https://mosquitto.org/) - MQTT Broker
- [Raspberry Pi Setup](https://www.raspberrypi.com/documentation/) - Pi Docs
- [Python venv](https://docs.python.org/3/library/venv.html) - Virtual Environment

---

## ✅ Verifikations-Checklisten

### Deployment Checkliste
- [ ] SSH funktioniert: `ssh nilsgollub@192.168.1.202 "echo OK"`
- [ ] Python venv aktiv: `source .venv/bin/activate`
- [ ] Dependencies OK: `pip list | grep flask`
- [ ] .env konfiguriert: `cat .env`
- [ ] Service läuft: `systemctl --user status worx_gps_rec`
- [ ] Daten ankommen: `mosquitto_sub -h 192.168.1.100 -t "worx/gps"`
- [ ] Daten gespeichert: `ls ~/Worx_GPS/data/`

### Test Checkliste
- [ ] Server Tests: `pytest tests/test_servers.py -v` → 29 ✅
- [ ] Validation Tests: `pytest tests/test_server_startup_validation.py -v` → 6 ✅
- [ ] Integration Tests: Dashboard öffnet sich
- [ ] API Tests: `curl http://localhost:5000/api/status` → 200

---

## 🆘 Hilfe

**Dokumentation nicht klar?**
→ PROJECT_DOCUMENTATION.md - Glossar

**Befehle vergessen?**
→ QUICK_REFERENCE.md - Cheat Sheet

**Error Message?**
→ RASPBERRY_PI_DEPLOYMENT.md - Fehlerbehandlung

**Test fehlgeschlagen?**
→ SERVER_TEST_REPORT.md oder TEST_STRUCTURE.md

---

## 📞 Support

**Für weitere Fragen:**

1. **Logs prüfen** (90% der Probleme)
   ```bash
   journalctl --user -u worx_gps_rec -f
   ```

2. **MQTT testen** (Konnektivität)
   ```bash
   mosquitto_sub -h 192.168.1.100 -t "worx/#" -v
   ```

3. **Systemd Status** (Service gesundheit)
   ```bash
   systemctl --user status worx_gps_rec
   ```

4. **Dokumentation durchsuchen**
   - Ctrl+F in der Markdown-Datei

---

## 📊 Dokumentations-Statistiken

```
Gesamte Dokumentation: ~2500 Zeilen
├─ Projektdokumentation: 600 Zeilen
├─ Deployment Guide: 500 Zeilen
├─ Schnell-Referenz: 300 Zeilen
├─ Test-Docs: 400 Zeilen
└─ Diese Übersicht: 200 Zeilen

Abgedeckte Themen:
✅ Architektur
✅ Installation
✅ Konfiguration
✅ Betrieb
✅ Monitoring
✅ Troubleshooting
✅ APIs
✅ Testing
✅ Deployment
✅ Best Practices
```

---

**Version**: 1.0  
**Erstellt**: 2026-03-17  
**Status**: ✅ Vollständig & produktionsreif  

🎉 **Viel Erfolg mit Worx_GPS!**
