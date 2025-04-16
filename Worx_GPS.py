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
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class WorxGps:
    def __init__(self):
        self.test_mode = REC_CONFIG["test_mode"]
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.heatmap_generator = HeatmapGenerator()
        self.data_manager = DataManager()
        self.gps_data_buffer = ""
        # deque speichert die letzten 10 Mähvorgänge (jeder als Liste von Punkten)
        self.maehvorgang_data = deque(maxlen=10)
        # alle_maehvorgang_data ist eine Liste von Listen (Mähvorgängen)
        self.alle_maehvorgang_data = self.data_manager.load_all_mow_data()  # Lade alle Daten beim Start
        # self.maehvorgang_count = 0 # Wird aktuell nicht verwendet, kann ggf. entfernt werden
        self.problemzonen_data = self.data_manager.read_problemzonen_data()  # Lädt aus Datei oder gibt leeres deque
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()
        logging.info("WorxGps initialisiert.")
        # Initialisiere Heatmaps beim Start, falls Daten vorhanden
        self.initial_heatmap_update()

    def initial_heatmap_update(self):
        """Aktualisiert Heatmaps beim Start, falls Daten vorhanden sind."""
        logging.info("Führe initiale Heatmap-Aktualisierung durch...")
        # Lade die letzten 10 Mähvorgänge aus den Dateien, falls das deque leer ist
        # Dies ist eine Annahme, dass load_all_mow_data die Daten chronologisch liefert
        # oder wir laden die letzten 10 Dateien explizit.
        # Einfacher Ansatz: Verwende die bereits geladenen `alle_maehvorgang_data`
        if not self.maehvorgang_data and self.alle_maehvorgang_data:
            # Fülle das deque mit den letzten max. 10 Einträgen aus der Gesamtliste
            # Annahme: alle_maehvorgang_data ist eine Liste von Listen (Mähvorgängen)
            num_to_load = min(len(self.alle_maehvorgang_data), 10)
            # Lade die letzten 'num_to_load' Mähvorgänge
            for mow_session in self.alle_maehvorgang_data[-num_to_load:]:
                # Stelle sicher, dass mow_session eine Liste ist (oder was auch immer erwartet wird)
                if isinstance(mow_session, list):
                    self.maehvorgang_data.append(mow_session)
                else:
                    logging.warning(
                        f"Unerwarteter Datentyp in alle_maehvorgang_data: {type(mow_session)}. Überspringe.")
            logging.info(f"{len(self.maehvorgang_data)} Mähvorgänge in das 'letzte 10'-Deque geladen.")

        # Letzte 10 Mähvorgänge
        if self.maehvorgang_data:  # Prüfe ob deque Daten hat
            # Korrektur: Daten korrekt aus deque extrahieren
            data_for_heatmap_10 = [point for mow_session in self.maehvorgang_data for point in mow_session]
            self.update_single_heatmap("heatmap_10_maehvorgang", data_for_heatmap_10, False)

        # Kumulierte Daten
        if self.alle_maehvorgang_data:  # Prüfe ob Daten geladen wurden
            # Korrektur: alle_maehvorgang_data ist eine Liste von Listen, wir brauchen eine flache Liste
            flat_all_data = [point for mow_session in self.alle_maehvorgang_data for point in mow_session]
            self.update_single_heatmap("heatmap_kumuliert", flat_all_data, False)

        # Problemzonen
        if self.problemzonen_data:  # Prüfe ob Daten geladen wurden
            self.update_single_heatmap("problemzonen_heatmap", list(self.problemzonen_data), False)
        logging.info("Initiale Heatmap-Aktualisierung abgeschlossen.")

    def on_mqtt_message(self, msg):
        """Verarbeitet eingehende MQTT-Nachrichten."""
        try:
            payload_preview = msg.payload[:100]
            logging.debug(f"RAW MQTT Message Received - Topic: {msg.topic}, Payload Preview: {payload_preview}...")
        except Exception as log_err:
            logging.error(f"Fehler beim Loggen der RAW-Nachricht: {log_err}")

        try:
            payload_decoded = msg.payload.decode()
            logging.debug(f"Decoded MQTT Message - Topic: {msg.topic}")

            if msg.topic == self.mqtt_handler.topic_gps:
                logging.debug(f"Handling GPS data on topic {msg.topic}...")
                self.handle_gps_data(payload_decoded)
            elif msg.topic == self.mqtt_handler.topic_status:
                logging.debug(f"Handling Status data on topic {msg.topic}...")
                self.handle_status_data(payload_decoded)
            else:
                logging.debug(f"Nachricht auf unbehandeltem Topic empfangen (nach Filterung): {msg.topic}")
        except UnicodeDecodeError:
            logging.error(f"Fehler beim Dekodieren der MQTT-Nachricht auf Topic {msg.topic}")
        except Exception as e:
            logging.error(f"Fehler in on_mqtt_message: {e}", exc_info=True)

    def handle_gps_data(self, csv_data):
        """Verarbeitet empfangene GPS-Daten (CSV-Format)."""
        logging.debug(f"handle_gps_data called with data preview: {csv_data[:100]}...")

        if csv_data != "-1":
            logging.debug(f"Appending data chunk to buffer (length {len(csv_data)})...")
            self.gps_data_buffer += csv_data
            logging.debug(f"Current buffer size: {len(self.gps_data_buffer)}")
        else:
            logging.info("End-Marker für GPS-Daten empfangen, verarbeite Puffer...")
            logging.debug(f"Processing buffer content (first 200 chars): {self.gps_data_buffer[:200]}...")
            gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            if gps_data:
                logging.info(f"{len(gps_data)} GPS-Punkte aus Puffer gelesen.")

                # Daten speichern und hinzufügen
                self.maehvorgang_data.append(gps_data)  # Fügt die Liste der Punkte als EIN Element zum deque hinzu
                # Korrektur: alle_maehvorgang_data ist Liste von Listen
                self.alle_maehvorgang_data.append(gps_data)  # Fügt den aktuellen Mähvorgang hinzu

                filename = self.data_manager.get_next_mow_filename()
                self.data_manager.save_gps_data(gps_data, filename)

                logging.info("Starte Heatmap-Aktualisierung nach neuem Mähvorgang...")
                # Aktueller Mähvorgang
                self.update_single_heatmap("heatmap_aktuell", gps_data, True)

                # Letzte 10 Mähvorgänge
                # Korrektur: Daten korrekt aus deque extrahieren
                data_for_heatmap_10 = [point for mow_session in self.maehvorgang_data for point in mow_session]
                self.update_single_heatmap("heatmap_10_maehvorgang", data_for_heatmap_10, False)

                # Kumulierte Daten
                # Korrektur: alle_maehvorgang_data ist Liste von Listen, wir brauchen eine flache Liste
                flat_all_data = [point for mow_session in self.alle_maehvorgang_data for point in mow_session]
                self.update_single_heatmap("heatmap_kumuliert", flat_all_data, False)

                # Problemzonen (wird auch in handle_status_data aufgerufen, aber hier zur Sicherheit)
                self.update_single_heatmap("problemzonen_heatmap", list(self.problemzonen_data), False)

                logging.info("Heatmap-Aktualisierung abgeschlossen.")

            else:
                logging.error("Fehler: Konnte keine GPS-Daten aus dem Puffer lesen oder Puffer war leer.")
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

            self.gps_data_buffer = ""
            logging.debug("GPS-Datenpuffer geleert.")

    def handle_status_data(self, csv_data):
        """Verarbeitet empfangene Status-Nachrichten."""
        logging.debug(f"handle_status_data called with data: {csv_data}")
        parts = csv_data.split(",")
        if len(parts) >= 3 and parts[0] == "problem":
            logging.debug(f"Empfangene Problemzonen-Daten: {csv_data}")
            if csv_data != "problem,-1,-1":
                try:
                    _, lat_str, lon_str = parts[:3]
                    problem_data = {"lat": float(lat_str), "lon": float(lon_str), "timestamp": time.time()}

                    # Füge nur hinzu, wenn nicht schon sehr ähnliche Koordinate kürzlich hinzugefügt wurde
                    # (Einfache Prüfung, um Duplikate bei schnellen Meldungen zu vermeiden)
                    is_duplicate = False
                    if self.problemzonen_data:
                        last_problem = self.problemzonen_data[-1]
                        time_diff = time.time() - last_problem.get('timestamp', 0)
                        lat_diff = abs(problem_data['lat'] - last_problem.get('lat', 0))
                        lon_diff = abs(problem_data['lon'] - last_problem.get('lon', 0))
                        if time_diff < 10 and lat_diff < 0.00001 and lon_diff < 0.00001:
                            is_duplicate = True
                            logging.debug(f"Problemzone {problem_data} als Duplikat erkannt, wird ignoriert.")

                    if not is_duplicate:
                        self.problemzonen_data.append(problem_data)
                        logging.info(f"Problemzone hinzugefügt: {problem_data}")

                        # Alte Problemzonen entfernen und speichern
                        self.data_manager.remove_old_problemzonen()
                        # Lade die aktualisierten Daten nach dem Entfernen alter Daten
                        # self.problemzonen_data = self.data_manager.load_problemzonen_data() # Lade neu aus Datei
                        # Oder: Arbeite direkt mit dem deque weiter, das in remove_old_problemzonen modifiziert wurde
                        self.data_manager.save_problemzonen_data(
                            self.problemzonen_data)  # Speichere das modifizierte deque

                        # Aktualisiere die Problemzonen-Heatmap
                        self.update_single_heatmap("problemzonen_heatmap", list(self.problemzonen_data), False)

                except ValueError:
                    logging.error(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}")
                except Exception as e:
                    logging.error(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}",
                                  exc_info=True)
            else:
                logging.info("End-Marker für Problemzonen empfangen.")
        else:
            logging.info(f"Empfangene Statusmeldung: {csv_data}")

    def update_single_heatmap(self, config_key, data, draw_path):
        """
        Aktualisiert eine einzelne Heatmap (HTML und PNG).

        Args:
            config_key (str): Der Schlüssel in HEATMAP_CONFIG.
            data (list): Die Datenpunkte für die Heatmap.
            draw_path (bool): Ob der Pfad gezeichnet werden soll.
        """
        if config_key in HEATMAP_CONFIG:
            config = HEATMAP_CONFIG[config_key]
            logging.debug(f"Aktualisiere Heatmap: {config_key}")

            if not data:
                logging.warning(f"Keine Daten zum Aktualisieren der Heatmap '{config_key}' vorhanden.")
                # Optional: Leere Karte erstellen oder alte löschen? Aktuell: Nichts tun.
                return

            try:
                # Erstelle interaktive Karte
                self.heatmap_generator.create_heatmap(data, config["output"], draw_path)

                # Erstelle PNG von temporärer Satellitenkarte
                if "png_output" in config:
                    logging.debug(f"Generiere PNG: {config_key}")
                    self.heatmap_generator.save_html_as_png(data, draw_path, config["png_output"],
                                                            config_key_hint=config_key)
            except KeyError as e:
                logging.error(f"Fehlender Schlüssel in HEATMAP_CONFIG für '{config_key}': {e}")
            except Exception as e:
                logging.error(f"Fehler beim Aktualisieren der Heatmap '{config_key}': {e}", exc_info=True)
        else:
            logging.warning(f"Heatmap-Key '{config_key}' nicht in HEATMAP_CONFIG gefunden.")


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
