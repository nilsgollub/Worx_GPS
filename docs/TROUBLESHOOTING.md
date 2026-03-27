# Troubleshooting: Worx GPS Monitor Add-on

Dieses Dokument beschreibt bekannte Probleme und Lösungen bei der Installation und Nutzung des Home Assistant Add-ons.

---

## 1. WebUI zeigt "404: Not Found"
**Symptom:** Beim Öffnen des Add-ons in der Home Assistant Seitenleiste erscheint die Meldung "The requested URL was not found on the server".

### Ursache: Ingress Pfad-Konflikt
Home Assistant nutzt "Ingress", um das Web-Interface des Add-ons über einen sicheren Token-Pfad (z.B. `/api/hassio_ingress/xyz...`) erreichbar zu machen. Wenn das Backend (Flask) den Ingress-Präfix nicht korrekt entfernt oder die React Single-Page-Application (SPA) versucht, Routen aufzurufen, die Flask nicht kennt, wirft der Server einen 404-Fehler.

### Lösung (ab v2.6.8):
*   **Update:** Installiere mindestens Version **v2.6.8**. Diese Version enthält einen robusten "Catch-all Handler", der alle unbekannten Anfragen automatisch an die `index.html` des Frontends weiterleitet.
*   **Pfade:** Das Add-on sucht die Frontend-Dateien jetzt absolut unter `/app/frontend/dist`. Stelle sicher, dass beim Build/Kopieren dieser Ordner im Add-on vorhanden ist.
*   **Cache:** Falls nach einem Update immer noch 404 erscheint, leere den Browser-Cache oder drücke `Strg + F5`.

---

## 2. Add-on Update wird nicht angezeigt
**Symptom:** Du hast eine neue Version auf GitHub gesehen, aber Home Assistant zeigt kein Update an.

### Lösung:
1.  Gehe zu **Einstellungen** -> **Add-ons** -> **Add-on Store**.
2.  Klicke oben rechts auf das **Drei-Punkte-Menü**.
3.  Wähle **"Nach Updates suchen"** (Check for updates).
4.  Lade die Seite neu (`F5`).
5.  Der Supervisor braucht manchmal bis zu 10 Minuten, um die neue `config.yaml` von GitHub zu laden.

---

## 3. MQTT Verbindung fehlgeschlagen
**Symptom:** Dashbord zeigt "MQTT nicht verbunden" oder keine Live-Daten vom Mäher.

### Lösung:
*   **Host:** Nutze `core-mosquitto` als Hostname, wenn du das offizielle Mosquitto Add-on verwendest. Falls das nicht geht, trage die **interne IP** deines Home Assistant Servers ein.
*   **Credentials:** Falls du in Mosquitto keine speziellen User angelegt hast, lasse User/Passwort im Add-on leer (sofern "Allow anonymous" aktiv ist). Wir empfehlen jedoch einen dedizierten MQTT-User.
*   **Log-Check:** Schaue in die Add-on Logs nach Zeilen wie `MqttService - Verbinde mit...`.

---

## 4. Pi Zero antwortet nicht auf Befehle
**Symptom:** Buttons wie "Git Pull" oder "Restart" im Dashboard bewirken nichts auf dem Roboter.

### Lösung:
*   **MQTT-Topic:** Prüfe in der `config.py` auf dem Pi Zero, ob das Topic für Steuerung (`topic_control`) mit dem im Add-on übereinstimmt (Standard: `worx/control`).
*   **Pi-Dienst:** Stelle sicher, dass auf dem Pi Zero das Skript `Worx_GPS_Rec.py` läuft und auf MQTT-Nachrichten reagiert.
*   **Ping:** Der Pi Zero schickt alle 30-60 Sekunden einen Status-Ping. Wenn im Dashboard unter "System Info" bei "Pi Update" ein alter Zeitstempel steht, besteht keine Verbindung zum Pi.

---

## 5. Karten werden nicht geladen (Vollbild)
**Symptom:** Die Live-Karte im Dashboard funktioniert, aber die Vollbild-Links (`/live`, `/maps`) zeigen 404.

### Lösung:
*   Nutze die Navigation innerhalb der WebUI (links im Menü) statt die URL manuell einzutippen. Durch das Ingress-System von Home Assistant funktionieren direkte URL-Aufrufe ohne den Ingress-Token nicht.
*   Version **v2.6.5+** nutzt einen `HashRouter` im Frontend, was die Kompatibilität mit HA Ingress deutlich verbessert.

---

Stand: 27.03.2026 (v2.6.8)
