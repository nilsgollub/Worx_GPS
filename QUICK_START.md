# 🚀 QUICK START - Worx_GPS Funktionscheck

## ⚡ VORSCHRITT: Scripts auf dem Pi hochladen

Die Diagnose-Scripts müssen zuerst auf den Pi übertragen werden.

**→ Lese zuerst: [SCRIPT_UPLOAD_ANLEITUNG.md](SCRIPT_UPLOAD_ANLEITUNG.md)**

Kurz gefasst:
```bash
# 1. SSH zum Pi
ssh nilsgollub@192.168.1.202

# 2. Script hochladen (copy-paste die Inhalte)
cd ~/Worx_GPS
nano run_funktionscheck.sh  # Ctrl+Shift+V zum Einfügen

# 3. Ausführbar machen
chmod +x run_funktionscheck.sh
```

---

## ⚡ 30 Sekunden Schnelltest (NACH Upload)

Auf dem Raspberry Pi ausführen:

```bash
cd ~/Worx_GPS
systemctl --user status worx_gps_rec.service
```

**Erwartung**: `active (running)`

---

## 📋 5 Minuten Kompletter Check

```bash
# 1. Verbinde SSH
ssh nilsgollub@192.168.1.202
# Passwort: JhiswenP3003!

# 2. Ganze Diagnose auf einmal durchlaufen
cd ~/Worx_GPS && bash run_funktionscheck.sh
```

Das ist alles! Das Script zeigt dir **10 automatische Checks** mit Ergebnissen.

---

## 🛠️ Wenn etwas nicht ok ist

**→ Schau ins [FUNKTIONSCHECK_ANLEITUNG.md](FUNKTIONSCHECK_ANLEITUNG.md)**

- Problem-Lösungsanleitung
- Fehlerbehandlung
- Debugging-Tipps
- Erfolgs-Kriterien

---

## 📍 Datei-Übersicht

| Datei | Zweck | Zeit |
|--------|-------|------|
| `run_funktionscheck.sh` | Automatisierter Check aller Komponenten | 3 min |
| `FUNKTIONSCHECK_ANLEITUNG.md` | Detaillierte Schritt-für-Schritt Anleitung | 15 min |
| `DEBUG_CHECKLIST_SSH.md` | Erweiterte Diagnose wenn Probleme auftreten | 20 min |

---

## ✅ Erfolgs-Kriterien

Alle dieser Punkte müssen GRÜN sein:

```
✅ System läuft (Hostname angezeigt)
✅ Disk >10% frei
✅ Memory >50MB frei
✅ GPS-Modul unter /dev/ttyACM0
✅ Service läuft (active)
✅ GPS-Daten werden empfangen
✅ Fahrtdaten gespeichert (maehvorgang_*.json)
✅ MQTT erreichbar
✅ Keine Fehler in Logs
```

---

**Wichtigste Befehle:**

```bash
# Service-Status
systemctl --user status worx_gps_rec.service

# Neu starten
systemctl --user restart worx_gps_rec.service

# Logs live folgen
journalctl --user -u worx_gps_rec.service -f

# GPS-Daten direkt lesen
timeout 2 cat /dev/ttyACM0

# Daten anschauen
ls -lh ~/Worx_GPS/data/
```

---

**Erstellt**: 2026-03-17  
**Projekt**: Worx GPS RPi Zero  
**SSH-Host**: 192.168.1.202:22
