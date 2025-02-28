# data_manager.py
import json
import os
from datetime import datetime, timedelta
from collections import deque
from config import PROBLEM_CONFIG
import glob


class DataManager:
    def __init__(self):
        self.problem_json = PROBLEM_CONFIG["problem_json"]
        self.max_problemzonen = PROBLEM_CONFIG["max_problemzonen"]
        self.problemzonen_data = deque(maxlen=self.max_problemzonen)
        self.load_problemzonen_data()  # lade die Problemzonen beim initialisieren

    def save_gps_data(self, data, filename):
        """Speichert GPS-Daten in einer JSON-Datei."""
        try:
            with open(filename, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Fehler beim Speichern der GPS-Daten: {e}")

    def save_problemzonen_data(self, data):
        """Speichert Problemzonen-Daten in einer JSON-Datei."""
        try:
            with open(self.problem_json, "w") as f:
                json.dump(list(data), f)  # Konvertiere deque zu Liste für JSON
        except Exception as e:
            print(f"Fehler beim Speichern der Problemzonen-Daten: {e}")

    def load_problemzonen_data(self):
        """Lädt Problemzonen-Daten aus der JSON-Datei."""
        try:
            if os.path.exists(self.problem_json):
                with open(self.problem_json, "r") as f:
                    data = json.load(f)
                    self.problemzonen_data.extend(data)  # Daten aus JSON in deque
            else:
                return []
        except Exception as e:
            print(f"Fehler beim Lesen der Problemzonen-Daten: {e}")
            return []

    def read_problemzonen_data(self):
        """Gibt die aktuellen Problemzonen zurück"""
        return self.problemzonen_data

    def remove_old_problemzonen(self):
        """Entfernt Problemzonen, die älter als 2 Monate sind."""
        two_months_ago = datetime.now() - timedelta(days=60)
        filtered_problemzonen = []
        for item in self.problemzonen_data:
            if datetime.fromtimestamp(item["timestamp"]) >= two_months_ago:
                filtered_problemzonen.append(item)
        self.problemzonen_data = deque(filtered_problemzonen, maxlen=self.max_problemzonen)

    def get_next_mow_filename(self, folder="."):
        """Generiert den nächsten Dateinamen für einen Mähvorgang."""
        # Liste alle JSON-Dateien im Ordner auf
        files = [f for f in os.listdir(folder) if f.startswith("maehvorgang_") and f.endswith(".json")]

        if not files:
            return "maehvorgang_1.json"  # Erste Datei, falls keine vorhanden

        # Finde die höchste Nummer
        highest_number = 0
        for file in files:
            try:
                number = int(file.split("_")[1].split(".")[0])
                highest_number = max(highest_number, number)
            except (ValueError, IndexError):
                print(f"Ungültiger Dateiname: {file}")
                continue
        return f"maehvorgang_{highest_number + 1}.json"  # Nächste Nummer

    def load_all_mow_data(self, folder="."):
        """Lädt alle Mähvorgangsdaten aus den JSON-Dateien."""
        all_mow_data = []
        # Erstelle das Suchmuster für alle JSON-Dateien
        json_pattern = os.path.join(folder, "maehvorgang_*.json")
        # Suche alle JSON-Dateien, die dem Muster entsprechen
        json_files = glob.glob(json_pattern)

        for json_file in json_files:
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                    all_mow_data.append(data)
            except Exception as e:
                print(f"Fehler beim Lesen der Mähvorgangsdaten aus {json_file}: {e}")
        return all_mow_data

    def load_last_mow_data(self, folder="."):
        """Lädt die Daten des letzten Mähvorgangs."""
        # Liste alle JSON-Dateien im Ordner auf
        files = [f for f in os.listdir(folder) if f.startswith("maehvorgang_") and f.endswith(".json")]
        if not files:
            return []  # Keine Dateien vorhanden

        # Finde die neueste Datei
        latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(folder, f)))
        try:
            with open(os.path.join(folder, latest_file), "r") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Fehler beim Lesen der Mähvorgangsdaten aus {latest_file}: {e}")
            return []
