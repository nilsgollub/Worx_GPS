# Worx_GPS.py
import logging
from mqtt_handler import MqttHandler
from heatmap_generator import HeatmapGenerator
from data_manager import DataManager
# Importiere ALLE benötigten Configs und utils
from config import HEATMAP_CONFIG, REC_CONFIG, POST_PROCESSING_CONFIG, PROBLEM_CONFIG, ASSIST_NOW_CONFIG, GEO_CONFIG
from processing import apply_moving_average, apply_kalman_filter, remove_outliers_by_speed, remove_drift_at_standstill
from utils import read_gps_data_from_csv_string, flatten_data, calculate_area_coverage
import time
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)


class WorxGps:
    # __init__ (unverändert)
    def __init__(self):
        self.test_mode = REC_CONFIG["test_mode"]
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.heatmap_generator = HeatmapGenerator()
        self.data_manager = DataManager(data_folder="data")
        self.gps_data_buffer = ""
        self.maehvorgang_data = deque(maxlen=10)  # Hält die letzten 10 Sessions
        self.alle_maehvorgang_data = self.data_manager.load_all_mow_data()
        self.problemzonen_data = self.data_manager.read_problemzonen_data()
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()
        logger.info("WorxGps initialisiert.")
        self.initial_heatmap_update()

    # initial_heatmap_update angepasst
    def initial_heatmap_update(self):
        """Aktualisiert Karten beim Start, falls Daten vorhanden sind."""
        logger.info("Führe initiale Karten-Aktualisierung durch...")

        # Fülle das deque 'maehvorgang_data' (unverändert)
        if not self.maehvorgang_data and self.alle_maehvorgang_data:
            num_to_load = min(len(self.alle_maehvorgang_data), 10)
            for mow_session in self.alle_maehvorgang_data[-num_to_load:]:
                if isinstance(mow_session, list):
                    self.maehvorgang_data.append(mow_session)
                else:
                    logger.warning(f"Unerwarteter Datentyp in alle_maehvorgang_data: {type(mow_session)}.")
            logger.info(f"{len(self.maehvorgang_data)} Mähvorgänge in das 'letzte 10'-Deque geladen.")

        # --- Letzte 10 Mähvorgänge (Heatmap UND Qualitäts-Pfade) ---
        if self.maehvorgang_data:
            current_last_10_sessions = list(self.maehvorgang_data)
            self.update_single_map("heatmap_10_maehvorgang", current_last_10_sessions, draw_path=True,
                                   is_multi=True)
            # NEU: Aufruf für quality_path_10 und wifi_heatmap
            self.update_single_map("quality_path_10", current_last_10_sessions, draw_path=True,
                                   is_multi=True)
            self.update_single_map("wifi_heatmap", current_last_10_sessions, draw_path=True,
                                   is_multi=True)
        else:
            logger.info("Keine Daten für 'heatmap_10_maehvorgang', 'quality_path_10' und 'wifi_heatmap'.")

        # --- Kumulierte Daten (Nur Heatmap) ---
        if self.alle_maehvorgang_data:
            flat_all_data = flatten_data(self.alle_maehvorgang_data)
            self.update_single_map("heatmap_kumuliert", flat_all_data, draw_path=False, is_multi=False)
            # Der Aufruf für quality_path_cumulative wurde entfernt
        else:
            logger.info("Keine Daten für 'heatmap_kumuliert'.")

        # --- Problemzonen (Heatmap) ---
        if self.problemzonen_data:
            self.update_single_map("problemzonen_heatmap", self.problemzonen_data, draw_path=False, is_multi=False)
        else:
            logger.info("Keine Daten für 'problemzonen_heatmap'.")

        logger.info("Initiale Karten-Aktualisierung abgeschlossen.")

    # on_mqtt_message (unverändert)
    def on_mqtt_message(self, msg):
        try:
            payload_preview = msg.payload[:100].decode('utf-8', errors='ignore')
            logger.debug(f"RAW MQTT Message Received - Topic: {msg.topic}, Payload Preview: {payload_preview}...")
        except Exception as log_err:
            logger.error(f"Fehler beim Loggen der RAW-Nachricht: {log_err}")

        try:
            payload_decoded = msg.payload.decode()
            logger.debug(f"Decoded MQTT Message - Topic: {msg.topic}")

            if msg.topic == self.mqtt_handler.topic_gps:
                self.handle_gps_data(payload_decoded)
            elif msg.topic == self.mqtt_handler.topic_status:
                self.handle_status_data(payload_decoded)
            else:
                logger.debug(f"Nachricht auf unbehandeltem Topic empfangen (nach Filterung): {msg.topic}")
        except UnicodeDecodeError:
            logger.error(f"Fehler beim Dekodieren der MQTT-Nachricht auf Topic {msg.topic}")
        except Exception as e:
            logger.error(f"Fehler in on_mqtt_message: {e}", exc_info=True)

    # handle_gps_data angepasst
    def handle_gps_data(self, csv_data):
        """Verarbeitet empfangene GPS-Daten (CSV-Format), führt Filterung durch."""
        logger.debug(f"handle_gps_data called with data preview: {csv_data[:100]}...")

        if csv_data != "-1":
            self.gps_data_buffer += csv_data
            logger.debug(f"Current buffer size: {len(self.gps_data_buffer)}")
        else:
            logger.info("End-Marker für GPS-Daten empfangen, verarbeite Puffer...")
            logging.debug(f"Processing buffer content (first 200 chars): {self.gps_data_buffer[:200]}...")

            # Schritte 1-3: Daten lesen und verarbeiten
            raw_gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            self.gps_data_buffer = ""
            if not raw_gps_data:
                return
            
            logger.info(f"End-Marker empfangen. {len(raw_gps_data)} Punkte empfangen. Warte auf WebUI-Speicherung...")
            
            # Kurze Pause, damit DataService (WebUI) den Speichervorgang abschließen kann
            time.sleep(2)
            
            # Daten neu aus der DB laden, um konsistent zu sein
            self.alle_maehvorgang_data = self.data_manager.load_all_mow_data()
            if self.alle_maehvorgang_data:
                new_processed_data = self.alle_maehvorgang_data[-1]
                self.maehvorgang_data.append(new_processed_data)
            else:
                logger.warning("Keine Daten in der DB gefunden nach Mähvorgang.")
                return

            logger.info("Starte Karten-Aktualisierung (Evaluation-Mode)...")
            processed_data = self.maehvorgang_data[-1]

            logger.info("Starte Karten-Aktualisierung nach neuem Mähvorgang...")

            # Letzte 10 Mähvorgänge vorverarbeiten (Drift im Stillstand entfernen)
            # Wir wenden den Filter auf jede Session einzeln an
            filtered_last_10 = [remove_drift_at_standstill(session) for session in self.maehvorgang_data]
            processed_data_filtered = filtered_last_10[-1] if filtered_last_10 else []

            # Aktueller Mähvorgang (Heatmap + Pfad)
            self.update_single_map("heatmap_aktuell", processed_data_filtered, draw_path=True, is_multi=False)

            # Letzte 10 Mähvorgänge (Heatmap UND Qualitäts-Pfade)
            self.update_single_map("heatmap_10_maehvorgang", filtered_last_10, draw_path=True, is_multi=True)
            self.update_single_map("quality_path_10", filtered_last_10, draw_path=True, is_multi=True)
            self.update_single_map("wifi_heatmap", filtered_last_10, draw_path=True, is_multi=True)

            # Kumulierte Daten (Nur Heatmap)
            flat_all_data = flatten_data(self.alle_maehvorgang_data)
            self.update_single_map("heatmap_kumuliert", flat_all_data, draw_path=False, is_multi=False)
            # Der Aufruf für quality_path_cumulative wurde entfernt

            # Problemzonen (Heatmap)
            self.update_single_map("problemzonen_heatmap", self.problemzonen_data, draw_path=False, is_multi=False)
            logging.info("Karten-Aktualisierung abgeschlossen.")

    # handle_status_data (unverändert)
    def handle_status_data(self, csv_data):
        """Verarbeitet empfangene Status-Nachrichten."""
        logger.debug(f"handle_status_data called with data: {csv_data}")
        parts = csv_data.split(",")
        if len(parts) >= 3 and parts[0] == "problem" and csv_data != "problem,-1,-1":
            logging.debug(f"Empfangene Problemzonen-Daten: {csv_data}")
            try:
                _, lat_str, lon_str = parts[:3]
                problem_data = {"lat": float(lat_str), "lon": float(lon_str), "timestamp": time.time()}
                # Nur Karten-Update triggern, kein Speichern (macht WebUI)
                self.problemzonen_data = self.data_manager.read_problemzonen_data()
                self.update_single_map("problemzonen_heatmap", self.problemzonen_data, draw_path=False,
                                        is_multi=False)
            except ValueError:
                logger.error(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}")
            except Exception as e:
                logger.error(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}", exc_info=True)
        elif csv_data == "problem,-1,-1":
            logging.info("End-Marker für Problemzonen empfangen (keine Aktion).")
        else:
            logging.info(f"Empfangene Statusmeldung: {csv_data}")

    # update_single_map (unverändert zur letzten Version)
    def update_single_map(self, config_key, data, draw_path, is_multi=False):
        """
        Aktualisiert eine einzelne Karte (HTML und optional PNG).
        Kann Heatmaps oder Pfadkarten erstellen.
        """
        if config_key in HEATMAP_CONFIG:
            config = HEATMAP_CONFIG[config_key]
            html_output_file = config["output"]
            png_output_file = config.get("png_output")
            generate_png = config.get("generate_png", True)

            logger.debug(f"Aktualisiere Karte: {config_key} -> {html_output_file}")

            if not data:
                logger.warning(f"Keine Daten zum Aktualisieren der Karte '{config_key}' vorhanden.")
                return

            try:
                # HTML erstellen
                # visualize_quality_path wird jetzt innerhalb von create_heatmap aus der Config gelesen
                self.heatmap_generator.create_heatmap(data, html_output_file, draw_path, is_multi_session=is_multi)

                # PNG erstellen, falls Name vorhanden UND Generierung aktiviert
                if png_output_file and generate_png:
                    logger.debug(f"Generiere PNG für {config_key} -> {png_output_file}")
                    # visualize_quality_path wird jetzt innerhalb von save_html_as_png aus der Config gelesen
                    self.heatmap_generator.save_html_as_png(data, draw_path, png_output_file,
                                                            config_key_hint=config_key,
                                                            is_multi_session_data=is_multi)
                elif png_output_file and not generate_png:
                    logger.debug(f"PNG-Generierung für {config_key} übersprungen (deaktiviert in Config).")

            except KeyError as e:
                logger.error(f"Fehlender Schlüssel in HEATMAP_CONFIG für '{config_key}': {e}")
            except Exception as e:
                logger.error(f"Fehler beim Aktualisieren der Karte '{config_key}': {e}", exc_info=True)
        else:
            logging.warning(f"Karten-Key '{config_key}' nicht in HEATMAP_CONFIG gefunden.")


# __main__ (unverändert)
if __name__ == "__main__":
    log_level = logging.DEBUG if REC_CONFIG.get("debug_logging", False) else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

    worx_gps = WorxGps()
    logger.info(f"Worx_GPS gestartet im {'Testmodus' if worx_gps.test_mode else 'Realmodus'}.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Beende Worx_GPS...")
        if worx_gps.mqtt_handler:
            worx_gps.mqtt_handler.disconnect()
        logger.info("Worx_GPS beendet.")
    except Exception as e:
        logger.error(f"Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
        if worx_gps.mqtt_handler:
            worx_gps.mqtt_handler.disconnect()
