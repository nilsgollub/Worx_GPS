# Worx GPS - Home Assistant Add-on Rollout 🏰🛰️

Dieses Projekt wurde so vorbereitet, dass es direkt als **lokales Add-on** in Home Assistant OS installiert werden kann.

### 📦 1. Installation (Lokal)
1.  Verbinde dich mit deinem Home Assistant Pi (via **Samba Share** oder **SSH & Web Terminal** Add-on).
2.  Navigiere zum Ordner `/addons/local`.
3.  Erstelle dort einen Unterordner `worx_gps_monitor`.
4.  Kopiere **ALLES** aus diesem Projekt-Hauptverzeichnis in diesen neuen Ordner (inkl. der Dateien aus `ha-addon/`).
    *   *Tipp:* Die Dateien `Dockerfile`, `config.yaml` und `run.sh` müssen im Hauptverzeichnis des Add-on-Ordners liegen, damit HA sie erkennt.

### 🚀 2. Aktivierung & Bekanntes Problem ⚠️
1.  Gehe in Home Assistant auf **Einstellungen** -> **Add-ons**.
2.  Klicke unten rechts auf **Add-on Store**.
3.  Wähle oben rechts das Drei-Punkte-Menü -> **Nach Updates suchen**.
4.  Unter "Local Add-ons" erscheint nun **Worx GPS Monitor**. 🏎️
5.  Installiere das Add-on und starte es.

**WICHTIGER HINWEIS (Stand 21.03.2026):** 🚩
Die WebUI ist aktuell **NICHT** über den offiziellen HA-Knopf ("Benutzeroberfläche öffnen") erreichbar (Fehler: **404 Not Found**). Dieses Ingress-Problem ist bekannt. ✨📉 💔 

### ⚙️ 3. Konfiguration
1.  Gib im Reiter "Konfiguration" deine MQTT-Daten ein.
2.  **Lösung für den Zugriff:** Öffne die WebUI stattdessen direkt über die IP deines HA-Pis auf Port **5001**: `http://192.168.1.155:5001`.
3.  **WICHTIG:** Gehe zum Reiter "Netzwerk" im Add-on und trage rechts neben dem Port 5001 ebenfalls **`5001`** ein (statt 0/leer). Speichern und Add-on neu starten! ✨🛰️🏎️

### ⚠️ 5. Ingress-Fallstricke (Troubleshooting) 🕵️‍♂️🛰️
Falls das Dashboard (über "Benutzeroberfläche öffnen") einen **404 Not Found** oder einen **MIME-Type Error** (Browser-Konsole) zeigt, beachte folgende Punkte:

1.  **Browser Cache & Refresh:** 🚩
    Nach dem ersten Start oder Änderungen an der `config.yaml` muss die Home Assistant Seite oft mit **STRG + F5** (Hard Refresh) neu geladen werden, damit der Ingress-Tunnel erkannt wird.
2.  **Rebuild ist Pflicht:** 🏗️
    Wenn sich die `config.yaml` ändert (z.B. `ingress: true` hinzugefügt wird), reicht ein einfacher Neustart des Add-ons oft nicht aus. Klicke auf **"NEU ERSTELLEN" (Build)**, damit Home Assistant die neuen Metadaten übernimmt.
3.  **Vite Build (Relative Pfade):** 🏇
    Das React Frontend **muss** mit `base: './'` in der `vite.config.js` gebaut werden. Nur so finden die Assets (JS/CSS) ihren Weg durch den Home Assistant Tunnel. Ohne diesen Punkt suchen die Dateien fälschlicherweise an der Wurzel der Domain (Domain-Root) statt im Ingress-Unterordner.
4.  **MIME-Type Error:** 🕵️‍♂️
    Sollte die Browser-Konsole melden: `Expected a JS module script but the server responded with a MIME type of "text/html"`, dann liefert der Flask-Server die `index.html` anstelle der JS-Datei aus. Dies wird durch die automatische Ingress-Pfad-Korrektur in der `webui.py` verhindert – stelle sicher, dass die neueste Version aktiv ist! ✅ 

### 📁 6. Daten-Management
Die Datenbank `worx_gps.db` und die Heatmaps werden im persistenten HA-Ordner `/data` gespeichert. Das bedeutet: Auch bei Add-on Updates bleiben deine Statistiken und Karten erhalten! 🕵️‍♂️🛰️🏁
