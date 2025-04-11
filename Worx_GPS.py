# Worx_GPS.py
from mqtt_handler import MqttHandler
from heatmap_generator import HeatmapGenerator
from data_manager import DataManager
from utils import read_gps_data_from_csv_string
# Importiere REC_CONFIG und HEATMAP_CONFIG (HEATMAP_CONFIG war schon da)
from config import HEATMAP_CONFIG, REC_CONFIG
import time


class WorxGps:
    # Entferne test_mode aus den Parametern
    def __init__(self):
        # Lies test_mode aus der Konfiguration (REC_CONFIG)
        self.test_mode = REC_CONFIG["test_mode"]
        # Übergib den gelesenen Wert an MqttHandler
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.heatmap_generator = HeatmapGenerator()
        self.data_manager = DataManager()
        self.gps_data_buffer = ""
        self.maehvorgang_data = []
        self.alle_maehvorgang_data = []
        self.maehvorgang_count = 0
        self.problemzonen_data = self.data_manager.read_problemzonen_data()
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()

    def on_mqtt_message(self, msg):
        if msg.topic == self.mqtt_handler.topic_gps:
            self.handle_gps_data(msg.payload.decode())
        elif msg.topic == self.mqtt_handler.topic_status:
            self.handle_status_data(msg.payload.decode())

    def handle_gps_data(self, csv_data):
        if csv_data != "-1":  # Ende-Marker noch nicht erreicht
            self.gps_data_buffer += csv_data  # Daten zum Puffer hinzufügen
        else:
            # Ende-Marker erreicht, Daten verarbeiten
            gps_data = read_gps_data_from_csv_string(self.gps_data_buffer)
            if gps_data:
                # --- Mögliche Verbesserung: Heatmap-Konfiguration pr, dass die Keys existieren, bevor du darauf zugreifst
                heatmap_aktuell_key = "heatmap_aktuell"  # Beispiel, passe die Keys an deine HEATMAP_CONFIG an
                heatmap_10_key = "heatmap_10_maehvorgang"
                heatmap_kumuliert_key = "heatmap_kumuliert"
                problemzonen_heatmap_key = "problemzonen_heatmap"

                self.maehvorgang_data.append(gps_data)
                self.alle_maehvorgang_data.extend(gps_data)
                filename = self.data_manager.get_next_mow_filename()
                self.data_manager.save_gps_data(gps_data, filename)

                # Sicherer Zugriff auf Heatmap-Konfiguration
                if heatmap_aktuell_key in HEATMAP_CONFIG:
                    self.heatmap_generator.create_heatmap([gps_data], HEATMAP_CONFIG[heatmap_aktuell_key], True)
                if heatmap_10_key in HEATMAP_CONFIG:
                    self.heatmap_generator.create_heatmap(list(self.maehvorgang_data),
                                                          HEATMAP_CONFIG[heatmap_10_key], False)
                if heatmap_kumuliert_key in HEATMAP_CONFIG:
                    self.heatmap_generator.create_heatmap([self.alle_maehvorgang_data],
                                                          HEATMAP_CONFIG[heatmap_kumuliert_key], False)
                if problemzonen_heatmap_key in HEATMAP_CONFIG:
                    # Stelle sicher, dass problemzonen_data eine Liste von Listen ist, falls create_heatmap das erwartet
                    problem_data_for_heatmap = [list(self.problemzonen_data)] if self.problemzonen_data else []
                    self.heatmap_generator.create_heatmap(problem_data_for_heatmap,
                                                          HEATMAP_CONFIG[problemzonen_heatmap_key], False)
                # --- Ende Verbesserungsvorschlag ---
            else:
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")
            self.gps_data_buffer = ""  # Puffer leeren

    def handle_status_data(self, csv_data):
        # Überprüfen, ob es sich um eine Problemmeldung handelt
        parts = csv_data.split(",")
        if len(parts) >= 3 and parts[0] == "problem":  # Mindestens 3 Teile und beginnt mit "problem"
            print("Empfangene Problemzonen-Daten:", csv_data)
            if csv_data != "problem,-1,-1":  # Ende-Marker ignorieren
                try:
                    # CSV-Daten in Dictionary umwandeln (nur lat und lon)
                    _, lat_str, lon_str = parts[:3]  # Nimm nur die ersten drei Teile
                    problem_data = {"lat": float(lat_str), "lon": float(lon_str), "timestamp": time.time()}
                    self.problemzonen_data.append(problem_data)
                    # Rufe remove_old_problemzonen auf, falls es existiert und die Liste zurückgibt
                    if hasattr(self.data_manager, 'remove_old_problemzonen'):
                        self.problemzonen_data = self.data_manager.remove_old_problemzonen(
                            self.problemzonen_data)  # Übergib die aktuelle Liste
                    self.data_manager.save_problemzonen_data(self.problemzonen_data)

                    # --- Mögliche Verbesserung: Heatmap-Konfiguration prüfen ---
                    problemzonen_heatmap_key = "problemzonen_heatmap"
                    if problemzonen_heatmap_key in HEATMAP_CONFIG:
                        # Stelle sicher, dass problemzonen_data eine Liste von Listen ist
                        problem_data_for_heatmap = [list(self.problemzonen_data)] if self.problemzonen_data else []
                        self.heatmap_generator.create_heatmap(problem_data_for_heatmap,
                                                              HEATMAP_CONFIG[problemzonen_heatmap_key], False)
                    # --- Ende Verbesserungsvorschlag ---

                except ValueError:
                    print(f"Fehler beim Konvertieren der Problemzonen-Koordinaten: {csv_data}")
                except Exception as e:
                    print(f"Unerwarteter Fehler bei der Verarbeitung von Problemzonen-Daten: {e}")
        else:
            # Statusmeldung ausgeben
            print("Empfangene Statusmeldung:", csv_data)


if __name__ == "__main__":
    # Keine Übergabe von test_mode mehr nötig, wird aus config gelesen
    worx_gps = WorxGps()
    # Optional: Gib aus, in welchem Modus das Skript läuft
    print(f"Worx_GPS gestartet im {'Testmodus' if worx_gps.test_mode else 'Realmodus'}.")
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("Beende Worx_GPS...")
            if worx_gps.mqtt_handler:
                worx_gps.mqtt_handler.disconnect()
            break
        except Exception as e:
            print(f"Unerwarteter Fehler in der Hauptschleife: {e}")
            # Optional: Hier könnte man versuchen, den MQTT-Handler neu zu verbinden
            time.sleep(5)  # Warte kurz, bevor die Schleife weiterläuft
