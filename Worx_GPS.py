# Worx_GPS.py
import logging  # Logging importieren
from mqtt_handler import MqttHandler
from heatmap_generator import HeatmapGenerator
from data_manager import DataManager
from utils import read_gps_data_from_csv_string
# Importiere REC_CONFIG und HEATMAP_CONFIG (HEATMAP_CONFIG war schon da)
from config import HEATMAP_CONFIG, REC_CONFIG
import time
from collections import deque

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class WorxGps:
    def __init__(self):
        self.test_mode = REC_CONFIG["test_mode"]
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.heatmap_generator = HeatmapGenerator()
        self.data_manager = DataManager()
        self.gps_data_buffer = ""
        self.maehvorgang_data = deque(maxlen=10)
        self.alle_maehvorgang_data = []
        self.maehvorgang_count = 0
        self.problemzonen_data = self.data_manager.read_problemzonen_data()
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()
        logging.info("WorxGps initialisiert.")

    def on_mqtt_message(self, msg):
        """Verarbeitet eingehende MQTT-Nachrichten."""
        # --- NEUES LOGGING: Jede Nachricht loggen ---
        try:
            payload_preview = msg.payload[:100]  # Nur die ersten 100 Bytes für die Vorschau
            logging.debug(f"RAW MQTT Message Received - Topic: {msg.topic}, Payload Preview: {payload_preview}...")
        except Exception as log_err:
            logging.error(f"Fehler beim Loggen der RAW-Nachricht: {log_err}")
        # --- ENDE NEUES LOGGING ---

        try:
            payload_decoded = msg.payload.decode()
            # --- Log nach erfolgreicher Dekodierung ---
            logging.debug(f"Decoded MQTT Message - Topic: {msg.topic}")
            # ---

            if msg.topic == self.mqtt_handler.topic_gps:
                # --- Log spezifisch für GPS Topic ---
                logging.debug(f"Handling GPS data on topic {msg.topic}...")
                # ---
                self.handle_gps_data(payload_decoded)
            elif msg.topic == self.mqtt_handler.topic_status:
                # --- Log spezifisch für Status Topic ---
                logging.debug(f"Handling Status data on topic {msg.topic}...")
                # ---
                self.handle_status_data(payload_decoded)
            else:
                # Dieses Log bleibt, ist aber jetzt redundant zum RAW-Log oben
                logging.debug(f"Nachricht auf unbehandeltem Topic empfangen (nach Filterung): {msg.topic}")
        except UnicodeDecodeError:
            logging.error(f"Fehler beim Dekodieren der MQTT-Nachricht auf Topic {msg.topic}")
        except Exception as e:
            logging.error(f"Fehler in on_mqtt_message: {e}", exc_info=True)

    def handle_gps_data(self, csv_data):
        """Verarbeitet empfangene GPS-Daten (CSV-Format)."""
        # --- Log am Anfang der Funktion ---
        logging.debug(f"handle_gps_data called with data preview: {csv_data[:100]}...")
        # ---

        if csv_data != "-1":  # Ende-Marker noch nicht erreicht
            logging.debug(f"Appending data chunk to buffer (length {len(csv_data)})...")
            self.gps_data_buffer += csv_data  # Daten zum Puffer hinzufügen
            logging.debug(f"Current buffer size: {len(self.gps_data_buffer)}")
        else:
            # Ende-Marker erreicht, Daten verarbeiten
            logging.info("End-Marker für GPS-Daten empfangen, verarbeite Puffer...")
            # --- Log den Pufferinhalt VOR der Verarbeitung ---
            logging.debug(f"Processing buffer content (first 200 chars): {self.gps_data_buffer[:200]}...")
            # ---
            gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            if gps_data:
                logging.info(f"{len(gps_data)} GPS-Punkte aus Puffer gelesen.")
                heatmap_aktuell_key = "heatmap_aktuell"
                heatmap_10_key = "heatmap_10_maehvorgang"
                heatmap_kumuliert_key = "heatmap_kumuliert"
                problemzonen_heatmap_key = "problemzonen_heatmap"

                self.maehvorgang_data.append(gps_data)
                self.alle_maehvorgang_data.extend(gps_data)

                filename = self.data_manager.get_next_mow_filename()
                self.data_manager.save_gps_data(gps_data, filename)

                # --- Heatmap-Generierung ---
                logging.info("Starte Heatmap-Generierung...")  # Log Start
                # Aktueller Mähvorgang
                if heatmap_aktuell_key in HEATMAP_CONFIG:
                    logging.debug(f"Generiere Heatmap: {heatmap_aktuell_key}")
                    self.heatmap_generator.create_heatmap(gps_data, HEATMAP_CONFIG[heatmap_aktuell_key]["output"], True)
                    if "png_output" in HEATMAP_CONFIG[heatmap_aktuell_key]:
                        logging.debug(f"Generiere PNG: {heatmap_aktuell_key}")
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[heatmap_aktuell_key]["output"],
                                                                HEATMAP_CONFIG[heatmap_aktuell_key]["png_output"])
                else:
                    logging.warning(f"Heatmap-Key '{heatmap_aktuell_key}' nicht in HEATMAP_CONFIG gefunden.")

                # Letzte 10 Mähvorgänge
                if heatmap_10_key in HEATMAP_CONFIG:
                    logging.debug(f"Generiere Heatmap: {heatmap_10_key}")
                    data_for_heatmap_10 = [point for sublist in self.maehvorgang_data for point in sublist]
                    self.heatmap_generator.create_heatmap(data_for_heatmap_10, HEATMAP_CONFIG[heatmap_10_key]["output"],
                                                          False)
                    if "png_output" in HEATMAP_CONFIG[heatmap_10_key]:
                        logging.debug(f"Generiere PNG: {heatmap_10_key}")
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[heatmap_10_key]["output"],
                                                                HEATMAP_CONFIG[heatmap_10_key]["png_output"])
                else:
                    logging.warning(f"Heatmap-Key '{heatmap_10_key}' nicht in HEATMAP_CONFIG gefunden.")

                # Kumulierte Daten
                if heatmap_kumuliert_key in HEATMAP_CONFIG:
                    logging.debug(f"Generiere Heatmap: {heatmap_kumuliert_key}")
                    self.heatmap_generator.create_heatmap(self.alle_maehvorgang_data,
                                                          HEATMAP_CONFIG[heatmap_kumuliert_key]["output"], False)
                    if "png_output" in HEATMAP_CONFIG[heatmap_kumuliert_key]:
                        logging.debug(f"Generiere PNG: {heatmap_kumuliert_key}")
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[heatmap_kumuliert_key]["output"],
                                                                HEATMAP_CONFIG[heatmap_kumuliert_key]["png_output"])
                else:
                    logging.warning(f"Heatmap-Key '{heatmap_kumuliert_key}' nicht in HEATMAP_CONFIG gefunden.")

                # Problemzonen
                if problemzonen_heatmap_key in HEATMAP_CONFIG:
                    logging.debug(f"Generiere Heatmap: {problemzonen_heatmap_key}")
                    problem_data_for_heatmap = list(self.problemzonen_data)
                    self.heatmap_generator.create_heatmap(problem_data_for_heatmap,
                                                          HEATMAP_CONFIG[problemzonen_heatmap_key]["output"], False)
                    if "png_output" in HEATMAP_CONFIG[problemzonen_heatmap_key]:
                        logging.debug(f"Generiere PNG: {problemzonen_heatmap_key}")
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[problemzonen_heatmap_key]["output"],
                                                                HEATMAP_CONFIG[problemzonen_heatmap_key]["png_output"])
                else:
                    logging.warning(f"Heatmap-Key '{problemzonen_heatmap_key}' nicht in HEATMAP_CONFIG gefunden.")
                logging.info("Heatmap-Generierung abgeschlossen.")  # Log Ende
                # --- Ende Heatmap-Generierung ---

            else:
                logging.error("Fehler: Konnte keine GPS-Daten aus dem Puffer lesen oder Puffer war leer.")
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

            self.gps_data_buffer = ""  # Puffer nach Verarbeitung leeren
            logging.debug("GPS-Datenpuffer geleert.")

    def handle_status_data(self, csv_data):
        """Verarbeitet empfangene Status-Nachrichten."""
        # --- Log am Anfang der Funktion ---
        logging.debug(f"handle_status_data called with data: {csv_data}")
        # ---
        parts = csv_data.split(",")
        if len(parts) >= 3 and parts[0] == "problem":
            logging.debug(f"Empfangene Problemzonen-Daten: {csv_data}")
            if csv_data != "problem,-1,-1":
                try:
                    _, lat_str, lon_str = parts[:3]
                    problem_data = {"lat": float(lat_str), "lon": float(lon_str), "timestamp": time.time()}
                    self.problemzonen_data.append(problem_data)
                    logging.info(f"Problemzone hinzugefügt: {problem_data}")

                    self.data_manager.remove_old_problemzonen()
                    self.problemzonen_data = self.data_manager.read_problemzonen_data()
                    self.data_manager.save_problemzonen_data(self.problemzonen_data)

                    # --- Heatmap-Generierung für Problemzonen ---
                    problemzonen_heatmap_key = "problemzonen_heatmap"
                    if problemzonen_heatmap_key in HEATMAP_CONFIG:
                        logging.debug(f"Generiere Heatmap: {problemzonen_heatmap_key}")  # Log
                        problem_data_for_heatmap = list(self.problemzonen_data)
                        self.heatmap_generator.create_heatmap(problem_data_for_heatmap,
                                                              HEATMAP_CONFIG[problemzonen_heatmap_key]["output"], False)
                        if "png_output" in HEATMAP_CONFIG[problemzonen_heatmap_key]:
                            logging.debug(f"Generiere PNG: {problemzonen_heatmap_key}")  # Log
                            self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[problemzonen_heatmap_key]["output"],
                                                                    HEATMAP_CONFIG[problemzonen_heatmap_key][
                                                                        "png_output"])
                    else:
                        logging.warning(f"Heatmap-Key '{problemzonen_heatmap_key}' nicht in HEATMAP_CONFIG gefunden.")
                    # --- Ende Heatmap-Generierung ---

                except ValueError:
                    logging.error(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}")
                except Exception as e:
                    logging.error(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}",
                                  exc_info=True)
            else:
                logging.info("End-Marker für Problemzonen empfangen.")
        else:
            logging.info(f"Empfangene Statusmeldung: {csv_data}")


if __name__ == "__main__":
    worx_gps = WorxGps()
    logging.info(f"Worx_GPS gestartet im {'Testmodus' if worx_gps.test_mode else 'Realmodus'}.")
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Beende Worx_GPS...")
            if worx_gps.mqtt_handler:
                worx_gps.mqtt_handler.disconnect()
            break
        except Exception as e:
            logging.error(f"Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
            time.sleep(5)
