# 🔍 Worx_GPS Debug-Checkliste (SSH Manuell)

**Datum**: 2026-03-17  
**Status**: SSH funktioniert zu 192.168.1.202 ✅  
**Nächster Schritt**: Folgende Befehle manuell im SSH-Terminal ausführen

---

## 🚀 Quick-Start Debug-Session

```bash
# 1. SSH-Verbindung herstellen
ssh nilsgollub@192.168.1.202
# Passwort eingeben: JhiswenP3003!

# ===== AB HIER IM SSH-TERMINAL: =====

# 2. Basis System-Info
echo "=== SYSTEM INFO ==="
uname -a
python3 --version
df -h

# 3. Ins Worx_GPS Verzeichnis
cd ~/Worx_GPS
pwd
ls -la | head -20

# 4. Virtual Environment prüfen
echo "=== VENV ===" 
ls -la .venv/bin/ | grep python
source .venv/bin/activate

# 5. GPS-Modul Status
echo "=== GPS-MODUL ==="
ls -la /dev/tty*
cat /dev/ttyACM0 | timeout 3 head -5
# Sollte NMEA-Daten zeigen: $GPGGA,..., $GPRMC,...

# 6. Service Status
echo "=== SERVICE ==="
systemctl --user status worx_gps_rec.service
systemctl --user is-active worx_gps_rec.service

# 7. Live-Logs ansehen
echo "=== LOGS (letzten 50 Zeilen) ==="
journalctl --user -u worx_gps_rec.service -n 50 --no-pager

# 8. Daten-Verzeichnis
echo "=== DATEN ==="
ls -lah data/
ls -lah data/maehvorgang*.json 2>/dev/null | tail -5

# 9. .env Konfiguration prüfen
echo "=== CONFIGURATION ==="
cat pi_env.txt | grep -E "GPS_|MQTT_"

# 10. MQTT Test
echo "=== MQTT TEST ==="
mosquitto_sub -h 192.168.1.100 -t "worx/#" -v -c -W 2 --max-lifetime 5 2>/dev/null || echo "MQTT nicht verfügbar"

# 11. Disk Space & Memory
echo "=== RESOURCES ==="
df -h /
free -h

# 12. Prozesse
echo "=== PROZESSE ==="
ps aux | grep -E "python|Worx"
```

---

## 📋 Was jede Sektion prüft

| Befehl | Was wird geprüft |
|--------|------------------|
| `uname -a` | Linux Kernel & Architektur |
| `python3 --version` | Python Installation |
| `ls /dev/tty*` | GPS-Modul Port verfügbar? |
| `cat /dev/ttyACM0` | GPS-Daten fließen? |
| `systemctl status` | Service aktiv? |
| `journalctl` | Fehler in Logs? |
| `ls data/` | Werden Daten gespeichert? |
| `cat pi_env.txt` | Konfiguration korrekt? |
| `mosquitto_sub` | MQTT Broker erreichbar? |
| `df -h` | Genug Speicherplatz? |
| `free -h` | RAM-Auslastung OK? |

---

## 🎯 Expected Output

### GPS-Modul OK:
```
$ cat /dev/ttyACM0 | timeout 2 head -3
$GPGGA,142345.000,4812.345,N,01145.678,E,1,08,0.9,545.4,M,46.9,M,,*47
$GPRMC,142345.000,A,4812.345,N,01145.678,E,022.4,084.4,170326,003.1,W*62
$GPGSA,A,3,04,05,09,12,24,,,,,,,2.5,1.3,2.1*30
```

### Service aktiv:
```
$ systemctl --user is-active worx_gps_rec.service
active
```

### Daten werden gespeichert:
```
$ ls -lah data/maehvorgang*.json | tail -2
-rw-r--r-- 1 nilsgollub nilsgollub 1.2M Mar 17 14:23 data/maehvorgang_2026-03-17_14.json
-rw-r--r-- 1 nilsgollub nilsgollub 3.4K Mar 17 14:20 data/problemzonen.json
```

### Logs zeigen normales Verhalten:
```
$ journalctl -u worx_gps_rec -n 5 --no-pager
Mar 17 14:23:45 WorxPi python[658]: 2026-03-17 14:23:45 - INFO - GPS Fix: qual=1, sats=8
Mar 17 14:23:46 WorxPi python[658]: 2026-03-17 14:23:46 - INFO - Data recorded: lat=48.12, lon=11.45
Mar 17 14:23:47 WorxPi python[658]: 2026-03-17 14:23:47 - INFO - Problem detector: OK
```

---

## ⚠️ Fehlersuche nach Symptom

### Problem: GPS-Modul nicht gefunden (`/dev/ttyACM0 nicht vorhanden`)

```bash
# Mögliche Lösungen:
ls /dev/ttyUSB*              # Ist es ttyUSB0 statt ttyACM0?
dmesg | tail -20            # Hat Kernel das Modul erkannt?
lsusb                       # Wird Modul als USB erkannt?

# .env korrigieren wenn nötig:
nano pi_env.txt
# Ändere: GPS_SERIAL_PORT=/dev/ttyUSB0
# Speichere & exit

# Service neu starten:
systemctl --user restart worx_gps_rec
```

### Problem: Service läuft nicht (`inactive`)

```bash
# Logs anschauen:
journalctl --user -u worx_gps_rec -n 100 -p ERR

# Service manuell starten:
source .venv/bin/activate
python3 Worx_GPS_Rec.py

# Sollte Fehler zeigen (z.B. "SerialException: No such device")
# Wenn Fehler kein GPS-Modul ist → ping mir (siehe unten)
```

### Problem: MQTT nicht verfügbar

```bash
# Prüfe Broker-Verbindung:
ping 192.168.1.100
mosquitto_pub -h 192.168.1.100 -t "test" -m "hello"

# Wenn nicht antwortet → MQTT Broker down oder IP falsch
# .env prüfen:
grep MQTT_HOST pi_env.txt
```

### Problem: Kein Speicherplatz

```bash
# Disk-Ausnutzung prüfen:
df -h /

# Wenn < 10% frei:
du -sh data/                     # Wie groß ist data Verzeichnis?
ls -laSh data/ | head -20        # Größte Dateien finden

# Archivieren & löschen (nur wenn Sie sicher sind!):
tar czf backup_$(date +%Y%m%d).tar.gz data/
rm data/maehvorgang_2026-03-0[1-5]*.json
```

---

## 📞 Debugging für Support

Falls Fehler vorkommen, sammles diese Infos:

```bash
# 1. Komplette Error-Log speichern
journalctl --user -u worx_gps_rec.service --no-pager > ~/error_log.txt

# 2. System-Dump
uname -a > ~/system_info.txt
python3 --version >> ~/system_info.txt
df -h >> ~/system_info.txt
free -h >> ~/system_info.txt

# 3. GPS-Modul Daten
cat /dev/ttyACM0 | timeout 5 head -20 > ~/gps_sample.txt

# 4. .env (ohne Passwörter!)
grep -v PASSWORD pi_env.txt > ~/config_safe.txt

# Diese Infos dann hochladen/teilen
ls -la ~/*.txt
```

---

## 🎯 Kritische Feststellen

| Item | Expected | Command |
|------|----------|---------|
| **GPS-Port** | `/dev/ttyACM0` sichtbar | `ls /dev/tty*` |
| **GPS-Daten** | NMEA-Strings (`$GPGGA...`) | `cat /dev/ttyACM0 \| head -3` |
| **Service** | `active` | `systemctl --user status worx_gps_rec` |
| **Daten-Folder** | > 0 JSON-Dateien | `ls data/*.json` |
| **Disk-Space** | > 10% frei | `df -h /` |
| **Memory** | > 50MB frei | `free -h` |

---

## ✅ Checkliste: System ist OK wenn...

```
☐ cat /dev/ttyACM0 zeigt NMEA-Daten
☐ systemctl --user status worx_gps_rec = active
☐ journalctl zeigt keine ERROR/EXCEPTION
☐ ls data/ zeigt aktuelle JSON-Dateien (heute's Datum)
☐ df -h zeigt > 10% freien Speicher
☐ free -h zeigt > 50MB freies RAM
☐ mosquitto_sub verbindet sich zu MQTT Broker (optional)
```

Wenn alle ☑ = **System läuft normal! ✅**

---

**Nach dieser Checkliste haben wir alle Info um Probleme zu diagnostizieren!**
