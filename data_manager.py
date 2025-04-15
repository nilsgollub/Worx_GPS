# data_manager.py
import json
import os
from datetime import datetime, timedelta
from collections import deque
from config import PROBLEM_CONFIG
import glob
import logging  # Logging importieren

# Logging konfigurieren (optional, aber empfohlen)
# Setze das Level nach Bedarf (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DataManager:
    def __init__(self):
        self.problem_json = PROBLEM_CONFIG["problem_json"]
        self.max_problemzonen = PROBLEM_CONFIG["max_problemzonen"]
        self.problemzonen_data = deque(maxlen=self.max_problemzonen)
        self.load_problemzonen_data()  # lade die Problemzonen beim initialisieren
        logging.info("DataManager initialisiert.")  # Log nach Initialisierung

    def save_gps_data(self, data, filename):
        """Speichert GPS-Daten in einer JSON-Datei."""
        try:
            with open(filename, "w") as f:
                json.dump(data, f)
            logging.info(f"GPS-Daten erfolgreich in {filename} gespeichert.")  # Log Erfolg
        except Exception as e:
            # print(f"Fehler beim Speichern der GPS-Daten: {e}") # ALT
            logging.error(f"Fehler beim Speichern der GPS-Daten in {filename}: {e}")  # NEU

    def save_problemzonen_data(self, data):
        """Speichert Problemzonen-Daten in einer JSON-Datei."""
        try:
            with open(self.problem_json, "w") as f:
                json.dump(list(data), f)  # Konvertiere deque zu Liste für JSON
            logging.info(f"Problemzonen-Daten erfolgreich in {self.problem_json} gespeichert.")  # Log Erfolg
        except Exception as e:
            # print(f"Fehler beim Speichern der Problemzonen-Daten: {e}") # ALT
            logging.error(f"Fehler beim Speichern der Problemzonen-Daten in {self.problem_json}: {e}")  # NEU

    def load_problemzonen_data(self):
        """Lädt Problemzonen-Daten aus der JSON-Datei und gibt das deque zurück."""
        try:
            if os.path.exists(self.problem_json):
                with open(self.problem_json, "r") as f:
                    data = json.load(f)
                    # --- Korrektur: Sicherstellen, dass nur gültige Daten hinzugefügt werden ---
                    if isinstance(data, list):
                        self.problemzonen_data.extend(data)  # Daten aus JSON in deque
                        logging.info(f"{len(data)} Problemzonen aus {self.problem_json} geladen.")
                    else:
                        logging.warning(
                            f"Ungültiges Format in {self.problem_json}: Erwartete Liste, bekam {type(data)}")
                        # Optional: Hier leere Liste zurückgeben oder Fehler auslösen
                        # return [] # Oder raise TypeError(...)
                    # --- Ende Korrektur ---
            else:
                logging.info(f"Problemzonen-Datei {self.problem_json} nicht gefunden. Starte mit leerer Liste.")
                # return [] # Alte Version: Rückgabe hier war inkonsistent
        except json.JSONDecodeError as e:  # Spezifischer Fehler für JSON
            logging.error(f"Fehler beim Parsen der JSON-Daten in {self.problem_json}: {e}")
            # return [] # Alte Version
        except Exception as e:
            # print(f"Fehler beim Lesen der Problemzonen-Daten: {e}") # ALT
            logging.error(f"Fehler beim Lesen der Problemzonen-Daten aus {self.problem_json}: {e}")  # NEU
            # return [] # Alte Version

        # Gib immer das aktuelle (möglicherweise leere) deque zurück
        return self.problemzonen_data
        # --- Ende Korrektur ---

    def read_problemzonen_data(self):
        """Gibt die aktuellen Problemzonen zurück"""
        return self.problemzonen_data

    def remove_old_problemzonen(self):
        """Entfernt Problemzonen, die älter als 2 Monate sind."""
        two_months_ago = datetime.now() - timedelta(days=60)
        initial_count = len(self.problemzonen_data)
        # Filtere direkt im deque (effizienter als neue Liste zu erstellen)
        # Gehe rückwärts durch, um Indizes beim Entfernen nicht zu verschieben
        removed_count = 0
        for i in range(len(self.problemzonen_data) - 1, -1, -1):
            item = self.problemzonen_data[i]
            try:
                # Füge eine Prüfung hinzu, ob 'timestamp' existiert und ein Float ist
                if 'timestamp' in item and isinstance(item['timestamp'], (int, float)):
                    if datetime.fromtimestamp(item["timestamp"]) < two_months_ago:
                        del self.problemzonen_data[i]
                        removed_count += 1
                else:
                    logging.warning(f"Problemzone ohne gültigen Timestamp gefunden und entfernt: {item}")
                    del self.problemzonen_data[i]
                    removed_count += 1
            except TypeError as e:
                logging.warning(f"Fehler beim Verarbeiten des Timestamps in Problemzone {item}: {e}. Entferne Element.")
                del self.problemzonen_data[i]
                removed_count += 1

        if removed_count > 0:
            logging.info(f"{removed_count} alte Problemzonen entfernt.")
        # Das deque wird direkt modifiziert, keine Neuzuweisung nötig

    def get_next_mow_filename(self, folder="."):
        """Generiert den nächsten Dateinamen für einen Mähvorgang."""
        try:
            # Liste alle JSON-Dateien im Ordner auf
            files = [f for f in os.listdir(folder) if f.startswith("maehvorgang_") and f.endswith(".json")]
        except FileNotFoundError:
            logging.warning(f"Ordner '{folder}' für Mähvorgänge nicht gefunden. Erstelle maehvorgang_1.json.")
            return "maehvorgang_1.json"
        except Exception as e:
            logging.error(f"Fehler beim Auflisten des Ordners '{folder}': {e}")
            # Fallback oder Fehler auslösen? Hier Fallback:
            return "maehvorgang_error.json"

        if not files:
            return "maehvorgang_1.json"  # Erste Datei, falls keine vorhanden

        # Finde die höchste Nummer
        highest_number = 0
        for file in files:
            try:
                # Teile Dateinamen: maehvorgang_NUMBER.json
                parts = file.split('.')[0].split('_')
                if len(parts) == 2 and parts[0] == "maehvorgang":
                    number = int(parts[1])
                    highest_number = max(highest_number, number)
                else:
                    # print(f"Ungültiger Dateiname: {file}") # ALT
                    logging.warning(f"Ungültiger Dateiname ignoriert: {file}")  # NEU
            except (ValueError, IndexError):
                # print(f"Ungültiger Dateiname: {file}") # ALT
                logging.warning(f"Ungültiger Dateiname ignoriert (Fehler beim Parsen): {file}")  # NEU
                continue
        return f"maehvorgang_{highest_number + 1}.json"  # Nächste Nummer

    def load_all_mow_data(self, folder="."):
        """Lädt alle Mähvorgangsdaten aus den JSON-Dateien."""
        all_mow_data = []
        # Erstelle das Suchmuster für alle JSON-Dateien
        json_pattern = os.path.join(folder, "maehvorgang_*.json")
        # Suche alle JSON-Dateien, die dem Muster entsprechen
        json_files = glob.glob(json_pattern)

        if not json_files:
            logging.info(f"Keine Mähvorgangsdateien in '{folder}' gefunden.")
            return []

        logging.info(f"Lade Daten aus {len(json_files)} Mähvorgangsdateien in '{folder}'...")
        for json_file in json_files:
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                    all_mow_data.append(data)
            except json.JSONDecodeError as e:
                logging.error(f"Fehler beim Parsen der JSON-Daten in {json_file}: {e}")
            except Exception as e:
                # print(f"Fehler beim Lesen der Mähvorgangsdaten aus {json_file}: {e}") # ALT
                logging.error(f"Fehler beim Lesen der Mähvorgangsdaten aus {json_file}: {e}")  # NEU
        return all_mow_data

    def load_last_mow_data(self, folder="."):
        """Lädt die Daten des letzten Mähvorgangs."""
        try:
            # Liste alle JSON-Dateien im Ordner auf
            files = [f for f in os.listdir(folder) if f.startswith("maehvorgang_") and f.endswith(".json")]
        except FileNotFoundError:
            logging.warning(f"Ordner '{folder}' für Mähvorgänge nicht gefunden.")
            return []
        except Exception as e:
            logging.error(f"Fehler beim Auflisten des Ordners '{folder}': {e}")
            return []

        if not files:
            logging.info(f"Keine Mähvorgangsdateien in '{folder}' gefunden.")
            return []  # Keine Dateien vorhanden

        try:
            # Finde die neueste Datei basierend auf der Änderungszeit
            latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(folder, f)))
            latest_file_path = os.path.join(folder, latest_file)
            logging.info(f"Lade letzten Mähvorgang: {latest_file_path}")
            with open(latest_file_path, "r") as f:
                data = json.load(f)
                return data
        except ValueError as e:  # Kann auftreten, wenn getctime fehlschlägt
            logging.error(f"Fehler beim Ermitteln der neuesten Datei in '{folder}': {e}")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"Fehler beim Parsen der JSON-Daten in {latest_file_path}: {e}")
            return []
        except Exception as e:
            # print(f"Fehler beim Lesen der Mähvorgangsdaten aus {latest_file}: {e}") # ALT
            logging.error(f"Fehler beim Lesen der letzten Mähvorgangsdaten aus {latest_file_path}: {e}")  # NEU
            return []
