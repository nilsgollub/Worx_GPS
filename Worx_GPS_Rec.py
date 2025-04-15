# Worx_GPS_Rec.py
import sys
import pkg_resources
import logging  # Logging importieren
from mqtt_handler import MqttHandler
from gps_handler import GpsHandler
from data_recorder import DataRecorder
from problem_detection import ProblemDetector
from config import REC_CONFIG
import time
import subprocess

# Logging konfigurieren (optional, aber empfohlen)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')  # Level auf DEBUG setzen

# --- Debug Info (kann später entfernt werden) ---
logging.debug(f"--- Debug Info ---")
logging.debug(f"Python Executable: {sys.executable}")
try:
    paho_version = pkg_resources.get_distribution("paho-mqtt").version
    logging.debug(f"Paho-MQTT Version: {paho_version}")
except pkg_resources.DistributionNotFound:
    logging.debug("Paho-MQTT Version: Not Found!")
logging.debug(f"--- End Debug Info ---")


# --- Ende Debug Info ---


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
        logging.info("WorxGpsRec initialisiert.")  # Info Log

    def on_mqtt_message(self, msg):
        # --- Korrektur: print zu logging.debug ---
        # print(f"DEBUG: Nachricht empfangen - Topic: '{msg.topic}', Payload: '{msg.payload.decode()}'") # ALT
        logging.debug(f"Nachricht empfangen - Topic: '{msg.topic}', Payload: '{msg.payload.decode()}'")  # NEU
        # --- Ende Korrektur ---

        if msg.topic == self.mqtt_handler.topic_control:
            payload = msg.payload.decode()
            if payload == "start":
                self.start_recording()
            elif payload == "stop" and self.is_recording:
                self.stop_recording()
            elif payload == "problem":
                self.send_problem_message()
            elif payload == "fakegps_on":
                self.gps_handler.change_gps_mode("fake_route")
                logging.info("GPS-Modus auf 'fake_route' geändert.")  # Log
            elif payload == "fakegps_off":
                self.gps_handler.change_gps_mode("real")
                logging.info("GPS-Modus auf 'real' geändert.")  # Log
            elif payload == "start_route":
                self.gps_handler.change_gps_mode("fake_route")
                logging.info("GPS-Modus auf 'fake_route' geändert (start_route).")  # Log
            elif payload == "stop_route":
                self.gps_handler.change_gps_mode("fake_random")
                logging.info("GPS-Modus auf 'fake_random' geändert (stop_route).")  # Log
            elif payload == "random_points":
                self.gps_handler.change_gps_mode("fake_random")
                logging.info("GPS-Modus auf 'fake_random' geändert (random_points).")  # Log
            elif payload == "shutdown":
                logging.info("Shutdown-Befehl empfangen. Fahre Raspberry Pi herunter...")  # Log
                try:
                    subprocess.call(["sudo", "shutdown", "-h", "now"])
                except FileNotFoundError:
                    logging.error("Fehler: 'sudo' Befehl nicht gefunden. Shutdown nicht möglich.")
                except Exception as e:
                    logging.error(f"Fehler beim Ausführen des Shutdown-Befehls: {e}")
            else:
                logging.warning(f"Unbekannter Befehl empfangen: {payload}")  # Log
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_command")

    def start_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.data_recorder.clear_buffer()  # Puffer leeren beim Start
            logging.info("Aufnahme gestartet.")  # Log
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording started")
        else:
            logging.warning("Aufnahme läuft bereits.")  # Log

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            logging.info("Aufnahme gestoppt. Sende Daten...")  # Log
            self.data_recorder.send_buffer_data()
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording stopped")
        else:
            logging.warning("Aufnahme war nicht aktiv.")  # Log

    def send_problem_message(self):
        # Verwende die zuletzt bekannte Position, falls verfügbar
        gps_data = self.gps_handler.last_known_position
        if gps_data:
            problem_data = f"problem,{gps_data['lat']},{gps_data['lon']}"
            logging.info(f"Sende Problem-Nachricht: {problem_data}")  # Log
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, problem_data)
        else:
            logging.warning("Keine GPS-Daten verfügbar, um Problem zu senden.")  # Log
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

    def main_loop(self):
        last_status_send = time.time() - 10  # Sicherstellen, dass der erste Status sofort gesendet wird
        logging.info("Hauptschleife gestartet.")  # Log
        while True:
            try:  # Füge try...except um die Hauptlogik hinzu
                current_time = time.time()
                gps_data = self.gps_handler.get_gps_data()  # Hole GPS Daten einmal pro Durchlauf

                if self.is_recording:
                    if gps_data:  # Nur wenn gültige GPS-Daten vorhanden sind
                        # --- Korrektur: add_gps_data und add_position in den if-Block verschoben ---
                        if self.gps_handler.is_inside_boundaries(gps_data["lat"], gps_data["lon"]) or self.test_mode:
                            # Daten im Puffer sammeln (immer, auch im Testmodus)
                            self.data_recorder.add_gps_data(gps_data)
                            # Neue Position an Problem Detector senden
                            self.problem_detector.add_position(gps_data)
                            logging.debug(f"Gültiger GPS-Punkt innerhalb Grenzen verarbeitet: {gps_data}")  # Debug Log
                        # --- Ende Korrektur ---
                        else:
                            logging.debug(
                                f"Koordinaten ({gps_data['lat']},{gps_data['lon']}) liegen außerhalb des Grundstücks.")  # Debug Log
                    else:
                        logging.debug("Keine gültigen GPS-Daten während der Aufnahme.")  # Debug Log

                # Auch wenn keine Aufzeichnung läuft, Status-Updates senden (alle 10 Sekunden)
                if current_time - last_status_send >= 10:
                    # Verwende die bereits abgerufenen gps_data
                    if gps_data:
                        status_message = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"
                        logging.debug(f"Sende Status-Update: {status_message}")  # Debug Log
                        self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, status_message)
                    else:
                        logging.debug("Keine gültigen GPS-Daten für Statusmeldung.")  # Debug Log
                    last_status_send = current_time  # Zeit aktualisieren

                # AssistNow Offline-Daten aktualisieren (einmal täglich)
                # Die check_assist_now Methode loggt bereits intern
                self.gps_handler.check_assist_now()

                # Wartezeit basierend auf Konfiguration
                time.sleep(REC_CONFIG["storage_interval"])

            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt empfangen. Beende Hauptschleife.")
                break  # Schleife beenden
            except Exception as e:
                logging.error(f"Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
                time.sleep(5)  # Warte kurz nach einem Fehler

        # Aufrn nach der Schleife
        logging.info("Hauptschleife beendet. Trenne MQTT-Verbindung.")
        if self.mqtt_handler:
            self.mqtt_handler.disconnect()
        if self.gps_handler and self.gps_handler.ser_gps and self.gps_handler.ser_gps.is_open:
            logging.info("Schließe serielle GPS-Verbindung.")
            self.gps_handler.ser_gps.close()


if __name__ == "__main__":
    worx_gps_rec = WorxGpsRec()
    worx_gps_rec.main_loop()  # Starte die Hauptschleife
