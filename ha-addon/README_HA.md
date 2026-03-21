# Worx GPS - Home Assistant Add-on Rollout 🏰🛰️

Dieses Projekt wurde so vorbereitet, dass es direkt als **lokales Add-on** in Home Assistant OS installiert werden kann.

### 📦 1. Installation (Lokal)
1.  Verbinde dich mit deinem Home Assistant Pi (via **Samba Share** oder **SSH & Web Terminal** Add-on).
2.  Navigiere zum Ordner `/addons/local`.
3.  Erstelle dort einen Unterordner `worx_gps_monitor`.
4.  Kopiere **ALLES** aus diesem Projekt-Hauptverzeichnis in diesen neuen Ordner (inkl. der Dateien aus `ha-addon/`).
    *   *Tipp:* Die Dateien `Dockerfile`, `config.yaml` und `run.sh` müssen im Hauptverzeichnis des Add-on-Ordners liegen, damit HA sie erkennt.

### 🚀 2. Aktivierung in HA
1.  Gehe in Home Assistant auf **Einstellungen** -> **Add-ons**.
2.  Klicke unten rechts auf **Add-on Store**.
3.  Wähle oben rechts das Drei-Punkte-Menü -> **Nach Updates suchen**.
4.  Unter "Local Add-ons" erscheint nun **Worx GPS Monitor**. 🏁🏎️
5.  Installiere das Add-on. 

### ⚙️ 3. Konfiguration
1.  Gib im Reiter "Konfiguration" deine MQTT-Daten ein.
    *   Standardmäßig ist `core-mosquitto` für den offiziellen HA MQTT Broker vorausgefüllt. ✨
2.  Starte das Add-on.
3.  Aktiviere **"In der Seitenleiste anzeigen"**, um dein Mäher-Dashboard jederzeit mit einem Klick zu öffnen! 🏎️💨🛰️🎯

### 📁 4. Daten-Management
Die Datenbank `worx_gps.db` und die Heatmaps werden im persistenten HA-Ordner `/data` gespeichert. Das bedeutet: Auch bei Add-on Updates bleiben deine Statistiken und Karten erhalten! 🕵️‍♂️🛰️🏁
