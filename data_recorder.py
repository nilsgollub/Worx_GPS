# data_recorder.py (Korrigierte Version)
# Diese Klasse ist dafür verantwortlich, GPS-Datenpunkte während einer Aufnahmesitzung
# zu puffern und die gesammelten Daten auf Anfrage über MQTT zu senden.

import logging
import io  # Benötigt für das effiziente Erstellen von Strings im Speicher

# Logging konfigurieren (optional, aber empfohlen für die Fehlersuche)
#.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


import logging
import io
import os

class DataRecorder:
    """
    Puffert GPS-Datenpunkte in einer lokalen Datei und sendet sie via MQTT.
    Dies übersteht auch Stromausfälle des Pi Zeros.
    """

    def __init__(self, mqtt_handler):
        """
        Initialisiert den DataRecorder.

        Args:
            mqtt_handler: Eine Instanz von MqttHandler, die zum Veröffentlichen
                          von Nachrichten verwendet wird.
        """
        if mqtt_handler is None:
            raise ValueError("MqttHandler instance is required.")
        self.mqtt_handler = mqtt_handler
        self.buffer_file = "offline_gps_buffer.csv"
        logging.info("DataRecorder (mit offline persistenz) initialisiert.")

    def _get_wifi_signal_strength(self):
        """Liest die WiFi-Signalstärke in dBm von /proc/net/wireless."""
        try:
            if os.path.exists("/proc/net/wireless"):
                with open("/proc/net/wireless", "r") as f:
                    lines = f.readlines()
                for line in lines[2:]:
                    # Prüfe auf gängige Interface-Namen
                    if line.strip().startswith("wlan0:") or line.strip().startswith("wlan1:"):
                        parts = line.split()
                        # Der Wert ist oft der 4. Wert (Index 3) und hat oft einen Punkt am Ende (z.B. "-65.")
                        level_str = parts[3].strip('.')
                        return int(level_str)
        except Exception as e:
            # Nur Debug, da es auf dem PC/Jetson fehlschlagen wird
            logging.debug(f"Konnte WiFi-Signal nicht lesen: {e}")
        return None

    def add_gps_data(self, gps_data):
        if gps_data and isinstance(gps_data, dict):
            lat = gps_data.get('lat', '')
            lon = gps_data.get('lon', '')
            time_stamp = gps_data.get('timestamp', '')
            satellites = gps_data.get('satellites', '')
            wifi_dbm = self._get_wifi_signal_strength()
            wifi_str = wifi_dbm if wifi_dbm is not None else ''

            try:
                with open(self.buffer_file, "a") as f:
                    f.write(f"{lat},{lon},{time_stamp},{satellites},{wifi_str}\n")
            except Exception as e:
                logging.error(f"DataRecorder: Fehler beim Schreiben in Datei: {e}")
        elif gps_data is not None:
            logging.warning(f"DataRecorder: Ignoriere ungültige GPS-Daten: {gps_data}")

    def clear_buffer(self):
        if os.path.exists(self.buffer_file):
            try:
                os.remove(self.buffer_file)
                logging.info("DataRecorder Puffer-Datei geleert.")
            except Exception as e:
                logging.error(f"Fehler beim Leeren des Puffers: {e}")

    def send_buffer_data(self):
        if not hasattr(self.mqtt_handler, 'topic_gps') or not self.mqtt_handler.topic_gps:
            logging.error("DataRecorder: MQTT handler hat kein 'topic_gps' Attribut oder es ist leer.")
            return

        topic = self.mqtt_handler.topic_gps

        if not os.path.exists(self.buffer_file) or os.path.getsize(self.buffer_file) == 0:
            logging.warning("DataRecorder: Kein Daten im Puffer zum Senden.")
            try:
                self.mqtt_handler.publish_message(topic, "-1")
                logging.info(f"DataRecorder: End-Marker (-1) für leeren Puffer an {topic} gesendet.")
            except Exception as e:
                logging.error(f"DataRecorder: Fehler beim Senden des End-Markers: {e}")
            return

        logging.info(f"DataRecorder: Lese gepufferte Daten aus {self.buffer_file}.")
        
        try:
            with open(self.buffer_file, "r") as f:
                csv_string = f.read()

            if csv_string:
                self.mqtt_handler.publish_message(topic, csv_string)
                logging.info(f"DataRecorder: Daten erfolgreich an {topic} gesendet über MQTT Queue.")
            
            self.mqtt_handler.publish_message(topic, "-1")
            logging.info(f"DataRecorder: End-Marker (-1) an {topic} gesendet.")

            # Da die Daten nun in der MQTT Queue liegen, können wir die Datei leeren
            self.clear_buffer()

        except Exception as e:
            logging.error(f"DataRecorder: Fehler beim Senden der Daten: {e}")

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
    recorder.send_buffer_data()

    print("\n--- DataRecorder Test Ende ---")

