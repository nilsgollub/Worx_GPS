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

# Logging konfigurieren (optional, aber empfohlen)
# Setze das Level nach Bedarf (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class WorxGps:
    # Entferne test_mode aus den Parametern
    def __init__(self):
        # Lies test_mode aus der Konfiguration (REC_CONFIG)
        self.test_mode = REC_CONFIG["test_mode"]
        # bergib den gelesenen Wert an MqttHandler
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.heatmap_generator = HeatmapGenerator()
        self.data_manager = DataManager()
        self.gps_data_buffer = ""
        # --- Korrektur/Vereinheitlichung: Verwende deque für maehvorgang_data ---
        # self.maehvorgang_data = [] # Alte Version
        self.maehvorgang_data = deque(maxlen=10)  # Verwende deque mit Limit (z.B. 10)
        # --- Ende Korrektur ---
        self.alle_maehvorgang_data = []
        self.maehvorgang_count = 0  # Wird aktuell nicht verwendet, könnte entfernt werden
        # Hole problemzonen_data vom DataManager nach dessen Initialisierung
        self.problemzonen_data = self.data_manager.read_problemzonen_data()
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()
        logging.info("WorxGps initialisiert.")  # Log nach Initialisierung

    def on_mqtt_message(self, msg):
        """Verarbeitet eingehende MQTT-Nachrichten."""
        try:
            payload_decoded = msg.payload.decode()
            if msg.topic == self.mqtt_handler.topic_gps:
                self.handle_gps_data(payload_decoded)
            elif msg.topic == self.mqtt_handler.topic_status:
                self.handle_status_data(payload_decoded)
            # Optional: Loggen von Nachrichten auf anderen Topics
            else:
                logging.debug(f"Nachricht auf unbehandeltem Topic empfangen: {msg.topic}")  # NEU
        except UnicodeDecodeError:
            # print(f"Fehler beim Dekodieren der MQTT-Nachricht auf Topic {msg.topic}") # ALT
            logging.error(f"Fehler beim Dekodieren der MQTT-Nachricht auf Topic {msg.topic}")  # NEU
        except Exception as e:
            # print(f"Fehler in on_mqtt_message: {e}") # ALT
            logging.error(f"Fehler in on_mqtt_message: {e}", exc_info=True)  # NEU (exc_info=True fügt Traceback hinzu)

    def handle_gps_data(self, csv_data):
        """Verarbeitet empfangene GPS-Daten (CSV-Format)."""
        if csv_data != "-1":  # Ende-Marker noch nicht erreicht
            self.gps_data_buffer += csv_data  # Daten zum Puffer hinzufügen
        else:
            # Ende-Marker erreicht, Daten verarbeiten
            logging.info("End-Marker für GPS-Daten empfangen, verarbeite Puffer...")  # Log
            gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            if gps_data:
                logging.info(f"{len(gps_data)} GPS-Punkte aus Puffer gelesen.")  # Log
                # Definiere die erwarteten Keys für die Heatmap-Konfiguration
                heatmap_aktuell_key = "heatmap_aktuell"
                heatmap_10_key = "heatmap_10_maehvorgang"
                heatmap_kumuliert_key = "heatmap_kumuliert"
                problemzonen_heatmap_key = "problemzonen_heatmap"

                # Füge die *gesamte Liste* der geparsten Daten als *ein* Element zum Mähvorgang-deque hinzu
                self.maehvorgang_data.append(gps_data)
                # Füge die *einzelnen Punkte* zur Liste aller Daten hinzu
                self.alle_maehvorgang_data.extend(gps_data)

                filename = self.data_manager.get_next_mow_filename()
                self.data_manager.save_gps_data(gps_data, filename)  # Speichern nutzt jetzt Logging

                # --- Heatmap-Generierung ---
                # Aktueller Mähvorgang (nur die zuletzt empfangenen Daten)
                if heatmap_aktuell_key in HEATMAP_CONFIG:
                    # Übergib die Liste der Punkte direkt
                    self.heatmap_generator.create_heatmap(gps_data, HEATMAP_CONFIG[heatmap_aktuell_key]["output"],
                                                          True)  # Pfad zeichnen
                    # Optional: PNG generieren
                    if "png_output" in HEATMAP_CONFIG[heatmap_aktuell_key]:
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[heatmap_aktuell_key]["output"],
                                                                HEATMAP_CONFIG[heatmap_aktuell_key]["png_output"])
                else:
                    # print(f"Warnung: Heatmap-Key '{heatmap_aktuell_key}' nicht in HEATMAP_CONFIG gefunden.") # ALT
                    logging.warning(f"Heatmap-Key '{heatmap_aktuell_key}' nicht in HEATMAP_CONFIG gefunden.")  # NEU

                # Letzte 10 Mähvorgänge
                if heatmap_10_key in HEATMAP_CONFIG:
                    # Konvertiere das deque von Listen in eine flache Liste von Punkten für die Heatmap
                    data_for_heatmap_10 = [point for sublist in self.maehvorgang_data for point in sublist]
                    self.heatmap_generator.create_heatmap(data_for_heatmap_10, HEATMAP_CONFIG[heatmap_10_key]["output"],
                                                          False)
                    # Optional: PNG generieren
                    if "png_output" in HEATMAP_CONFIG[heatmap_10_key]:
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[heatmap_10_key]["output"],
                                                                HEATMAP_CONFIG[heatmap_10_key]["png_output"])
                else:
                    # print(f"Warnung: Heatmap-Key '{heatmap_10_key}' nicht in HEATMAP_CONFIG gefunden.") # ALT
                    logging.warning(f"Heatmap-Key '{heatmap_10_key}' nicht in HEATMAP_CONFIG gefunden.")  # NEU

                # Kumulierte Daten (alle Punkte)
                if heatmap_kumuliert_key in HEATMAP_CONFIG:
                    self.heatmap_generator.create_heatmap(self.alle_maehvorgang_data,
                                                          HEATMAP_CONFIG[heatmap_kumuliert_key]["output"], False)
                    # Optional: PNG generieren
                    if "png_output" in HEATMAP_CONFIG[heatmap_kumuliert_key]:
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[heatmap_kumuliert_key]["output"],
                                                                HEATMAP_CONFIG[heatmap_kumuliert_key]["png_output"])
                else:
                    # print(f"Warnung: Heatmap-Key '{heatmap_kumuliert_key}' nicht in HEATMAP_CONFIG gefunden.") # ALT
                    logging.warning(f"Heatmap-Key '{heatmap_kumuliert_key}' nicht in HEATMAP_CONFIG gefunden.")  # NEU

                # Problemzonen (aktuelle Liste)
                if problemzonen_heatmap_key in HEATMAP_CONFIG:
                    # Konvertiere das deque in eine Liste für die Heatmap
                    problem_data_for_heatmap = list(self.problemzonen_data)
                    self.heatmap_generator.create_heatmap(problem_data_for_heatmap,
                                                          HEATMAP_CONFIG[problemzonen_heatmap_key]["output"], False)
                    # Optional: PNG generieren
                    if "png_output" in HEATMAP_CONFIG[problemzonen_heatmap_key]:
                        self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[problemzonen_heatmap_key]["output"],
                                                                HEATMAP_CONFIG[problemzonen_heatmap_key]["png_output"])
                else:
                    # print(f"Warnung: Heatmap-Key '{problemzonen_heatmap_key}' nicht in HEATMAP_CONFIG gefunden.") # ALT
                    logging.warning(
                        f"Heatmap-Key '{problemzonen_heatmap_key}' nicht in HEATMAP_CONFIG gefunden.")  # NEU
                # --- Ende Heatmap-Generierung ---

            else:
                # Sende Fehlermeldung, wenn das Parsen fehlschlägt oder keine Daten liefert
                # print("Fehler: Konnte keine GPS-Daten aus dem Puffer lesen oder Puffer war leer.") # ALT
                logging.error("Fehler: Konnte keine GPS-Daten aus dem Puffer lesen oder Puffer war leer.")  # NEU
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

            self.gps_data_buffer = ""  # Puffer nach Verarbeitung leeren
            logging.debug("GPS-Datenpuffer geleert.")  # Log

    def handle_status_data(self, csv_data):
        """Verarbeitet empfangene Status-Nachrichten."""
        parts = csv_data.split(",")
        # Prüfe auf Problemzonen-Nachricht
        if len(parts) >= 3 and parts[0] == "problem":
            # print("Empfangene Problemzonen-Daten:", csv_data) # ALT
            logging.debug(f"Empfangene Problemzonen-Daten: {csv_data}")  # NEU (Debug, da es normal ist)
            # Ignoriere den speziellen End-Marker für Problemzonen
            if csv_data != "problem,-1,-1":
                try:
                    _, lat_str, lon_str = parts[:3]  # Nimm nur die ersten drei Teile
                    # Konvertiere Koordinaten und füge Zeitstempel hinzu
                    problem_data = {"lat": float(lat_str), "lon": float(lon_str), "timestamp": time.time()}
                    self.problemzonen_data.append(problem_data)  # Füge zum lokalen deque hinzu
                    logging.info(f"Problemzone hinzugefügt: {problem_data}")  # Log

                    # --- Korrektur: remove_old_problemzonen modifiziert self.problemzonen_data direkt ---
                    # Rufe die Methode auf, die das interne deque des DataManagers modifiziert
                    self.data_manager.remove_old_problemzonen()  # Nutzt jetzt Logging
                    # Aktualisiere das lokale deque mit den Daten aus dem DataManager
                    self.problemzonen_data = self.data_manager.read_problemzonen_data()
                    # --- Ende Korrektur ---

                    # Speichere die (potenziell gefilterten) Problemzonen
                    self.data_manager.save_problemzonen_data(self.problemzonen_data)  # Nutzt jetzt Logging

                    # --- Heatmap-Generierung für Problemzonen ---
                    problemzonen_heatmap_key = "problemzonen_heatmap"
                    if problemzonen_heatmap_key in HEATMAP_CONFIG:
                        # Konvertiere das deque in eine Liste für die Heatmap
                        problem_data_for_heatmap = list(self.problemzonen_data)
                        self.heatmap_generator.create_heatmap(problem_data_for_heatmap,
                                                              HEATMAP_CONFIG[problemzonen_heatmap_key]["output"], False)
                        # Optional: PNG generieren
                        if "png_output" in HEATMAP_CONFIG[problemzonen_heatmap_key]:
                            self.heatmap_generator.save_html_as_png(HEATMAP_CONFIG[problemzonen_heatmap_key]["output"],
                                                                    HEATMAP_CONFIG[problemzonen_heatmap_key][
                                                                        "png_output"])
                    else:
                        # print(f"Warnung: Heatmap-Key '{problemzonen_heatmap_key}' nicht in HEATMAP_CONFIG gefunden.") # ALT
                        logging.warning(
                            f"Heatmap-Key '{problemzonen_heatmap_key}' nicht in HEATMAP_CONFIG gefunden.")  # NEU
                    # --- Ende Heatmap-Generierung ---

                except ValueError:
                    # print(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}") # ALT
                    logging.error(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}")  # NEU
                except Exception as e:
                    # print(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}") # ALT
                    logging.error(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}",
                                  exc_info=True)  # NEU
            else:
                logging.info("End-Marker für Problemzonen empfangen.")  # Log
        else:
            # Behandle andere Statusmeldungen (oder logge sie einfach)
            # print("Empfangene Statusmeldung:", csv_data) # ALT
            logging.info(f"Empfangene Statusmeldung: {csv_data}")  # NEU
            # Hier könnte weitere Logik für andere Statusmeldungen stehen


if __name__ == "__main__":
    # Keine Übergabe von test_mode mehr nötig, wird aus config gelesen
    worx_gps = WorxGps()
    # Optional: Gib aus, in welchem Modus das Skript läuft
    # print(f"Worx_GPS gestartet im {'Testmodus' if worx_gps.test_mode else 'Realmodus'}.") # ALT
    logging.info(f"Worx_GPS gestartet im {'Testmodus' if worx_gps.test_mode else 'Realmodus'}.")  # NEU
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            # print("Beende Worx_GPS...") # ALT
            logging.info("Beende Worx_GPS...")  # NEU
            if worx_gps.mqtt_handler:
                worx_gps.mqtt_handler.disconnect()  # Nutzt jetzt Logging
            break
        except Exception as e:
            # print(f"Unerwarteter Fehler in der Hauptschleife: {e}") # ALT
            logging.error(f"Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)  # NEU
            # Optional: Hier könnte man versuchen, den MQTT-Handler neu zu verbinden
            time.sleep(5)  # Warte kurz, bevor die Schleife weiterläuft
