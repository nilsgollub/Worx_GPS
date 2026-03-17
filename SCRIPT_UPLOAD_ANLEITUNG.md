# 🚀 SCRIPTS UPLOAD ZUM RASPBERRY PI - SOFORT-ANLEITUNG

## ⚡ Schnellste Methode (Copy-Paste)

### Schritt 1: SSH zum Pi
```bash
ssh nilsgollub@192.168.1.202
# Passwort: JhiswenP3003!
```

### Schritt 2: Ins Worx_GPS Verzeichnis
```bash
cd ~/Worx_GPS
```

### Schritt 3: Script mit cat schreiben

**Option A: run_funktionscheck.sh hochladen**

Öffne [run_funktionscheck.sh](run_funktionscheck.sh) in einem Editor, kopiere den GESAMTEN Inhalt, dann auf dem Pi im Terminal:

```bash
cat > run_funktionscheck.sh << 'EOF'
[HIER DEN KOMPLETTEN INHALT VON run_funktionscheck.sh EINFÜGEN]
EOF
chmod +x run_funktionscheck.sh
```

**Option B: check_raspi.sh hochladen**

```bash
cat > check_raspi.sh << 'EOF'
[HIER DEN KOMPLETTEN INHALT VON check_raspi.sh EINFÜGEN]
EOF
chmod +x check_raspi.sh
```

### Schritt 4: Datei kommt an prüfen
```bash
ls -la *.sh | grep funktionscheck
# Sollte anzeigen: -rwxr-xr-x ... run_funktionscheck.sh
```

### Schritt 5: FUNKTIONSCHECK DURCHFÜHREN!
```bash
bash run_funktionscheck.sh
```

---

## 📌 Noch einfacher: Nano Editor verwenden

```bash
# 1. Nano öffnen
nano run_funktionscheck.sh

# 2. Mit Ctrl+Shift+V einfügen (Windows Terminal)
#    oder Cmd+V (Mac)

# 3. Mit Ctrl+X speichern, dann Y + Enter

# 4. Ausführbar machen
chmod +x run_funktionscheck.sh

# 5. Run!
bash run_funktionscheck.sh
```

---

## 🔄 Alternative: Per Vi Editor

```bash
vi run_funktionscheck.sh
# i drücken (insert mode)
# Content einfügen
# Esc drücken
# :wq eingeben + Enter
chmod +x run_funktionscheck.sh
bash run_funktionscheck.sh
```

---

## 🎯 Was nach Upload die Ausgabe sein sollte:

```
╔════════════════════════════════════════════════════════════╗
║         WORX_GPS FUNKTIONSCHECK - ALLE TESTS              ║
║    (3-5 Minuten, alles auf einmal durchlaufen)            ║
╚════════════════════════════════════════════════════════════╝

1️⃣  SYSTEM INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
raspi-zero-worx
5.15.76-v7+
Python 3.9.2

2️⃣  DISK & SPEICHER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/dev/root (3.2G frei / 29.2G verwendet)
7.9G frei / 7.9G gesamt

[... weitere Checks ...]

✅ Bestandene Checks: 9/9
🎉 ALLES GRÜN! System läuft einwandfrei!
```

---

## ⚠️ Häufige Probleme

### Problem: "bash: run_funktionscheck.sh: No such file or directory"
**Lösung**: Datei wurde nicht korrekt geschrieben. Prüfe mit `ls -la` ob die Datei da ist.

### Problem: "Permission denied"
**Lösung**: Vergessen die Datei ausführbar zu machen:
```bash
chmod +x run_funktionscheck.sh
```

### Problem: Einfügzeit ist sehr lang oder Script antwortet nicht
**Lösung**: Das ist normal bei großen Dateien. Warte 10-20 Sekunden.

### Problem: SSH fragt immer wieder nach Passwort
**Lösung**: Das ist normal. Gib immer: `JhiswenP3003!` ein

---

## ✅ Checkliste vor dem Start

- [ ] SSH zum Pi funktioniert
- [ ] Im richtigen Verzeichnis: `pwd` zeigt `/home/nilsgollub/Worx_GPS`
- [ ] Editor-Fenster offen mit run_funktionscheck.sh
- [ ] Terminal-Fenster offen beim Pi
- [ ] Bereit zum Kopieren & Einfügen

---

## 🎓 Datei-Inhalt kopieren - SCHRITT FÜR SCHRITT

### Auf deinem Rechner:
1. Öffne `run_funktionscheck.sh` in VS Code, Notepad++ oder Editor
2. Markiere ALLES (Ctrl+A)
3. Kopiere (Ctrl+C)

### Auf dem Raspberry Pi (SSH Terminal):
```bash
cat > run_funktionscheck.sh << 'EOF'
```

4. Füge ALLES ein (Ctrl+Shift+V oder Cmd+V)
5. Drücke Enter nach der letzten Zeile
6. Tippe: `EOF`
7. Drücke Enter nochmal

Dann solltest du wieder zum prompt kommen:
```
nilsgollub@raspi-zero-worx:~/Worx_GPS$
```

---

**Bereit?** Start: `bash run_funktionscheck.sh`
