# Worx_GPS_Rec.py
import sys
# import pkg_resources # Nicht mehr benötigt für die Kernfunktionalität, DeprecationWarning vermeiden
import logging  # Logging importieren
# --- ADDED IMPORTS ---
import serial
import paho.mqtt.client as paho_mqtt_client
# --- END ADDED IMPORTS ---
from mqtt_handler import MqttHandler
from gps_handler import GpsHandler
from data_recorder import DataRecorder
from problem_detection import ProblemDetector
from config import REC_CONFIG
import time
import subprocess

# Logging konfigurieren (optional, aber empfohlen)
# Stelle sicher, dass das Level auf DEBUG steht, um alle Meldungen zu sehen
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class WorxGpsRec:
    def __init__(self):
        self.test_mode = REC_CONFIG["test_mode"]
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.gps_handler = GpsHandler()
        self.data_recorder = DataRecorder(self.mqtt_handler)
        self.problem_detector = ProblemDetector(self.mqtt_handler)
        self.is_recording = False
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()
        # Das Abonnieren erfolgt jetzt automatisch im _on_connect Callback des MqttHandlers
        logging.info("WorxGpsRec initialisiert.")  # Info Log

    def on_mqtt_message(self, msg):
        # Sicherstellen, dass Payload dekodierbar ist
        try:
            payload = msg.payload.decode()
            logging.debug(f"Nachricht empfangen - Topic: '{msg.topic}', Payload: '{payload}'")
        except UnicodeDecodeError:
            logging.warning(f"Konnte Payload auf Topic '{msg.topic}' nicht dekodieren.")
            return  # Verarbeitung abbrechen, wenn Payload nicht lesbar ist

        if msg.topic == self.mqtt_handler.topic_control:
            # --- Vereinfachte Logik für GPS-Modus ---
            mode_mapping = {
                "fakegps_on": "fake_route",
                "start_route": "fake_route",
                "stop_route": "fake_random",  # Beachte: stop_route setzt jetzt random
                "random_points": "fake_random",
                "fakegps_off": "real"
            }

            if payload == "start":
                self.start_recording()
            elif payload == "stop":  # Stoppt nur, wenn Aufnahme läuft
                self.stop_recording()
            elif payload == "problem":
                self.send_problem_message()
            elif payload in mode_mapping:
                new_mode = mode_mapping[payload]
                if self.gps_handler.change_gps_mode(new_mode):
                    logging.info(f"GPS-Modus auf '{new_mode}' geändert (via {payload}).")
                else:
                    logging.warning(f"Fehler beim Ändern des GPS-Modus auf '{new_mode}'.")
            elif payload == "shutdown":
                logging.info("Shutdown-Befehl empfangen. Fahre Raspberry Pi herunter...")
                try:
                    subprocess.call(["sudo", "shutdown", "-h", "now"])
                except FileNotFoundError:
                    logging.error("Fehler: 'sudo' Befehl nicht gefunden. Shutdown nicht möglich.")
                except Exception as e:
                    logging.error(f"Fehler beim Ausführen des Shutdown-Befehls: {e}")
            else:
                logging.warning(f"Unbekannter Befehl empfangen: {payload}")
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_command")
        else:
            logging.debug(f"Nachricht auf anderem Topic ignoriert: {msg.topic}")

    def start_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.data_recorder.clear_buffer()
            logging.info("Aufnahme gestartet.")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording started")
        else:
            logging.warning("Aufnahme läuft bereits.")

    def stop_recording(self):
        # Stoppt nur, wenn die Aufnahme aktiv ist
        if self.is_recording:
            self.is_recording = False
            logging.info("Aufnahme gestoppt. Sende Daten...")
            self.data_recorder.send_buffer_data()
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording stopped")
        else:
            logging.warning("Aufnahme war nicht aktiv, Stop-Befehl ignoriert.")

    def send_problem_message(self):
        gps_data = self.gps_handler.last_known_position
        if gps_data and 'lat' in gps_data and 'lon' in gps_data:
            problem_data = f"problem,{gps_data['lat']},{gps_data['lon']}"
            logging.info(f"Sende Problem-Nachricht: {problem_data}")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, problem_data)
        else:
            logging.warning("Keine gültigen GPS-Daten verfügbar, um Problem zu senden.")
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

    def main_loop(self):
        last_status_send = time.time() - 10
        logging.info("Hauptschleife gestartet.")
        loop_counter = 0
        while True:
            # --- NEUES LOGGING HIER ---
            logging.debug(f"*** main_loop: Entering while True (Iteration {loop_counter + 1}) ***")
            # --- Ende NEUES LOGGING ---
            try:
                loop_counter += 1
                logging.debug(f"--- Start Hauptschleife Iteration {loop_counter} ---")
                current_time = time.time()

                # --- GPS Daten holen und loggen ---
                gps_data = self.gps_handler.get_gps_data()
                logging.debug(f"GPS Data received in loop: {gps_data}")
                # --- Ende GPS Daten Log ---

                if self.is_recording:
                    if gps_data:
                        if all(k in gps_data for k in ("lat", "lon")):
                            if self.gps_handler.is_inside_boundaries(gps_data["lat"],
                                                                     gps_data["lon"]) or self.test_mode:
                                self.data_recorder.add_gps_data(gps_data)
                                self.problem_detector.add_position(gps_data)
                                logging.debug(f"Gültiger GPS-Punkt innerhalb Grenzen verarbeitet: {gps_data}")
                            else:
                                logging.debug(
                                    f"Koordinaten ({gps_data.get('lat', 'N/A')},{gps_data.get('lon', 'N/A')}) liegen außerhalb des Grundstücks.")
                        else:
                            logging.warning(f"Empfangene GPS-Daten unvollständig (lat/lon fehlt): {gps_data}")
                    else:
                        logging.debug("Keine gültigen GPS-Daten während der Aufnahme erhalten.")

                # Status senden alle 10 Sekunden
                if current_time - last_status_send >= 10:
                    logging.debug("Prüfe, ob Status gesendet werden soll...")
                    if gps_data:
                        if all(k in gps_data for k in ("lat", "lon", "timestamp", "satellites")):
                            status_message = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"
                            logging.debug(f"Sende Status-Update: {status_message}")
                            # --- HIER WIRD DER STATUS GESENDET ---
                            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, status_message)
                            # --- --- --- --- --- --- --- --- --- ---
                        else:
                            logging.warning(f"GPS-Daten für Status unvollständig: {gps_data}")
                    else:
                        logging.debug("Keine gültigen GPS-Daten für Statusmeldung vorhanden.")
                    last_status_send = current_time  # Zeit auch aktualisieren, wenn nichts gesendet wurde

                # AssistNow prüfen
                logging.debug("Prüfe AssistNow...")
                self.gps_handler.check_assist_now()
                logging.debug("AssistNow Prüfung beendet.")

                # Warten
                sleep_interval = REC_CONFIG.get("storage_interval", 2)
                logging.debug(f"Warte für {sleep_interval} Sekunden...")
                time.sleep(sleep_interval)
                logging.debug(f"--- Ende Hauptschleife Iteration {loop_counter} ---")

            except serial.SerialException as ser_e:
                logging.error(f"Serieller Fehler in der Hauptschleife: {ser_e}")
                if self.gps_handler:
                    if hasattr(self.gps_handler, '_reconnect_serial') and callable(
                            getattr(self.gps_handler, '_reconnect_serial')):
                        self.gps_handler._reconnect_serial()
                    else:
                        logging.warning("GpsHandler hat keine '_reconnect_serial' Methode.")
                logging.info("Warte 5 Sekunden nach seriellem Fehler...")
                time.sleep(5)

            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt empfangen. Beende Hauptschleife.")
                break
            except Exception as e:
                logging.error(f"Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
                logging.info("Warte 5 Sekunden nach unerwartetem Fehler...")
                time.sleep(5)

        # Cleanup nach der Schleife
        logging.info("Hauptschleife beendet. Räume auf...")
        if self.mqtt_handler:
            logging.info("Trenne MQTT-Verbindung.")
            self.mqtt_handler.disconnect()
        if hasattr(self.gps_handler, 'ser_gps') and self.gps_handler.ser_gps and self.gps_handler.ser_gps.is_open:
            logging.info("Schließe serielle GPS-Verbindung.")
            try:
                self.gps_handler.ser_gps.close()
            except Exception as e:
                logging.error(f"Fehler beim Schließen der seriellen Verbindung: {e}")
        logging.info("Aufräumen beendet.")


if __name__ == "__main__":
    worx_gps_rec = WorxGpsRec()
    worx_gps_rec.main_loop()
