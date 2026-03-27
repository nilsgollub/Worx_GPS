# data_sender.py
import paho.mqtt.client as mqtt  # Korrekter Import-Alias
import json
# from config import MQTT_CONFIG # Wird hier nicht direkt benötigt
import time
import logging  # Logging hinzugefügt
import csv  # CSV importieren
import os  # OS importieren für Beispiel

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DataSender:
    def __init__(self, mqtt_broker, mqtt_port, mqtt_user=None, mqtt_password=None):  # Korrekte Signatur
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        # Optional: User/Pass setzen, falls vorhanden
        if mqtt_user and mqtt_password:
            self.mqtt_client.username_pw_set(mqtt_user, mqtt_password)
        # Setze Callbacks (optional, aber gut für Debugging)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logging.error(f"DataSender: Fehler beim Verbinden oder Starten der MQTT-Schleife: {e}")
            raise  # Fehler weitergeben, damit der Aufrufer informiert ist
        self.mqtt_topic_gps = "worx/gps"  # Standard-Topic, kann überschrieben werden

    # Optionale Callbacks für Debugging
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logging.info(f"DataSender: Verbunden mit MQTT Broker: {self.mqtt_broker}")
        else:
            logging.error(f"DataSender: Verbindung fehlgeschlagen mit RC: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logging.info(f"DataSender: Verbindung zum MQTT Broker bewusst getrennt.")
        else:
            logging.warning(f"DataSender: Verbindung zum MQTT Broker unerwartet getrennt. RC: {reason_code}")

    def send_data(self, csv_file):
        """Liest Daten aus einer CSV-Datei und sendet sie als JSON via MQTT."""
        if not self.mqtt_client.is_connected():
            logging.error("DataSender: Nicht mit MQTT Broker verbunden. Senden nicht möglich.")
            return  # Frühzeitiger Ausstieg, wenn nicht verbunden

        try:
            data = self.read_csv(csv_file)
            if not data:  # Nicht senden, wenn keine Daten gelesen wurden
                logging.warning(f"DataSender: Keine gültigen Daten aus {csv_file} gelesen. Sende nichts.")
                return

            json_data = json.dumps(data)
            msg_info = self.mqtt_client.publish(self.mqtt_topic_gps, json_data)

            if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.info(
                    f"DataSender: Daten aus {csv_file} erfolgreich an {self.mqtt_topic_gps} gesendet (mid={msg_info.mid}).")
            else:
                logging.warning(f"DataSender: Problem beim Senden der Daten. RC: {msg_info.rc}")
            # Optional: Auf Bestätigung warten
            # msg_info.wait_for_publish(timeout=5)

        except FileNotFoundError:
            logging.error(f"DataSender: Fehler beim Senden - Datei nicht gefunden: {csv_file}")
        except json.JSONDecodeError as e:
            logging.error(f"DataSender: Fehler beim Konvertieren der Daten zu JSON: {e}")
        except Exception as e:
            logging.error(f"DataSender: Allgemeiner Fehler beim Senden der Daten aus {csv_file}: {e}")

    def read_csv(self, csv_file):
        """Liest eine CSV-Datei und gibt Daten als Liste von Dictionaries zurück."""
        data = []
        try:
            with open(csv_file, 'r', newline='') as f:  # newline='' ist wichtig für csv
                reader = csv.DictReader(f)  # Annahme: CSV hat Header
                required_keys = ['lat', 'lon', 'timestamp', 'satellites', 'state']  # Erwartete Header

                # Prüfe, ob alle benötigten Header vorhanden sind
                if not reader.fieldnames:
                    logging.error(f"DataSender: CSV-Datei {csv_file} ist leer oder hat keine Header-Zeile.")
                    return []
                if not all(key in reader.fieldnames for key in required_keys):
                    logging.error(
                        f"DataSender: CSV-Datei {csv_file} fehlen benötigte Header ({required_keys}). Gefunden: {reader.fieldnames}")
                    return []

                for i, row in enumerate(reader):
                    try:
                        # Konvertiere Werte und füge sie hinzu
                        data.append({
                            "latitude": float(row['lat']),
                            "longitude": float(row['lon']),
                            "timestamp": float(row['timestamp']),
                            "satellites": int(float(row['satellites'])),
                            "state": row['state'].strip(),
                        })
                    except (ValueError, TypeError, KeyError) as e:
                        # Logge Fehler bei der Konvertierung oder fehlenden Keys in einer Zeile
                        logging.warning(
                            f"DataSender: Fehler beim Verarbeiten von Zeile {i + 2} in {csv_file}: {e}. Zeile: {row}")
                        continue  # Überspringe fehlerhafte Zeile
        except FileNotFoundError:
            raise  # Gebe FileNotFoundError weiter an send_data
        except Exception as e:
            logging.error(f"DataSender: Fehler beim Lesen der CSV-Datei {csv_file}: {e}")
            return []  # Leere Liste bei anderen Lesefehlern

        if not data:
            logging.warning(f"DataSender: Keine gültigen Datenzeilen in {csv_file} gefunden.")
        return data

    def close(self):
        """Stoppt die MQTT-Schleife und trennt die Verbindung."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logging.info("DataSender: MQTT Verbindung geschlossen.")


# Beispielhafte Verwendung (kann entfernt werden)
if __name__ == '__main__':
    # Lade Konfiguration für das Beispiel
    from dotenv import load_dotenv  # Importiere load_dotenv hier

    load_dotenv(".env")
    broker = os.getenv("MQTT_HOST")
    port = int(os.getenv("MQTT_PORT", 1883))
    user = os.getenv("MQTT_USER")
    password = os.getenv("MQTT_PASSWORD")

    if not broker:
        print("Fehler: MQTT_HOST nicht in .env gesetzt.")
    else:
        try:
            # Erstelle eine Dummy-CSV-Datei
            dummy_csv = "dummy_data.csv"
            with open(dummy_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['lat', 'lon', 'timestamp', 'satellites', 'state'])
                writer.writerow([46.1, 7.1, time.time(), 5, 'fix'])
                writer.writerow([46.2, 7.2, time.time() + 1, 6, 'nofix'])
                writer.writerow([46.3, 'invalid', time.time() + 2, 7, 'fix'])  # Ungültige Zeile

            sender = DataSender(broker, port, user, password)
            time.sleep(2)  # Warte kurz auf Verbindung
            sender.send_data(dummy_csv)
            time.sleep(1)  # Warte kurz auf Senden
            sender.close()
            os.remove(dummy_csv)  # Räume Dummy-Datei auf
        except Exception as ex:
            print(f"Fehler im Beispiel: {ex}")
