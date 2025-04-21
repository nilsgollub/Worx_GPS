# data_manager.py
import json
import os
from datetime import datetime, timedelta
from collections import deque
from config import PROBLEM_CONFIG  # Annahme: PROBLEM_CONFIG ist in config.py korrekt definiert
import glob
import logging
from pathlib import Path  # pathlib importieren

# Hole den Logger (Konfiguration sollte im Hauptskript erfolgen)
logger = logging.getLogger(__name__)


class DataManager:
    def __init__(self, data_folder="data"):  # data_folder als Argument akzeptieren
        """
        Initialisiert den DataManager.

        Args:
            data_folder (str): Der Ordner, in dem Mähvorgangs- und Problemzonendaten gespeichert werden.
        """
        self.data_folder = Path(data_folder)  # data_folder als Path-Objekt speichern
        # Pfad zur Problemzonen-Datei relativ zum data_folder konstruieren
        # Verwende .get() für Sicherheit, falls Keys in PROBLEM_CONFIG fehlen
        self.problem_json_path = self.data_folder / PROBLEM_CONFIG.get("problem_json", "problemzonen.json")
        self.max_problemzonen = PROBLEM_CONFIG.get("max_problemzonen", 100)
        self.problemzonen_data = deque(maxlen=self.max_problemzonen)

        # Stelle sicher, dass der Datenordner existiert
        try:
            self.data_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Datenordner sichergestellt: {self.data_folder}")
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Datenordners {self.data_folder}: {e}")
            # Hier könnte man überlegen, ob man einen Fehler auslöst oder weitermacht

        self.load_problemzonen_data()  # Lade Problemzonen während der Initialisierung
        logger.info("DataManager initialisiert.")

    def save_gps_data(self, data, filename):
        """
        Speichert GPS-Daten in einer JSON-Datei im Datenordner.

        Args:
            data (list): Die Liste der GPS-Datenpunkte.
            filename (str): Der Dateiname (ohne Pfad).
        """
        file_path = self.data_folder / filename  # Verwende self.data_folder
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)  # Füge indent für Lesbarkeit hinzu
            logging.info(f"GPS-Daten erfolgreich in {file_path} gespeichert.")
        except TypeError as e:
            logging.error(f"Fehler beim Serialisieren der GPS-Daten für {file_path}: {e}")
        except OSError as e:
            logging.error(f"Fehler beim Schreiben der GPS-Daten in {file_path}: {e}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Speichern der GPS-Daten in {file_path}: {e}", exc_info=True)

    def save_problemzonen_data(self):
        """Speichert die aktuellen Problemzonen-Daten (aus self.problemzonen_data) in der JSON-Datei."""
        try:
            # Verwende self.problem_json_path
            with open(self.problem_json_path, "w") as f:
                # Konvertiere deque zu Liste für JSON
                json.dump(list(self.problemzonen_data), f, indent=4)  # Füge indent hinzu
            logging.info(f"Problemzonen-Daten erfolgreich in {self.problem_json_path} gespeichert.")
        except TypeError as e:
            logging.error(f"Fehler beim Serialisieren der Problemzonen-Daten für {self.problem_json_path}: {e}")
        except OSError as e:
            logging.error(f"Fehler beim Schreiben der Problemzonen-Daten in {self.problem_json_path}: {e}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Speichern der Problemzonen-Daten in {self.problem_json_path}: {e}",
                          exc_info=True)

    def load_problemzonen_data(self):
        """Lädt Problemzonen-Daten aus der JSON-Datei in das deque."""
        try:
            # Verwende self.problem_json_path
            if self.problem_json_path.exists():
                with open(self.problem_json_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # Füge nur gültige Einträge hinzu (optional, aber robuster)
                        valid_entries = [
                            entry for entry in data
                            if isinstance(entry, dict) and
                               'lat' in entry and 'lon' in entry and 'timestamp' in entry and
                               isinstance(entry['lat'], (int, float)) and
                               isinstance(entry['lon'], (int, float)) and
                               isinstance(entry['timestamp'], (int, float))
                        ]
                        invalid_count = len(data) - len(valid_entries)
                        if invalid_count > 0:
                            logging.warning(
                                f"{invalid_count} ungültige Einträge in {self.problem_json_path} ignoriert.")

                        # Füge gültige Daten zum deque hinzu (beachtet maxlen)
                        self.problemzonen_data.extend(valid_entries)
                        logging.info(f"{len(valid_entries)} gültige Problemzonen aus {self.problem_json_path} geladen.")
                    else:
                        logging.warning(
                            f"Ungültiges Format in {self.problem_json_path}: Erwartete Liste, bekam {type(data)}")
            else:
                logging.info(f"Problemzonen-Datei {self.problem_json_path} nicht gefunden. Starte mit leerer Liste.")
        except json.JSONDecodeError as e:
            logging.error(f"Fehler beim Parsen der JSON-Daten in {self.problem_json_path}: {e}")
        except OSError as e:
            logging.error(f"Fehler beim Lesen der Problemzonen-Datei {self.problem_json_path}: {e}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Laden der Problemzonen-Daten aus {self.problem_json_path}: {e}",
                          exc_info=True)
        # Kein Rückgabewert nötig, modifiziert self.problemzonen_data direkt

    def read_problemzonen_data(self):
        """Gibt die aktuellen Problemzonen als Liste zurück."""
        # Gibt eine Kopie als Liste zurück
        return list(self.problemzonen_data)

    def add_problemzone(self, problem_data):
        """
        Fügt eine neue Problemzone hinzu, prüft auf Duplikate, entfernt alte Zonen und speichert.

        Args:
            problem_data (dict): Die Daten der neuen Problemzone {'lat': float, 'lon': float, 'timestamp': float}.

        Returns:
            bool: True, wenn eine Zone hinzugefügt wurde, False, wenn es ein Duplikat war.
        """
        # Prüfe auf Duplikate (innerhalb von 10 Sekunden und sehr nah)
        is_duplicate = False
        if self.problemzonen_data:
            try:
                last_problem = self.problemzonen_data[-1]
                time_diff = problem_data['timestamp'] - last_problem.get('timestamp', 0)
                lat_diff = abs(problem_data['lat'] - last_problem.get('lat', 0))
                lon_diff = abs(problem_data['lon'] - last_problem.get('lon', 0))
                # Schwellenwerte ggf. anpassen
                if time_diff < 10 and lat_diff < 0.00001 and lon_diff < 0.00001:
                    is_duplicate = True
                    logging.debug(f"Problemzone {problem_data} als Duplikat erkannt, wird ignoriert.")
            except (KeyError, TypeError) as e:
                logging.warning(f"Fehler beim Prüfen auf Duplikate: {e}. Füge Zone trotzdem hinzu.")

        if not is_duplicate:
            self.problemzonen_data.append(problem_data)
            logging.info(f"Problemzone hinzugefügt: {problem_data}")
            # Alte Problemzonen entfernen
            self.remove_old_problemzonen()
            # Speichere das aktualisierte deque
            self.save_problemzonen_data()  # Ruft die angepasste Methode ohne Argument auf
            return True  # Signalisiert, dass eine Zone hinzugefügt wurde
        return False  # Signalisiert, dass es ein Duplikat war

    def remove_old_problemzonen(self):
        """Entfernt Problemzonen, die älter als 60 Tage sind, direkt im deque."""
        two_months_ago = datetime.now() - timedelta(days=60)
        initial_count = len(self.problemzonen_data)
        removed_count = 0

        # Erstelle ein neues deque mit den zu behaltenden Elementen
        # (deque unterstützt kein effizientes Entfernen aus der Mitte)
        kept_zones = deque(maxlen=self.max_problemzonen)
        for item in self.problemzonen_data:
            try:
                # Prüfe, ob 'timestamp' existiert und ein gültiger Zeitstempel ist
                if 'timestamp' in item and isinstance(item['timestamp'], (int, float)):
                    item_time = datetime.fromtimestamp(item["timestamp"])
                    if item_time >= two_months_ago:
                        kept_zones.append(item)
                    else:
                        removed_count += 1
                else:
                    logging.warning(f"Problemzone ohne gültigen Timestamp gefunden und entfernt: {item}")
                    removed_count += 1
            except (TypeError, ValueError, OSError) as e:  # ValueError/OSError für ungültige Timestamps
                logging.warning(f"Fehler beim Verarbeiten des Timestamps in Problemzone {item}: {e}. Entferne Element.")
                removed_count += 1

        if removed_count > 0:
            logging.info(f"{removed_count} alte oder ungültige Problemzonen entfernt.")
            # Ersetze das alte deque durch das neue
            self.problemzonen_data = kept_zones
            # Hinweis: save_problemzonen_data() muss danach aufgerufen werden,
            # was in add_problemzone() geschieht.

    def get_next_mow_filename(self):
        """Generiert den nächsten Dateinamen für einen Mähvorgang (z.B. maehvorgang_123.json) im Datenordner."""
        highest_number = 0
        try:
            # Verwende self.data_folder und glob
            pattern = self.data_folder / "maehvorgang_*.json"
            files = glob.glob(str(pattern))  # glob braucht einen String

            for file_path_str in files:
                file_path = Path(file_path_str)  # Konvertiere zu Path
                try:
                    # Extrahiere die Nummer aus dem Dateinamen
                    parts = file_path.stem.split('_')  # stem entfernt .json
                    if len(parts) == 2 and parts[0] == "maehvorgang":
                        number = int(parts[1])
                        highest_number = max(highest_number, number)
                    else:
                        logging.warning(f"Ungültiger Dateiname ignoriert: {file_path.name}")
                except (ValueError, IndexError):
                    logging.warning(f"Ungültiger Dateiname ignoriert (Fehler beim Parsen): {file_path.name}")
                    continue
        except Exception as e:
            logging.error(f"Fehler beim Ermitteln des nächsten Dateinamens in {self.data_folder}: {e}", exc_info=True)
            # Fallback auf einen generischen Namen bei Fehlern
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"maehvorgang_error_{timestamp_str}.json"

        next_number = highest_number + 1
        return f"maehvorgang_{next_number}.json"

    def load_all_mow_data(self):
        """Lädt alle Mähvorgangsdaten aus den JSON-Dateien im Datenordner."""
        all_mow_data = []
        try:
            # Verwende self.data_folder und glob
            json_pattern = self.data_folder / "maehvorgang_*.json"
            # Sortiere nach Änderungszeit, um eine konsistente Reihenfolge zu haben
            json_files = sorted(glob.glob(str(json_pattern)), key=os.path.getmtime)

            if not json_files:
                logging.info(f"Keine Mähvorgangsdateien in '{self.data_folder}' gefunden.")
                return []

            logging.info(f"Lade Daten aus {len(json_files)} Mähvorgangsdateien in '{self.data_folder}'...")
            for json_file_path in json_files:
                try:
                    with open(json_file_path, "r") as f:
                        data = json.load(f)
                        # Optional: Validierung der Datenstruktur hier hinzufügen
                        if isinstance(data, list):
                            all_mow_data.append(data)
                        else:
                            logging.warning(
                                f"Ungültiges Format in {json_file_path}: Erwartete Liste, bekam {type(data)}. Überspringe Datei.")
                except json.JSONDecodeError as e:
                    logging.error(f"Fehler beim Parsen der JSON-Daten in {json_file_path}: {e}")
                except OSError as e:
                    logging.error(f"Fehler beim Lesen der Mähvorgangsdatei {json_file_path}: {e}")
                except Exception as e:
                    logging.error(f"Unerwarteter Fehler beim Lesen von {json_file_path}: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Fehler beim Suchen nach Mähvorgangsdateien in {self.data_folder}: {e}", exc_info=True)

        return all_mow_data

    def load_last_mow_data(self, count=1):
        """
        Lädt die Daten der letzten 'count' Mähvorgänge aus dem Datenordner.

        Args:
            count (int): Die Anzahl der letzten Mähvorgänge, die geladen werden sollen.

        Returns:
            list: Eine Liste von Mähvorgängen (jeder Mähvorgang ist eine Liste von Punkten).
                  Gibt eine leere Liste zurück, wenn keine Daten gefunden wurden oder Fehler auftraten.
        """
        last_mow_data = []
        try:
            # Verwende self.data_folder und glob
            json_pattern = self.data_folder / "maehvorgang_*.json"
            # Finde alle Dateien und sortiere sie nach Änderungszeit (neueste zuerst)
            json_files = sorted(glob.glob(str(json_pattern)), key=os.path.getmtime, reverse=True)

            if not json_files:
                logging.info(f"Keine Mähvorgangsdateien in '{self.data_folder}' gefunden.")
                return []

            # Lade die gewünschte Anzahl der neuesten Dateien
            files_to_load = json_files[:count]
            logging.info(f"Lade die letzten {len(files_to_load)} Mähvorgänge...")

            # Lade in chronologischer Reihenfolge (älteste zuerst in der Ergebnisliste)
            for json_file_path in reversed(files_to_load):
                try:
                    with open(json_file_path, "r") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            last_mow_data.append(data)
                        else:
                            logging.warning(
                                f"Ungültiges Format in {json_file_path}: Erwartete Liste, bekam {type(data)}. Überspringe Datei.")
                except json.JSONDecodeError as e:
                    logging.error(f"Fehler beim Parsen der JSON-Daten in {json_file_path}: {e}")
                except OSError as e:
                    logging.error(f"Fehler beim Lesen der Mähvorgangsdatei {json_file_path}: {e}")
                except Exception as e:
                    logging.error(f"Unerwarteter Fehler beim Lesen von {json_file_path}: {e}", exc_info=True)

        except Exception as e:
            logging.error(f"Fehler beim Suchen/Sortieren der Mähvorgangsdateien in {self.data_folder}: {e}",
                          exc_info=True)

        return last_mow_data


# --- Beispielhafte Verwendung (optional, für Tests) ---
if __name__ == '__main__':
    # Konfiguriere Logging für den Test
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
    import time  # Importiere time für Tests

    # Erstelle einen Test-Datenordner
    test_folder = "test_data_manager"
    # Verwende Path für Ordnererstellung
    Path(test_folder).mkdir(exist_ok=True)

    # Initialisiere DataManager mit Testordner
    dm = DataManager(data_folder=test_folder)

    # Test 1: Problemzonen hinzufügen und speichern
    print("\n--- Test Problemzonen ---")
    dm.add_problemzone({'lat': 46.1, 'lon': 7.1, 'timestamp': time.time() - 70 * 24 * 3600})  # Älter als 60 Tage
    dm.add_problemzone({'lat': 46.2, 'lon': 7.2, 'timestamp': time.time() - 10 * 24 * 3600})  # Jünger
    dm.add_problemzone({'lat': 46.3, 'lon': 7.3, 'timestamp': time.time()})  # Ganz neu
    dm.add_problemzone({'lat': 46.3, 'lon': 7.3, 'timestamp': time.time() + 2})  # Duplikat-Test
    print(f"Aktuelle Problemzonen: {dm.read_problemzonen_data()}")
    # remove_old_problemzonen wird in add_problemzone aufgerufen
    print(f"Problemzonen nach potenzieller Bereinigung: {dm.read_problemzonen_data()}")

    # Test 2: Nächsten Dateinamen generieren
    print("\n--- Test Dateinamen ---")
    # Erstelle Dummy-Dateien mit Path
    Path(test_folder, "maehvorgang_1.json").touch()
    Path(test_folder, "maehvorgang_3.json").touch()
    Path(test_folder, "maehvorgang_abc.json").touch()  # Ungültig
    next_name = dm.get_next_mow_filename()
    print(f"Nächster Dateiname sollte 'maehvorgang_4.json' sein: {next_name}")

    # Test 3: GPS-Daten speichern
    print("\n--- Test GPS Speichern ---")
    test_gps_data = [{'lat': 46.5, 'lon': 7.5, 'timestamp': time.time()}]
    dm.save_gps_data(test_gps_data, next_name)

    # Test 4: Alle Mähdaten laden
    print("\n--- Test Alle Laden ---")
    all_data = dm.load_all_mow_data()
    print(f"Anzahl geladener Mähvorgänge: {len(all_data)}")
    if all_data:
        print(f"Erster geladener Mähvorgang (Beispiel): {all_data[0][:2]}...")  # Zeige nur die ersten paar Punkte

    # Test 5: Letzte Mähdaten laden
    print("\n--- Test Letzte Laden ---")
    last_data = dm.load_last_mow_data(count=2)  # Lade die letzten 2
    print(f"Anzahl der letzten geladenen Mähvorgänge: {len(last_data)}")
    if last_data:
        print(f"Zuletzt geladener Mähvorgang (Beispiel): {last_data[-1][:2]}...")

    # Aufräumen (optional)
    # import shutil
    # shutil.rmtree(test_folder)
    # print(f"\nTestordner {test_folder} gelöscht.")
