# 🚀 Worx_GPS Funktionscheck - Schnellanleitung

## Schritt 1: SSH zum Pi verbinden

```bash
ssh nilsgollub@192.168.1.202
# Passwort: JhiswenP3003!
```

## Schritt 2: Diagnose durchführen (Copy-Paste diese Befehle)

### 1️⃣ System-Informationen
```bash
cd ~/Worx_GPS && echo "=== SYSTEM ===" && hostname && uname -r && python3 --version
```

**Erwartetes Ergebnis:**
```
=== SYSTEM ===
raspi-zero-worx
5.15.x-xxx
Python 3.9.x
```

---

### 2️⃣ Speicher & Disk
```bash
echo "=== DISK ===" && df -h / | tail -1 && echo "" && echo "=== MEMORY ===" && free -h | tail -1
```

**Erwartetes Ergebnis:**
- Disk: Mindestens 10% frei (>100MB)
- Memory: Mindestens 50MB frei

---

### 3️⃣ GPS-Modul (KRITISCH!)
```bash
echo "=== GPS PORTS ===" && ls -la /dev/ttyACM* 2>/dev/null || ls /dev/ttyUSB* 2>/dev/null || echo "❌ KEIN GPS-MODUL GEFUNDEN!"
```

**Was bedeutet welche Ausgabe:**
- ✅ `/dev/ttyACM0` gefunden → GPS-Modul aktiv
- ⚠️ `/dev/ttyUSB0` statt ttyACM0 → Anderes USB-Device, aber OK wenn es Daten gibt
- ❌ Keine Ausgabe → GPS-Modul nicht verbunden!

---

### 4️⃣ Service Status
```bash
echo "=== SERVICE STATUS ===" && systemctl --user status worx_gps_rec.service --no-pager
```

**Erwartetes Ergebnis:**
```
● worx_gps_rec.service - Worx GPS Recording Service
     Loaded: loaded (/home/nilsgollub/.config/systemd/user/worx_gps_rec.service; enabled; vendor preset: disabled)
     Active: active (running) since ...
```

Wenn nicht aktiv:
```bash
systemctl --user start worx_gps_rec.service
```

---

### 5️⃣ GPS-Daten empfangen (TEST)
```bash
echo "=== TEST GPS DATEN ===" && timeout 3 cat /dev/ttyACM0 | head -5
```

**Erwartete Ausgabe:**
```
$GPRMC,142530.00,A,4807.40338,N,01151.05234,E,0.040,0.00,170226,,,A*72
$GPGGA,142530.00,4807.40338,N,01151.05234,E,1,08,1.50,500.1,M,46.9,M,,*68
```

Wenn **keine Ausgabe**: GPS-Modul sendet nicht → Kabel/Treiber prüfen

---

### 6️⃣ Service-Logs (Fehler prüfen)
```bash
echo "=== LETZTE 20 LOG-ZEILEN ===" && journalctl --user -u worx_gps_rec.service -n 20 --no-pager
```

**Auf folgende Fehler prüfen:**
- ❌ `serial.SerialException` → GPS-Treiber Problem
- ❌ `mqtt.Connection` → MQTT-Broker nicht erreichbar
- ✅ Keine ERROR/Exception → Alles OK!

---

### 7️⃣ Daten werden gespeichert? (KRITISCH!)
```bash
echo "=== FAHRTDATEN ===" && ls -lh data/maehvorgang*.json 2>/dev/null | tail -5 || echo "❌ KEINE FAHRTDATEN!"
echo "" && echo "=== PROBLEMZONEN ===" && ls -lh data/problemzonen.json 2>/dev/null || echo "ℹ️  Noch keine Problemzonen erkannt"
```

**Erwartetes Ergebnis:**
```
-rw-r--r-- 1 nilsgollub nilsgollub 2.3M Mar 17 14:23 data/maehvorgang_2026-03-17_14.json
-rw-r--r-- 1 nilsgollub nilsgollub 150K Mar 17 14:20 data/maehvorgang_2026-03-17_13.json
```

Wenn keine Dateien: Service läuft aber speichert nicht → Logs prüfen

---

### 8️⃣ MQTT-Broker erreichbar?
```bash
echo "=== MQTT BROKER TEST ===" && timeout 2 bash -c "cat > /dev/null < /dev/tcp/192.168.1.100/1883" && echo "✅ MQTT Broker erreichbar" || echo "❌ MQTT nicht erreichbar!"
```

---

### 9️⃣ Virtuelle Umgebung prüfen
```bash
echo "=== VENV ===" && test -d .venv && echo "✅ Virtual Environment OK" || echo "⚠️ VENV fehlt, neinstallieren mit: ./setup.sh"
```

---

### 🔟 Letzte 5 Einträge aus aktueller Datendatei
```bash
echo "=== LIVE DATEN ===" && tail -c 500 data/maehvorgang*.json 2>/dev/null | tail -1
```

**Erwartete Struktur:**
```json
{"timestamp": "2026-03-17T14:23:46", "latitude": 48.1234, "longitude": 11.5678, "satellites": 8, "mower_status": "mowing"}
```

---

## Komponenten-Check Zusammenfassung

| Komponente | Status | Befehl |
|-----------|--------|--------|
| System läuft | ✅/❌ | `hostname` |
| Disk frei | ✅/❌ | `df -h /` |
| Memory OK | ✅/❌ | `free -h` |
| **GPS-Modul** | ✅/❌ | `ls /dev/ttyACM0` |
| **Service läuft** | ✅/❌ | `systemctl --user status worx_gps_rec.service` |
| **GPS-Daten kommen** | ✅/❌ | `timeout 3 cat /dev/ttyACM0` |
| **Daten werden gespeichert** | ✅/❌ | `ls data/maehvorgang*.json` |
| MQTT erreichbar | ✅/❌ | `bash -c "cat > /dev/null < /dev/tcp/192.168.1.100/1883"` |

---

## 🚨 Wenn etwas nicht funktioniert:

### Problem: GPS-Modul nicht gefunden
```bash
# Schritt 1: USB-Geräte auflisten
lsusb

# Schritt 2: Alle seriellen Ports anschauen
ls -la /dev/tty*

# Schritt 3: Dmesg für Fehler prüfen
dmesg | tail -20
```

### Problem: Service nicht aktiv
```bash
# Service starten
systemctl --user start worx_gps_rec.service

# Logs prüfen
journalctl --user -u worx_gps_rec.service -f
```

### Problem: GPS-Daten kommen nicht
```bash
# Manuelle GPS-Daten lesen (2 Sekunden)
timeout 2 cat /dev/ttyACM0

# Oder mit hexdump (um Encoding zu prüfen)
timeout 2 hexdump -C /dev/ttyACM0 | head -5
```

### Problem: Keine Fahrtdaten gespeichert
```bash
# 1. Service-Status
systemctl --user status worx_gps_rec.service

# 2. Dateiberechtigungen prüfen
ls -la data/

# 3. Logs detailliert
journalctl --user -u worx_gps_rec -n 100 --no-pager | grep -i "error\|exception\|traceback"

# 4. Manuell einen Testlauf starten
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py
```

---

## ✅ Erfolgs-Kriterien (alles muss GRÜN sein)

- [ ] ✅ Hostname & Kernel-Version angezeigt
- [ ] ✅ Disk: >10% frei
- [ ] ✅ Memory: >50MB frei  
- [ ] ✅ GPS-Modul unter `/dev/ttyACM0` (oder `/dev/ttyUSB0`)
- [ ] ✅ Service läuft: `active (running)`
- [ ] ✅ GPS-Daten empfangen: NMEA-Sätze sichtbar
- [ ] ✅ Fahrtdaten vorhanden: `data/maehvorgang_*.json` existiert
- [ ] ✅ Letzte 5 Minuten: Datei-Timestamp aktuell
- [ ] ✅ MQTT-Broker erreichbar

---

## 📋 Report für Support

Wenn du Support brauchst, gib folgende Infos an:

```bash
echo "=== DIAGNOSEBERICHT ===" && \
echo "Hostname: $(hostname)" && \
echo "Kernel: $(uname -r)" && \
echo "Python: $(python3 --version)" && \
echo "Disk frei: $(df -h / | tail -1 | awk '{print $4}')" && \
echo "Memory frei: $(free -h | tail -1 | awk '{print $7}')" && \
echo "GPS-Port: $(ls /dev/ttyACM* 2>/dev/null || ls /dev/ttyUSB* 2>/dev/null || echo 'NICHT GEFUNDEN')" && \
echo "Service: $(systemctl --user is-active worx_gps_rec.service)" && \
echo "Daten: $(ls -1 data/maehvorgang*.json 2>/dev/null | wc -l) Dateien" && \
echo "Letzte Änderung: $(stat -c %y data/maehvorgang*.json 2>/dev/null | tail -1)"
```

---

**Erstellt:** 2026-03-17  
**Für:** Worx_GPS Raspberry Pi Zero  
**Version:** 1.0
