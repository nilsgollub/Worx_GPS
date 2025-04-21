# Worx_GPS.py
import logging
from mqtt_handler import MqttHandler
from heatmap_generator import HeatmapGenerator
from data_manager import DataManager
from utils import read_gps_data_from_csv_string
from config import HEATMAP_CONFIG, REC_CONFIG
import time
from collections import deque
from pathlib import Path  # pathlib verwenden

# Logging konfigurieren
# Besser: Logging im __main__ konfigurieren, nicht global
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Logger holen


class WorxGps:
    def __init__(self):
        self.test_mode = REC_CONFIG["test_mode"]
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.heatmap_generator = HeatmapGenerator()
        # DataManager mit Pfad initialisieren
        self.data_manager = DataManager(data_folder="data")  # data_folder übergeben
        self.gps_data_buffer = ""
        self.maehvorgang_data = deque(maxlen=10)
        self.alle_maehvorgang_data = self.data_manager.load_all_mow_data()
        # Problemzonen als Liste laden für einfachere Handhabung hier
        self.problemzonen_data = self.data_manager.read_problemzonen_data()  # Gibt Liste zurück
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()
        logger.info("WorxGps initialisiert.")
        self.initial_heatmap_update()

    def initial_heatmap_update(self):
        """Aktualisiert Heatmaps beim Start, falls Daten vorhanden sind."""
        logger.info("Führe initiale Heatmap-Aktualisierung durch...")

        # Fülle das deque 'maehvorgang_data' aus 'alle_maehvorgang_data'
        if not self.maehvorgang_data and self.alle_maehvorgang_data:
            num_to_load = min(len(self.alle_maehvorgang_data), 10)
            for mow_session in self.alle_maehvorgang_data[-num_to_load:]:
                if isinstance(mow_session, list):
                    self.maehvorgang_data.append(mow_session)
                else:
                    logger.warning(f"Unerwarteter Datentyp in alle_maehvorgang_data: {type(mow_session)}.")
            logger.info(f"{len(self.maehvorgang_data)} Mähvorgänge in das 'letzte 10'-Deque geladen.")

        # --- Letzte 10 Mähvorgänge (Interaktiv) ---
        if self.maehvorgang_data:
            # Übergebe die Liste der Sessions (deque -> list)
            # draw_path=False, da Pfade pro Session gezeichnet werden
            self.update_single_heatmap("heatmap_10_maehvorgang", list(self.maehvorgang_data), draw_path=True,
                                       is_multi=True)  # draw_path=True, Pfad pro Session
        else:
            logger.info("Keine Daten für 'heatmap_10_maehvorgang' vorhanden.")

        # --- Kumulierte Daten (Alle Sessions kombiniert) ---
        if self.alle_maehvorgang_data:
            flat_all_data = [point for mow_session in self.alle_maehvorgang_data for point in mow_session]
            self.update_single_heatmap("heatmap_kumuliert", flat_all_data, draw_path=False, is_multi=False)
        else:
            logger.info("Keine Daten für 'heatmap_kumuliert' vorhanden.")

        # --- Problemzonen ---
        if self.problemzonen_data:  # Ist jetzt eine Liste
            self.update_single_heatmap("problemzonen_heatmap", self.problemzonen_data, draw_path=False, is_multi=False)
        else:
            logger.info("Keine Daten für 'problemzonen_heatmap' vorhanden.")

        logger.info("Initiale Heatmap-Aktualisierung abgeschlossen.")

    def on_mqtt_message(self, msg):
        # ... (Rest der Methode bleibt gleich) ...
        try:
            payload_preview = msg.payload[:100].decode('utf-8', errors='ignore')  # Preview dekodieren
            logger.debug(f"RAW MQTT Message Received - Topic: {msg.topic}, Payload Preview: {payload_preview}...")
        except Exception as log_err:
            logger.error(f"Fehler beim Loggen der RAW-Nachricht: {log_err}")

        try:
            payload_decoded = msg.payload.decode()
            logger.debug(f"Decoded MQTT Message - Topic: {msg.topic}")

            if msg.topic == self.mqtt_handler.topic_gps:
                logger.debug(f"Handling GPS data on topic {msg.topic}...")
                self.handle_gps_data(payload_decoded)
            elif msg.topic == self.mqtt_handler.topic_status:
                logger.debug(f"Handling Status data on topic {msg.topic}...")
                self.handle_status_data(payload_decoded)
            else:
                logger.debug(f"Nachricht auf unbehandeltem Topic empfangen (nach Filterung): {msg.topic}")
        except UnicodeDecodeError:
            logger.error(f"Fehler beim Dekodieren der MQTT-Nachricht auf Topic {msg.topic}")
        except Exception as e:
            logger.error(f"Fehler in on_mqtt_message: {e}", exc_info=True)

    def handle_gps_data(self, csv_data):
        """Verarbeitet empfangene GPS-Daten (CSV-Format)."""
        logger.debug(f"handle_gps_data called with data preview: {csv_data[:100]}...")

        if csv_data != "-1":
            logger.debug(f"Appending data chunk to buffer (length {len(csv_data)})...")
            self.gps_data_buffer += csv_data
            logger.debug(f"Current buffer size: {len(self.gps_data_buffer)}")
        else:
            logger.info("End-Marker für GPS-Daten empfangen, verarbeite Puffer...")
            logging.debug(f"Processing buffer content (first 200 chars): {self.gps_data_buffer[:200]}...")
            gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            if gps_data:
                logger.info(f"{len(gps_data)} GPS-Punkte aus Puffer gelesen.")

                # Daten speichern und hinzufügen
                self.maehvorgang_data.append(gps_data)
                self.alle_maehvorgang_data.append(gps_data)

                filename = self.data_manager.get_next_mow_filename()
                # Stelle sicher, dass der Pfad korrekt übergeben wird (DataManager verwendet jetzt pathlib)
                self.data_manager.save_gps_data(gps_data, filename)  # Nur Dateiname übergeben

                logger.info("Starte Heatmap-Aktualisierung nach neuem Mähvorgang...")
                # Aktueller Mähvorgang
                self.update_single_heatmap("heatmap_aktuell", gps_data, draw_path=True, is_multi=False)

                # --- Letzte 10 Mähvorgänge (Interaktiv) ---
                # Übergebe die Liste der Sessions (deque -> list)
                self.update_single_heatmap("heatmap_10_maehvorgang", list(self.maehvorgang_data), draw_path=True,
                                           is_multi=True)

                # --- Kumulierte Daten (Alle Sessions kombiniert) ---
                flat_all_data = [point for mow_session in self.alle_maehvorgang_data for point in mow_session]
                self.update_single_heatmap("heatmap_kumuliert", flat_all_data, draw_path=False, is_multi=False)

                # Problemzonen (bleibt gleich)
                self.update_single_heatmap("problemzonen_heatmap", self.problemzonen_data, draw_path=False,
                                           is_multi=False)

                logging.info("Heatmap-Aktualisierung abgeschlossen.")

            else:
                logger.error("Fehler: Konnte keine GPS-Daten aus dem Puffer lesen oder Puffer war leer.")
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

            self.gps_data_buffer = ""
            logging.debug("GPS-Datenpuffer geleert.")

    def handle_status_data(self, csv_data):
        """Verarbeitet empfangene Status-Nachrichten."""
        logger.debug(f"handle_status_data called with data: {csv_data}")
        parts = csv_data.split(",")
        # Prüfe auf Problemzonen-Nachricht
        if len(parts) >= 3 and parts[0] == "problem" and csv_data != "problem,-1,-1":
            logging.debug(f"Empfangene Problemzonen-Daten: {csv_data}")
            try:
                _, lat_str, lon_str = parts[:3]
                problem_data = {"lat": float(lat_str), "lon": float(lon_str), "timestamp": time.time()}

                # Füge Problemzone hinzu (DataManager prüft auf Duplikate und speichert)
                added = self.data_manager.add_problemzone(problem_data)

                if added:
                    # Lade die Daten neu, falls sie sich geändert haben (inkl. Entfernung alter Zonen)
                    self.problemzonen_data = self.data_manager.read_problemzonen_data()
                    # Aktualisiere die Problemzonen-Heatmap
                    self.update_single_heatmap("problemzonen_heatmap", self.problemzonen_data, draw_path=False,
                                               is_multi=False)

            except ValueError:
                logger.error(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}")
            except Exception as e:
                logger.error(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}", exc_info=True)
        elif csv_data == "problem,-1,-1":
            logging.info("End-Marker für Problemzonen empfangen (keine Aktion).")
        else:
            # Andere Statusmeldungen einfach loggen
            logging.info(f"Empfangene Statusmeldung: {csv_data}")

    # --- update_single_heatmap angepasst ---
    def update_single_heatmap(self, config_key, data, draw_path, is_multi=False):
        """
        Aktualisiert eine einzelne Heatmap (HTML und PNG).

        Args:
            config_key (str): Der Schlüssel in HEATMAP_CONFIG.
            data (list): Die Datenpunkte (flach oder Liste von Listen).
            draw_path (bool): Ob der Pfad gezeichnet werden soll.
            is_multi (bool): Gibt an, ob 'data' eine Liste von Sessions ist.
        """
        if config_key in HEATMAP_CONFIG:
            config = HEATMAP_CONFIG[config_key]
            html_output_file = config["output"]  # Dateiname aus Config
            png_output_file = config.get("png_output")  # Optionaler PNG-Dateiname

            logger.debug(f"Aktualisiere Heatmap: {config_key} -> {html_output_file}")

            if not data:
                logger.warning(f"Keine Daten zum Aktualisieren der Heatmap '{config_key}' vorhanden.")
                # Optional: Leere Karte erstellen?
                # self.heatmap_generator.create_heatmap([], html_output_file, False, is_multi)
                return

            try:
                # Erstelle interaktive Karte (HTML)
                # Übergebe is_multi an create_heatmap
                self.heatmap_generator.create_heatmap(data, html_output_file, draw_path, is_multi_session=is_multi)

                # Erstelle PNG von temporärer Satellitenkarte, falls konfiguriert
                if png_output_file:
                    logger.debug(f"Generiere PNG für {config_key} -> {png_output_file}")
                    # save_html_as_png erwartet immer eine Liste von Sessions oder eine flache Liste
                    # und verwendet intern die flache Version für das PNG.
                    self.heatmap_generator.save_html_as_png(data, draw_path, png_output_file,
                                                            config_key_hint=config_key,
                                                            is_multi_session_data=is_multi)
            except KeyError as e:
                logger.error(f"Fehlender Schlüssel in HEATMAP_CONFIG für '{config_key}': {e}")
            except Exception as e:
                logger.error(f"Fehler beim Aktualisieren der Heatmap '{config_key}': {e}", exc_info=True)
        else:
            logging.warning(f"Heatmap-Key '{config_key}' nicht in HEATMAP_CONFIG gefunden.")


if __name__ == "__main__":
    # Logging hier konfigurieren
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
        # Optional: Graceful shutdown versuchen
        if worx_gps.mqtt_handler:
            worx_gps.mqtt_handler.disconnect()
