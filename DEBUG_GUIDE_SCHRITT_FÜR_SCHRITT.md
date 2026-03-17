# 🔍 DEBUGGING GUIDE - Worx_GPS Problembehebung

## Diagnose-Ergebnisse zusammengefasst
```
✅ System läuft (WorxPi, Python 3.11.2)
⚠️  Disk OK (48GB frei)
❌ GPS-Modul NICHT GEFUNDEN
❌ Service NICHT AKTIV
❌ MQTT nicht erreichbar
❌ Keine Fahrtdaten
```

---

## 🎯 Debug-Plan (Priorität)

### 1️⃣ GPS-MODUL - KRITISCH!

**Problem**: `/dev/ttyACM0` nicht gefunden

**Debug-Schritte:**

```bash
# Schritt 1: Alle USB/Serial Geräte auflisten
lsusb
# Sollte GPS-Modul anzeigen (z.B. "Prolific Technology Inc. PL2303 Serial Port")

# Schritt 2: Verfügbare Serial Ports prüfen
ls -la /dev/tty*
# Suche nach: ttyACM0, ttyUSB0, ttyS0

# Schritt 3: Dmesg nach Geräte-Fehlern
dmesg | tail -30 | grep -i "usb\|serial\|tty\|pl2303"

# Schritt 4: Kernel-Module prüfen
lsmod | grep -i "pl2303\|usb\|serial"

# Schritt 5: Berechtigung prüfen
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
# Sollte Besitzer sein: dialout group
```

**Was bedeuten die Ergebnisse:**
- ✅ `ttyACM0` oder `ttyUSB0` in `/dev/` → GPS-Modul erkannt
- ❌ `Keine Geräte` → USB-Kabel nicht verbunden oder Treiber fehlt
- ⚠️ `Berechtigungen denied` → User braucht `dialout` Gruppe

**Lösung wenn nicht erkannt:**
```bash
# 1. Kabel prüfen - USB-Modul physical disconnect/reconnect
sudo dmesg -w  # Live-Sehen wenn Modul angesteckt wird

# 2. Treiber prüfen (für PL2303)
sudo apt-get install -y pl2303-modules  # Falls nötig

# 3. User zur dialout-Gruppe hinzufügen
sudo usermod -a -G dialout nilsgollub
# DANN NEUES TERMINAL ÖFFNEN!
```

---

### 2️⃣ SERVICE STATUS - WICHTIG!

**Problem**: `worx_gps_rec.service` ist `inactive`

**Debug-Schritte:**

```bash
# Schritt 1: Service-Datei existiert?
systemctl --user list-unit-files | grep worx

# Schritt 2: Service-Datei location
cat ~/.config/systemd/user/worx_gps_rec.service

# Schritt 3: Service starten
systemctl --user start worx_gps_rec.service

# Schritt 4: Fehler prüfen
systemctl --user status worx_gps_rec.service -l

# Schritt 5: Logs detailliert
journalctl --user -u worx_gps_rec.service -n 50 --no-pager

# Schritt 6: Manuell starten (zum Debuggen)
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py
# Hier sehen wir die echten Fehler!
```

**Häufige Fehler:**
- `ModuleNotFoundError: pynmea2` → Dependencies nicht installiert
- `Serial port not found` → GPS-Modul physisch nicht verbunden
- `MQTT Connection refused` → MQTT-Broker nicht erreichbar
- `Permission denied /dev/ttyACM0` → User-Berechtigungen

---

### 3️⃣ MQTT BROKER - WICHTIG!

**Problem**: MQTT nicht zu 192.168.1.100:1883 erreichbar

**Debug-Schritte:**

```bash
# Schritt 1: Ist der MQTT-Host richtig?
cat config.py | grep -i "MQTT"
# oder
cat pi_env.txt | grep -i "MQTT_HOST"

# Schritt 2: Host erreichbar?
ping 192.168.1.100

# Schritt 3: Port offen?
nc -zv 192.168.1.100 1883
# oder
timeout 2 bash -c "cat > /dev/null < /dev/tcp/192.168.1.100/1883" && echo "OK" || echo "CLOSED"

# Schritt 4: MQTT Service prüfen (falls MQTT auf PI läuft)
ps aux | grep -i mosquitto

# Schritt 5: Mit mosquitto_sub testen
mosquitto_sub -h 192.168.1.100 -t "worx/#" -u <user> -P <pass>
# (Ctrl+C zum Abbrechen)
```

**Lösungsansätze:**
- IP falsch? → Netzwerk-Check: `ip addr`
- Host firewall blockiert? → `sudo ufw status`
- MQTT-Broker offline? → HomeAssistant auf 192.168.1.100 checken
- Passwort falsch? → Config aktualisieren

---

### 4️⃣ ABHÄNGIGKEITEN - WICHTIG!

**Problem**: Vielleicht sind Python-Module nicht installiert

**Debug-Schritte:**

```bash
# Schritt 1: Virtual Environment aktivieren
cd ~/Worx_GPS
source .venv/bin/activate

# Schritt 2: Requirements installieren
pip install -r requirements.txt

# Schritt 3: Spezifische Module prüfen
python3 -c "import pynmea2; print('✅ pynmea2 OK')"
python3 -c "import paho.mqtt.client; print('✅ paho-mqtt OK')"
python3 -c "import serial; print('✅ pyserial OK')"
python3 -c "import flask; print('✅ flask OK')"

# Schritt 4: Fehlende Module installieren
pip install pynmea2 paho-mqtt pyserial flask
```

---

## 🔧 SCHNELL-FIX REIHENFOLGE

### Minute 1-2: GPS-Modul Hardware prüfen
```bash
lsusb | grep -i prolific  # oder was auch immer dein GPS-Modul ist
# Wenn nicht da: Kabel reconnect
```

### Minute 3: Berechtigungen
```bash
sudo usermod -a -G dialout nilsgollub
# Neues Terminal öffnen!
```

### Minute 4: Dependencies
```bash
cd ~/Worx_GPS
source .venv/bin/activate
pip install -r requirements.txt
```

### Minute 5: MQTT hostname
```bash
cat config.py | grep MQTT_HOST
# Muss 192.168.1.100 sein (oder der richtige Host)
```

### Minute 6: Manueller Start
```bash
cd ~/Worx_GPS
source .venv/bin/activate
python3 Worx_GPS_Rec.py
# Beobachte die Ausgabe - Fehler sind jetzt sichtbar!
```

---

## ✅ DEBUGGING CHECKLISTE

Arbeite diese Punkte ab und berichte, wenn einen findet:

- [ ] GPS-Hardware physisch angeschlossen? (mit `lsusb` prüfen)
- [ ] GPS-Port sichtbar? (`ls /dev/ttyACM*` oder `ls /dev/ttyUSB*`)
- [ ] User in `dialout` Gruppe? (`groups` → sollte "dialout" enthalten)
- [ ] Python-Module installiert? (`python3 -c "import pynmea2"`)
- [ ] MQTT-Host erreichbar? (`ping 192.168.1.100` + `nc -zv 192.168.1.100 1883`)
- [ ] config.py/pi_env.txt hat richtige Einstellungen? (`cat config.py | grep -i mqtt`)
- [ ] Service-Datei existiert? (`systemctl --user list-unit-files | grep worx`)
- [ ] Manueller Start funktioniert? (`python3 Worx_GPS_Rec.py`)

---

## 🎯 NÄCHSTE SCHRITTE

1. **Sofort**: GPS-Hardware prüfen (`lsusb`)
2. **Dann**: Berechtigungen (`sudo usermod -a -G dialout nilsgollub`)
3. **Danach**: Dependencies (`pip install -r requirements.txt`)
4. **Dann**: Config prüfen (`cat config.py`)
5. **Dann**: Manueller Start (`python3 Worx_GPS_Rec.py`)
6. **Zuletzt**: Service starten (`systemctl --user start worx_gps_rec.service`)

---

**Was ist dein erstes Ergebnis von:**
```bash
lsusb | grep -i "prolific\|serial\|gps"
```

Gib mir die Ausgabe - dann können wir weitermachen!
