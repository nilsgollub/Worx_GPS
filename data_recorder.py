# data_recorder.py (Korrigierte Version)
# Diese Klasse ist dafür verantwortlich, GPS-Datenpunkte während einer Aufnahmesitzung
# zu puffern und die gesammelten Daten auf Anfrage über MQTT zu senden.

import logging
import io  # Benötigt für das effiziente Erstellen von Strings im Speicher

# Logging konfigurieren (optional, aber empfohlen für die Fehlersuche)
#.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DataRecorder:
    """
    Puffert GPS-Datenpunkte und sendet sie via MQTT.
    """

    def __init__(self, mqtt_handler):
        """
        Initialisiert den DataRecorder.

        Args:
            mqtt_handler: Eine Instanz von MqttHandler, die zum Veröffentlichen
                          von Nachrichten verwendet wird.
        """
        if mqtt_handler is None:
            # Sicherstellen, dass ein gültiger Handler übergeben wird
            raise ValueError("MqttHandler instance is required.")
        self.mqtt_handler = mqtt_handler
        self.gps_data_buffer = []  # Initialisiert eine leere Liste als Puffer
        logging.info("DataRecorder initialisiert.")

    def add_gps_data(self, gps_data):
        """
        Fügt einen einzelnen GPS-Datenpunkt (Dictionary) zum internen Puffer hinzu.

        Args:
            gps_data (dict): Ein Dictionary, das einen GPS-Punkt repräsentiert
                             (z.B. {'lat': ..., 'lon': ..., 'timestamp': ..., 'satellites': ...}).
                             Kann None sein, wird dann ignoriert.
        """
        if gps_data and isinstance(gps_data, dict):  # Nur gültige Dictionaries hinzufügen
            self.gps_data_buffer.append(gps_data)
            # Optional: Puffergrösse periodisch loggen für Debugging
            # if len(self.gps_data_buffer) % 100 == 0:
            #    logging.debug(f"DataRecorder Puffergrösse: {len(self.gps_data_buffer)}")
        elif gps_data is not None:
            logging.warning(f"DataRecorder: Ignoriere ungültige GPS-Daten: {gps_data}")

    def clear_buffer(self):
        """
        Leert den internen GPS-Datenpuffer.
        """
        self.gps_data_buffer = []
        logging.info("DataRecorder Puffer geleert.")

    def send_buffer_data(self):
        """
        Formatiert die gepufferten GPS-Daten als CSV-String und sendet sie via MQTT.
        Sendet danach einen End-Marker ("-1").
        """
        # Sicherstellen, dass der MQTT-Handler und das Topic verfügbar sind
        if not hasattr(self.mqtt_handler, 'topic_gps') or not self.mqtt_handler.topic_gps:
            logging.error("DataRecorder: MQTT handler hat kein 'topic_gps' Attribut oder es ist leer.")
            return

        topic = self.mqtt_handler.topic_gps

        if not self.gps_data_buffer:
            logging.warning("DataRecorder: Kein Daten im Puffer zum Senden.")
            # Sende End-Marker auch bei leerem Puffer, damit der Empfänger das Ende erkennt
            try:
                self.mqtt_handler.publish_message(topic, "-1")
                logging.info(f"DataRecorder: End-Marker (-1) für leeren Puffer an {topic} gesendet.")
            except Exception as e:
                logging.error(f"DataRecorder: Fehler beim Senden des End-Markers für leeren Puffer: {e}")
            return

        logging.info(f"DataRecorder: Bereite das Senden von {len(self.gps_data_buffer)} Datenpunkten vor.")

        # Nutze io.StringIO, um den CSV-String effizient im Speicher zu bauen
        # Dies ist performanter als häufige String-Konkatenation
        csv_output = io.StringIO()

        # Schreibe die Datenpunkte als CSV-Zeilen
        # Annahme: Der Empfänger (Worx_GPS.py) erwartet keine Kopfzeile,
        # da er DictReader mit festen Feldnamen verwendet.
        for data_point in self.gps_data_buffer:
            try:
                # Hole Werte sicherheitshalber mit .get(), falls Keys fehlen könnten
                lat = data_point.get('lat', '')
                lon = data_point.get('lon', '')
                timestamp = data_point.get('timestamp', '')
                satellites = data_point.get('satellites', '')
                # Schreibe die Zeile als einfachen CSV-String
                csv_output.write(f"{lat},{lon},{timestamp},{satellites}\n")
            except Exception as e:
                # Logge Fehler bei der Formatierung einzelner Punkte, fahre aber fort
                logging.error(
                    f"DataRecorder: Fehler beim Formatieren des Datenpunkts {data_point}: {e}. Überspringe Zeile.")

        # Hole den kompletten CSV-String aus dem StringIO Puffer
        csv_string = csv_output.getvalue()
        csv_output.close()  # Schliesse den StringIO Puffer

        # Sende die formatierten CSV-Daten via MQTT
        try:
            if csv_string:  # Sende nur, wenn der String nicht leer ist
                self.mqtt_handler.publish_message(topic, csv_string)
                logging.info(f"DataRecorder: {len(self.gps_data_buffer)} Datenpunkte erfolgreich an {topic} gesendet.")
            else:
                logging.warning("DataRecorder: Formatierter CSV-String ist leer, keine Daten gesendet.")

            # Sende den End-Marker "-1", um den Abschluss zu signalisieren
            self.mqtt_handler.publish_message(topic, "-1")
            logging.info(f"DataRecorder: End-Marker (-1) an {topic} gesendet.")

        except Exception as e:
            logging.error(f"DataRecorder: Fehler beim Senden der Daten oder des End-Markers via MQTT: {e}")

        # Das Leeren des Puffers wird durch clear_buffer() gehandhabt,
        # das in start_recording() von Worx_GPS_Rec.py aufgerufen wird.
        # Falls der Puffer *direkt nach dem Senden* geleert werden soll,
        # kann hier self.clear_buffer() aufgerufen werden.


# Beispielhafte Verwendung (nur für Testzwecke, wird normalerweise von Worx_GPS_Rec.py importiert und genutzt)
if __name__ == '__main__':
    # Erstelle einen Dummy-MQTT-Handler nur für lokale Tests
    class MockMqttHandler:
        def __init__(self):
            # Definiere das Topic, das der DataRecorder verwenden soll
            self.topic_gps = "test/worx/gps"
            print(f"MockMqttHandler initialisiert. Ziel-Topic: {self.topic_gps}")

        def publish_message(self, topic, payload):
            # Simuliere das Senden einer MQTT-Nachricht durch Ausgabe auf der Konsole
            print(f"--- Mock MQTT Publish ---")
            print(f"Topic: {topic}")
            # Kürze lange Payloads für die Ausgabe
            payload_str = str(payload)
            if len(payload_str) > 300:
                print(f"Payload (gekürzt): {payload_str[:300]}...")
            else:
                print(f"Payload: {payload_str}")
            print(f"-------------------------")


    print("--- Starte DataRecorder Test ---")
    mock_handler = MockMqttHandler()
    recorder = DataRecorder(mock_handler)

    # Simuliere das Hinzufügen von GPS-Daten
    print("\n--- Füge Testdaten hinzu ---")
    recorder.add_gps_data({'lat': 46.8118, 'lon': 7.1328, 'timestamp': 1678886400.123, 'satellites': 5})
    recorder.add_gps_data({'lat': 46.8119, 'lon': 7.1329, 'timestamp': 1678886402.456, 'satellites': 6})
    recorder.add_gps_data({'lat': 46.8120, 'lon': 7.1330, 'timestamp': 1678886404.789, 'satellites': 7})
    recorder.add_gps_data(None)  # Teste das Hinzufügen von None
    recorder.add_gps_data({'lat': 46.8121, 'lon': 7.1331})  # Teste fehlende Keys

    print(f"\nAktuelle Puffergrösse: {len(recorder.gps_data_buffer)}")

    # Simuliere das Senden der Daten nach einem Stopp-Befehl
    print("\n--- Sende gepufferte Daten ---")
    recorder.send_buffer_data()

    # Teste das Senden eines leeren Puffers
    print("\n--- Teste Senden bei leerem Puffer ---")
    recorder.clear_buffer()
    print(f"Puffergrösse nach clear_buffer(): {len(recorder.gps_data_buffer)}")
    recorder.send_buffer_data()

    print("\n--- DataRecorder Test Ende ---")

