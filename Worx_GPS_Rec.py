# Worx_GPS_Rec.py
import sys
import logging
import serial
# import paho.mqtt.client as paho_mqtt_client # Nicht mehr direkt hier benötigt
from mqtt_handler import MqttHandler  # Annahme: MqttHandler behandelt Reconnects intern
from gps_handler import GpsHandler
from data_recorder import DataRecorder
from problem_detection import ProblemDetector
# PI_STATUS_CONFIG importieren
from config import REC_CONFIG, MQTT_CONFIG, PI_STATUS_CONFIG
import time
import subprocess

# psutil importieren (falls noch nicht geschehen)
try:
    import psutil

    PSUTIL_AVAILABLE = True # Use uppercase for constant
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.info( # Changed to info, warning might be too alarming if not needed
        "psutil nicht gefunden. Pi-Temperatur kann nicht gelesen werden. Installiere mit 'pip install psutil'")

# Logging konfigurieren
# Stelle sicher, dass das Level auf DEBUG steht, um alle Meldungen zu sehen
# In einer Produktionsumgebung vielleicht auf INFO setzen
log_level = logging.DEBUG if REC_CONFIG.get("debug_logging", False) else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


class WorxGpsRec:
    def __init__(self):
        """Initialisiert die Hauptanwendungsklasse."""
        self.test_mode = REC_CONFIG.get("test_mode", False)
        logging.info(f"Initialisiere WorxGpsRec (Testmodus: {self.test_mode})")

        # Instanziierung der Handler
        # MqttHandler sollte idealerweise die Reconnect-Logik kapseln
        self.mqtt_handler = MqttHandler(
            test_mode=self.test_mode,
            lwt_payload="recorder_offline" # Spezifisches LWT für den Recorder
        )
        self.gps_handler = GpsHandler()  # GpsHandler kümmert sich um serielle Verbindung
        self.data_recorder = DataRecorder(self.mqtt_handler)
        self.problem_detector = ProblemDetector(self.mqtt_handler)

        self.is_recording = False

        # MQTT-Callback setzen und Verbindung initiieren
        # Der Handler sollte _on_connect und _on_disconnect nutzen
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()  # connect() im Handler sollte Reconnects verwalten

        logging.info("WorxGpsRec initialisiert.")

    def on_mqtt_message(self, msg):
        """Verarbeitet eingehende MQTT-Nachrichten auf dem Kontroll-Topic."""
        # Sicherstellen, dass Payload dekodierbar ist
        try:
            payload = msg.payload.decode('utf-8')  # Explizit utf-8 verwenden
            logging.debug(f"Nachricht empfangen - Topic: '{msg.topic}', Payload: '{payload}'")
        except UnicodeDecodeError:
            logging.warning(f"Konnte Payload auf Topic '{msg.topic}' nicht als UTF-8 dekodieren.")
            return  # Verarbeitung abbrechen

        # Nur Nachrichten auf dem Kontroll-Topic verarbeiten
        if msg.topic != self.mqtt_handler.topic_control:
            logging.debug(f"Nachricht auf anderem Topic ignoriert: {msg.topic}")
            return

        # --- Befehlsverarbeitung ---
        mode_mapping = {
            "fakegps_on": "fake_route",
            "start_route": "fake_route",
            "stop_route": "fake_random",
            "random_points": "fake_random",
            "fakegps_off": "real"
        }

        # --- Korrigierte Befehlsnamen für die WebUI ---
        command_actions = {
            "START_REC": self.start_recording,
            "STOP_REC": self.stop_recording,
            "PROBLEM": self.send_problem_message,  # Behalte PROBLEM bei, falls es noch anders genutzt wird
            "SHUTDOWN": self.initiate_shutdown,
            # Füge die alten Befehle hinzu, falls sie noch von woanders kommen
            "start": self.start_recording,
            "stop": self.stop_recording,
            "problem": self.send_problem_message,
            "shutdown": self.initiate_shutdown
        }

        if payload in command_actions:
            action = command_actions[payload]
            logging.info(f"Führe Aktion für Befehl '{payload}' aus.")
            action()  # Rufe die entsprechende Methode auf
        elif payload in mode_mapping:
            new_mode = mode_mapping[payload]
            logging.info(f"Versuche GPS-Modus auf '{new_mode}' zu ändern (via '{payload}').")
            if not self.gps_handler.change_gps_mode(new_mode):
                logging.warning(f"Fehler beim Ändern des GPS-Modus auf '{new_mode}'.")
                # Optional: MQTT-Statusnachricht senden
                # self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, f"error_gps_mode_{new_mode}")
        else:
            logging.warning(f"Unbekannter Befehl empfangen: '{payload}'")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_command")

    def start_recording(self):
        """Startet den Aufnahmeprozess."""
        if not self.is_recording:
            self.is_recording = True
            self.data_recorder.clear_buffer()
            logging.info("Aufnahme gestartet.")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording started")
        else:
            logging.warning("Aufnahme läuft bereits, 'start'-Befehl ignoriert.")

    # --- GEÄNDERTE stop_recording ---
    def stop_recording(self):
        """Stoppt den Aufnahmeprozess, sendet die Daten und stößt AssistNow Update an."""
        if self.is_recording:
            self.is_recording = False
            logging.info("Aufnahme gestoppt. Sende gepufferte Daten...")
            # send_buffer_data sollte intern prüfen, ob MQTT verbunden ist
            # oder die Nachricht ggf. verwerfen/später versuchen
            self.data_recorder.send_buffer_data()
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording stopped")

            # --- NEU: AssistNow Update nach Mähvorgang anstoßen ---
            logging.info("Stoße AssistNow Update nach Mähvorgang an.")
            if self.gps_handler:
                try:
                    # Rufe check_assist_now mit force_update=True auf
                    # Die Methode gibt True zurück, wenn alles ok ist (auch wenn kein Update nötig war)
                    # und False, wenn ein Update versucht wurde und fehlschlug.
                    success = self.gps_handler.check_assist_now(force_update=True)
                    if success:
                        logging.info("Manuelles AssistNow Update erfolgreich (oder nicht nötig).")
                    else:
                        # Fehler wurde bereits im GpsHandler geloggt
                        logging.warning("Manuelles AssistNow Update fehlgeschlagen (siehe vorherige Logs).")
                except AttributeError:
                    # Falls die Methode aus irgendeinem Grund nicht existiert
                    logging.warning(
                        "GpsHandler hat keine Methode 'check_assist_now' oder unterstützt 'force_update' nicht.")
                except Exception as e:
                    # Fängt andere unerwartete Fehler während des Updates ab
                    logging.error(f"Unerwarteter Fehler beim Anstoßen des AssistNow Updates: {e}", exc_info=True)
            else:
                logging.warning("Kein GpsHandler verfügbar, um AssistNow Update anzustoßen.")
            # --- Ende NEU ---

        else:
            logging.warning("Aufnahme war nicht aktiv, 'stop'-Befehl ignoriert.")

    # --- ENDE GEÄNDERTE stop_recording ---

    def send_problem_message(self):
        """Sendet die letzte bekannte Position als 'Problem'-Nachricht."""
        # Hole die letzte bekannte Position direkt vom GPS-Handler
        gps_data = self.gps_handler.last_known_position
        if gps_data and 'lat' in gps_data and 'lon' in gps_data:
            # Stelle sicher, dass lat/lon gültige Zahlen sind (obwohl sie es sein sollten)
            try:
                lat = float(gps_data['lat'])
                lon = float(gps_data['lon'])
                problem_data = f"problem,{lat:.6f},{lon:.6f}"  # Formatierung für Konsistenz
                logging.info(f"Sende Problem-Nachricht: {problem_data}")
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, problem_data)
            except (ValueError, TypeError):
                logging.warning("Ungültige Lat/Lon-Werte in last_known_position gefunden.")
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps_invalid_pos")
        else:
            logging.warning("Keine gültigen GPS-Daten verfügbar, um Problem zu senden.")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps_no_pos")

    def initiate_shutdown(self):
        """Leitet den System-Shutdown ein."""
        logging.info("Shutdown-Befehl empfangen. Fahre Raspberry Pi herunter...")
        # Optional: Statusnachricht senden, bevor der Shutdown beginnt
        self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "shutdown initiated")
        time.sleep(1)  # Kurze Pause, damit die Nachricht gesendet werden kann

        try:
            # Verwende subprocess.run für bessere Fehlerbehandlung
            result = subprocess.run(
                ["sudo", "shutdown", "-h", "now"],
                check=False,  # Wirft keine Exception bei Return Code != 0
                capture_output=True,  # Fängt stdout/stderr auf
                text=True,  # Dekodiert Output als Text
                timeout=10  # Timeout für den Befehl
            )
            if result.returncode != 0:
                logging.error(
                    f"Fehler beim Ausführen des Shutdown-Befehls (Code {result.returncode}): {result.stderr.strip()}")
                # Sende Fehlermeldung, falls MQTT noch geht (unwahrscheinlich bei Shutdown-Fehler)
                # self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_shutdown_failed")
            else:
                logging.info("Shutdown-Befehl erfolgreich ausgeführt.")
                # Keine weitere Aktion möglich, System fährt herunter
        except FileNotFoundError:
            logging.error("Fehler: 'sudo' oder 'shutdown' Befehl nicht gefunden. Shutdown nicht möglich.")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_shutdown_cmd_not_found")
        except subprocess.TimeoutExpired:
            logging.error("Timeout beim Warten auf den Shutdown-Befehl.")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_shutdown_timeout")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Ausführen des Shutdown-Befehls: {e}", exc_info=True)
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_shutdown_unexpected")

    # --- NEUE HILFSFUNKTION zum Lesen der Temperatur ---
    def _get_cpu_temperature(self):
        """Liest die CPU-Temperatur des Raspberry Pi aus."""
        if not PSUTIL_AVAILABLE: # Use the constant
            return None  # psutil nicht verfügbar

        try:
            # Versuche, die Temperatur über psutil auszulesen
            # Dies funktioniert auf vielen Linux-Systemen, einschließlich Raspberry Pi OS
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                # Suche nach einem passenden Eintrag (Namen können variieren)
                for name, entries in temps.items():
                    # Bevorzugte Namen prüfen
                    if "cpu_thermal" in name or "coretemp" in name or "k10temp" in name or "cpu_temp" in name:
                        for entry in entries:
                            if entry.current:
                                return round(entry.current, 1)
                    # Fallback: Suche nach generischen Namen
                    for entry in entries:
                        if 'temp' in entry.label.lower() or 'cpu' in entry.label.lower():
                            if entry.current:
                                return round(entry.current, 1)

            # Fallback für ältere Systeme oder wenn sensors_temperatures nicht funktioniert
            # Versuche, die Temperatur aus /sys/class/thermal/thermal_zone0/temp zu lesen
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp_milli = int(f.read().strip())
                    return round(temp_milli / 1000.0, 1)
            except (FileNotFoundError, ValueError): # Add ValueError for robustness
                logging.debug("Fallback /sys/class/thermal/thermal_zone0/temp nicht gefunden.")
                pass  # Datei nicht gefunden, versuche nichts weiter
            except Exception as e:
                logging.warning(f"Fehler beim Lesen von /sys/class/thermal/thermal_zone0/temp: {e}")

            logging.warning("Konnte CPU-Temperatur nicht über psutil oder sysfs lesen.")
            return None
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Lesen der CPU-Temperatur: {e}", exc_info=True)
            return None

    # --- ENDE NEUE HILFSFUNKTION ---

    def main_loop(self):
        """Die Hauptschleife der Anwendung."""
        # Status-Intervall aus Config oder Standardwert
        gps_status_interval = MQTT_CONFIG.get("status_interval", 5)
        # Stelle sicher, dass beim ersten Durchlauf gesendet wird
        last_gps_status_send = time.monotonic() - gps_status_interval - 1
        logging.info(f"Hauptschleife gestartet. GPS-Status wird alle {gps_status_interval}s gesendet.")

        # --- NEU: Intervall und Zeitstempel für Pi-Temperatur ---
        pi_status_interval = PI_STATUS_CONFIG.get("pi_status_interval", 60)
        pi_status_topic = PI_STATUS_CONFIG.get("topic_pi_status")
        last_pi_status_send = time.monotonic() - pi_status_interval - 1

        logging.debug(f"Pi Status Topic: '{pi_status_topic}', psutil available: {PSUTIL_AVAILABLE}, Interval: {pi_status_interval}s")

        if pi_status_topic and PSUTIL_AVAILABLE:
            logging.info(f"Pi-Temperatur wird alle {pi_status_interval}s auf Topic '{pi_status_topic}' gesendet.")
        elif not PSUTIL_AVAILABLE:
            logging.warning("PSUTIL nicht verfügbar, Pi-Temperatur wird nicht gesendet.")
        else:
            logging.warning(
                "Kein Topic für Pi-Status definiert (MQTT_TOPIC_PI_STATUS), Temperatur wird nicht gesendet.")
        # --- ENDE NEU ---

        loop_counter = 0
        while True:
            loop_counter += 1
            current_time = time.monotonic()  # Monotonic für Zeitintervalle verwenden
            logging.debug(f"--- Start Hauptschleife Iteration {loop_counter} (Time: {current_time:.2f}) ---")

            try:
                # --- Offline Probleme prüfen & senden ---
                self.problem_detector.check_offline_problems()

                # --- MQTT Verbindung prüfen (optional, wenn Handler robust ist) ---
                # if not self.mqtt_handler.is_connected():
                #    logging.warning("MQTT nicht verbunden. Versuche erneute Verbindung (sollte automatisch erfolgen)...")
                #    # Kein manuelles connect() hier, der Handler sollte es tun.
                #    time.sleep(5) # Kurze Pause, wenn nicht verbunden
                #    continue # Nächste Iteration

                # --- GPS Daten holen ---
                # get_gps_data sollte intern Fehler behandeln (z.B. SerialException)
                # und None zurückgeben, wenn keine gültigen Daten verfügbar sind.
                gps_data = self.gps_handler.get_gps_data()
                logging.debug(f"GPS Data received in loop: {gps_data}")

                # --- Aufnahme-Logik ---
                if self.is_recording:
                    if gps_data and all(k in gps_data for k in ("lat", "lon")):
                        try:
                            # Send unconditionally - Backend does geofence/filtering
                            self.data_recorder.add_gps_data(gps_data)
                            self.problem_detector.add_position(gps_data)
                            logging.debug(f"GPS-Punkt aufgezeichnet: {gps_data}")
                        except Exception as e:
                            logging.error(f"Fehler bei Verarbeitung von GPS Daten {gps_data}: {e}", exc_info=True)
                    elif gps_data:
                        logging.warning(f"Empfangene GPS-Daten unvollständig (lat/lon fehlt): {gps_data}")
                    else:
                        logging.debug("Keine gültigen GPS-Daten (kein Fix?) während der Aufnahme erhalten.")
                # --- Ende Aufnahme-Logik ---

                # --- GPS Status senden ---
                if current_time - last_gps_status_send >= gps_status_interval:
                    logging.debug("Sende GPS-Status...")
                    # Hole den formatierten Status-String vom Handler
                    status_message = self.gps_handler.get_last_gga_status()
                    # Sende den Status (MqttHandler sollte intern prüfen, ob verbunden)
                    self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, status_message)
                    last_gps_status_send = current_time
                # --- Ende GPS Status senden ---

                # --- NEU: Pi-Temperatur senden ---
                if pi_status_topic and PSUTIL_AVAILABLE and (current_time - last_pi_status_send >= pi_status_interval):
                    logging.debug("Lese und sende Pi-Temperatur...")
                    cpu_temp = self._get_cpu_temperature()
                    logging.debug(f"_get_cpu_temperature returned: {cpu_temp}")
                    if cpu_temp is not None:
                        try:
                            # Sende Temperatur als String
                            self.mqtt_handler.publish_message(pi_status_topic, f"{cpu_temp:.1f}")
                            logging.debug(f"Sende Pi-Temperatur: {cpu_temp:.1f}°C auf Topic {pi_status_topic}")
                            last_pi_status_send = current_time
                            logging.debug("Pi temperature message published.")
                        except Exception as e:
                            logging.error(f"Fehler beim Senden der Pi-Temperatur: {e}", exc_info=True)
                    else:
                        logging.warning("Konnte Pi-Temperatur nicht lesen, sende nichts.")
                        # Optional: Sende trotzdem, um zu sehen, dass die Schleife läuft
                        # last_pi_status_send = current_time
                # --- ENDE NEU ---

                # --- AssistNow prüfen (periodisch) ---
                # check_assist_now sollte intern Fehler behandeln
                logging.debug("Prüfe AssistNow (periodisch)...")
                # Rufe ohne force_update auf, um die zeitbasierte Prüfung zu nutzen
                self.gps_handler.check_assist_now()
                logging.debug("Periodische AssistNow Prüfung beendet.")
                # --- Ende AssistNow prüfen ---

                # --- Warten ---
                # Finde das kürzeste nächste Sendeintervall, um nicht unnötig lange zu schlafen
                next_gps_send = last_gps_status_send + gps_status_interval
                next_pi_send = last_pi_status_send + pi_status_interval if pi_status_topic and PSUTIL_AVAILABLE else float(
                    'inf')
                next_event_time = min(next_gps_send, next_pi_send)

                # Standard-Schlafintervall (z.B. für GPS-Daten lesen)
                base_sleep_interval = REC_CONFIG.get("storage_interval", 1)

                # Berechne die Zeit bis zum nächsten Ereignis (Status senden)
                wait_time_for_send = max(0, next_event_time - current_time)

                # Schlafe für die kürzere Zeit: entweder das Basisintervall oder bis zum nächsten Senden
                sleep_duration = min(base_sleep_interval, wait_time_for_send)

                logging.debug(f"Warte für {sleep_duration:.2f} Sekunden...")
                time.sleep(sleep_duration)
                logging.debug(f"--- Ende Hauptschleife Iteration {loop_counter} ---")

            # --- Fehlerbehandlung in der Hauptschleife ---
            except serial.SerialException as ser_e:
                # Spezifische Behandlung für serielle Fehler
                logging.error(f"Serieller Fehler in der Hauptschleife: {ser_e}")
                # Versuche, die serielle Verbindung im GpsHandler wiederherzustellen
                if self.gps_handler:
                    # Prüfen, ob die Methode existiert und aufrufbar ist
                    reconnect_method = getattr(self.gps_handler, '_reconnect_serial', None)
                    if callable(reconnect_method):
                        logging.info("Versuche serielle Verbindung wiederherzustellen...")
                        reconnect_method()
                    else:
                        logging.warning("GpsHandler hat keine '_reconnect_serial' Methode.")
                logging.info("Warte 5 Sekunden nach seriellem Fehler...")
                time.sleep(5)

            except KeyboardInterrupt:
                # Sauberes Beenden bei Strg+C
                logging.info("KeyboardInterrupt empfangen. Beende Hauptschleife.")
                break  # Schleife verlassen

            except Exception as e:
                # Allgemeine Fehlerbehandlung für unerwartete Probleme
                logging.error(f"Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
                # Kurze Pause, um Endlosschleifen bei permanenten Fehlern zu vermeiden
                logging.info("Warte 5 Sekunden nach unerwartetem Fehler...")
                time.sleep(5)

        # --- Cleanup nach der Schleife ---
        self.cleanup()

    def cleanup(self):
        """Räumt Ressourcen auf, wenn die Anwendung beendet wird."""
        logging.info("Hauptschleife beendet. Räume auf...")
        # MQTT-Verbindung trennen (Handler sollte dies sicher tun)
        if self.mqtt_handler:
            logging.info("Trenne MQTT-Verbindung...")
            self.mqtt_handler.disconnect()

        # Serielle Verbindung schließen (im GpsHandler)
        if self.gps_handler:
            logging.info("Schließe serielle GPS-Verbindung...")
            self.gps_handler.close_serial()  # Eigene Methode im Handler dafür vorsehen

        logging.info("Aufräumen beendet.")


if __name__ == "__main__":
    # Hauptausführungspunkt
    logging.info("Starte Worx GPS Recorder Anwendung.")
    try:
        print("Start")
        worx_gps_rec = WorxGpsRec()
        worx_gps_rec.main_loop()  # Startet die Hauptschleife
    except Exception as global_e:
        # Fängt Fehler während der Initialisierung ab
        logging.critical(f"Kritischer Fehler beim Starten oder während der Laufzeit: {global_e}", exc_info=True)
        # Optional: Versuche noch aufzuräumen, falls Instanz existiert
        try:
            if 'worx_gps_rec' in locals() and worx_gps_rec:
                worx_gps_rec.cleanup()
        except Exception as cleanup_e:
            logging.error(f"Fehler während des Cleanup nach kritischem Fehler: {cleanup_e}", exc_info=True)
        sys.exit(1)  # Beenden mit Fehlercode
    finally:
        logging.info("Worx GPS Recorder Anwendung beendet.")
        sys.exit(0)  # Normales Beenden# Worx_GPS_Rec.py

