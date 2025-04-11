# mqtt_handler.py

import paho.mqtt.client as paho_mqtt_client  # Importiere das Client-Modul mit einem anderen Namen
from paho.mqtt.enums import CallbackAPIVersion  # Importiere die Enum direkt

from config import MQTT_CONFIG, REC_CONFIG
import logging
import inspect  # Import für Debugging hinzugefügt

# Logging konfigurieren (optional, aber empfohlen)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class MqttHandler:
    def __init__(self, test_mode):
        self.test_mode = test_mode
        # Broker-Details basierend auf test_mode auswählen
        self.broker = MQTT_CONFIG["host_lokal"] if test_mode else MQTT_CONFIG["host"]
        self.port = MQTT_CONFIG["port_lokal"] if test_mode else MQTT_CONFIG["port"]
        self.user = MQTT_CONFIG["user_local"] if test_mode else MQTT_CONFIG["user"]
        self.password = MQTT_CONFIG["password_local"] if test_mode else MQTT_CONFIG["password"]

        # MQTT Topics aus der Konfiguration holen
        self.topic_control = MQTT_CONFIG["topic_control"]
        self.topic_gps = MQTT_CONFIG["topic_gps"]
        self.topic_status = MQTT_CONFIG["topic_status"]

        # --- Zusätzliches Debugging Start ---
        # Dieser Block hilft zu verstehen, welches CallbackAPIVersion-Objekt geladen wird.
        # Er kann entfernt werden, sobald das Problem gelöst ist.
        print("--- Debug Info CallbackAPIVersion (mqtt_handler.py) ---")
        print(f"Typ von CallbackAPIVersion: {type(CallbackAPIVersion)}")
        try:
            # Versuche, den Pfad des Moduls zu finden, aus dem CallbackAPIVersion stammt
            print(f"Modul von CallbackAPIVersion: {inspect.getmodule(CallbackAPIVersion)}")
            print(f"Datei von CallbackAPIVersion: {inspect.getfile(CallbackAPIVersion)}")
        except Exception as inspect_e:
            print(f"Konnte Details zu CallbackAPIVersion nicht ermitteln: {inspect_e}")
        # Gib alle Attribute von CallbackAPIVersion aus
        print(f"Attribute in CallbackAPIVersion: {dir(CallbackAPIVersion)}")
        print("--- Zusätzliches Debugging Ende ---")

        # MQTT Client initialisieren mit Callback API Version 2
        # Wenn der AttributeError weiterhin auftritt, stimmt etwas Grundlegendes
        # mit der Python-Umgebung oder dem Import nicht.
        try:
            # Die problematische Zeile:
            self.mqtt_client = paho_mqtt_client.Client(CallbackAPIVersion.VERSION2)
            logging.info("MQTT Client mit CallbackAPIVersion.V2 initialisiert.")
        except AttributeError as e:
            logging.error(f"FEHLER bei Initialisierung von mqtt.Client: {e}")
            logging.error(
                "Stellen Sie sicher, dass paho-mqtt >= 2.0.0 installiert ist und kein Namenskonflikt (mqtt.py/paho/) vorliegt.")
            # Fallback oder Abbruch, je nach Anforderung
            # Fallback auf V1 (kann zu anderem Verhalten führen, wenn Callbacks V2 erwarten):
            # self.mqtt_client = paho_mqtt_client.Client(CallbackAPIVersion.V1)
            # logging.warning("Fallback auf CallbackAPIVersion.V1.")
            # Oder Programm beenden:
            raise RuntimeError("Konnte MQTT Client nicht korrekt initialisieren.") from e

        # Standard-Callbacks setzen (können später überschrieben werden)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message  # Standard-Nachrichtenhandler
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Interner Callback für erfolgreiche Verbindung."""
        if rc == 0:
            logging.info(f"Erfolgreich mit MQTT Broker verbunden: {self.broker}:{self.port}")
            # Hier könnten initiale Subscriptions erfolgen, falls gewünscht
            # Beispiel: client.subscribe(self.topic_control)
        else:
            logging.error(f"Verbindung zum MQTT Broker fehlgeschlagen mit Code: {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Interner Callback für Verbindungsabbruch."""
        logging.warning(f"Verbindung zum MQTT Broker getrennt mit Code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Standard-Callback für eingehende Nachrichten (wird oft überschrieben)."""
        logging.debug(f"Standard-Nachricht empfangen auf Topic '{msg.topic}': {msg.payload.decode()}")
        # Normalerweise wird dieser Callback durch set_message_callback ersetzt

    def set_message_callback(self, callback):
        """Setzt eine benutzerdefinierte Callback-Funktion für eingehende Nachrichten."""
        if self.mqtt_client:
            logging.info(f"Setze benutzerdefinierten Nachrichten-Callback: {callback.__name__}")
            # Stellt sicher, dass der Callback das erwartete Format hat
            self.mqtt_client.on_message = lambda client, userdata, msg: callback(msg)
        else:
            logging.error("MQTT Client nicht initialisiert, Callback kann nicht gesetzt werden.")

    def connect(self):
        """Stellt die Verbindung zum MQTT Broker her und startet die Netzwerkschleife."""
        if not self.mqtt_client:
            logging.error("MQTT Client nicht initialisiert, Verbindung nicht möglich.")
            return

        try:
            if self.user and self.password:
                self.mqtt_client.username_pw_set(self.user, self.password)
                logging.info("MQTT Benutzername und Passwort gesetzt.")
            logging.info(f"Verbinde mit MQTT Broker: {self.broker}:{self.port}")
            self.mqtt_client.connect(self.broker, self.port, 60)
            self.mqtt_client.loop_start()  # Startet einen Hintergrund-Thread für Netzwerkereignisse
            logging.info("MQTT Netzwerkschleife gestartet.")
        except Exception as e:
            logging.error(f"Fehler beim Verbinden oder Starten der MQTT-Schleife: {e}")

    def disconnect(self):
        """Trennt die Verbindung zum MQTT Broker und stoppt die Netzwerkschleife."""
        if self.mqtt_client:
            try:
                logging.info("Trenne Verbindung zum MQTT Broker...")
                self.mqtt_client.loop_stop()  # Stoppt den Hintergrund-Thread
                self.mqtt_client.disconnect()
                logging.info("MQTT Verbindung getrennt und Schleife gestoppt.")
            except Exception as e:
                logging.error(f"Fehler beim Trennen der MQTT-Verbindung: {e}")

    def publish_message(self, topic, payload, retain=False):
        """Veröffentlicht eine Nachricht auf dem angegebenen Topic."""
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            logging.warning(f"Kann Nachricht nicht senden: MQTT Client nicht verbunden. Topic: {topic}")
            # Optional: Versuchen, neu zu verbinden oder Nachricht puffern
            return

        try:
            logging.debug(f"Sende Nachricht auf Topic '{topic}': {payload}")
            result = self.mqtt_client.publish(topic, payload, retain=retain)
            result.wait_for_publish(timeout=5)  # Warte kurz auf Bestätigung (optional)
            if result.rc == paho_mqtt_client.MQTT_ERR_SUCCESS:
                logging.debug(f"Nachricht erfolgreich gesendet (mid={result.mid}).")
            else:
                logging.warning(f"Problem beim Senden der Nachricht auf Topic '{topic}'. RC: {result.rc}")
        except Exception as e:
            logging.error(f"Fehler beim Senden der MQTT-Nachricht auf Topic '{topic}': {e}")

    def subscribe(self, topic):
        """Abonniert das angegebene Topic."""
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            logging.warning(f"Kann Topic nicht abonnieren: MQTT Client nicht verbunden. Topic: {topic}")
            return
        try:
            logging.info(f"Abonniere Topic: {topic}")
            result, mid = self.mqtt_client.subscribe(topic)
            if result == paho_mqtt_client.MQTT_ERR_SUCCESS:
                logging.debug(f"Topic '{topic}' erfolgreich abonniert (mid={mid}).")
            else:
                logging.warning(f"Problem beim Abonnieren von Topic '{topic}'. RC: {result}")
        except Exception as e:
            logging.error(f"Fehler beim Abonnieren von Topic '{topic}': {e}")


# Beispiel für die Verwendung (kann entfernt oder auskommentiert werden)
if __name__ == '__main__':
    # Beispiel: Handler im Testmodus erstellen
    test_handler = MqttHandler(test_mode=True)
    test_handler.connect()


    # Beispiel-Callback für Nachrichten
    def my_callback(msg):
        print(f"CALLBACK EMPFANGEN - Topic: {msg.topic}, Payload: {msg.payload.decode()}")


    test_handler.set_message_callback(my_callback)
    test_handler.subscribe(test_handler.topic_control)  # Beispiel-Subscription

    # Beispiel: Nachricht senden
    import time

    time.sleep(2)  # Kurz warten, bis Verbindung steht
    test_handler.publish_message(test_handler.topic_status, "Handler gestartet (Test)")

    # Handler laufen lassen (im Beispiel nur kurz)
    time.sleep(10)

    test_handler.disconnect()
