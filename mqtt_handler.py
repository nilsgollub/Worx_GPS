# mqtt_handler.py (Korrigierte Version)

import paho.mqtt.client as paho_mqtt_client
from paho.mqtt.enums import CallbackAPIVersion
from config import MQTT_CONFIG, REC_CONFIG # Assuming REC_CONFIG is still needed for test_mode elsewhere
import logging
import inspect

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
        # Kann entfernt werden, wenn alles funktioniert
        print("--- Debug Info CallbackAPIVersion (mqtt_handler.py) ---")
        print(f"Typ von CallbackAPIVersion: {type(CallbackAPIVersion)}")
        try:
            print(f"Modul von CallbackAPIVersion: {inspect.getmodule(CallbackAPIVersion)}")
            print(f"Datei von CallbackAPIVersion: {inspect.getfile(CallbackAPIVersion)}")
        except Exception as inspect_e:
            print(f"Konnte Details zu CallbackAPIVersion nicht ermitteln: {inspect_e}")
        print(f"Attribute in CallbackAPIVersion: {dir(CallbackAPIVersion)}")
        print("--- Zusätzliches Debugging Ende ---")

        # MQTT Client initialisieren mit Callback API Version 2
        try:
            self.mqtt_client = paho_mqtt_client.Client(CallbackAPIVersion.VERSION2)
            logging.info("MQTT Client mit CallbackAPIVersion.VERSION2 initialisiert.")
        except AttributeError as e:
            logging.error(f"FEHLER bei Initialisierung von mqtt.Client: {e}")
            logging.error(
                "Stellen Sie sicher, dass paho-mqtt >= 2.0.0 installiert ist und kein Namenskonflikt (mqtt.py/paho/) vorliegt.")
            raise RuntimeError("Konnte MQTT Client nicht korrekt initialisieren.") from e

        # Callbacks setzen
        self.mqtt_client.on_connect = self._on_connect
        # ---> KORRIGIERTE SIGNATUR HIER <---
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message  # Standard-Nachrichtenhandler

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Interner Callback für erfolgreiche Verbindung (V2 Signatur)."""
        # Beachte: Signatur für V2 angepasst (reason_code statt rc, flags und properties hinzugefügt)
        if reason_code == 0:
            logging.info(f"Erfolgreich mit MQTT Broker verbunden: {self.broker}:{self.port}")
            # Hier könnten initiale Subscriptions erfolgen, falls gewünscht
            # Beispiel: client.subscribe(self.topic_control)
        else:
            logging.error(f"Verbindung zum MQTT Broker fehlgeschlagen mit Reason Code: {reason_code}")

    # ---> KORRIGIERTE SIGNATUR HIER <---
    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """
        Interner Callback für Verbindungsabbruch (V2 Signatur).
        Akzeptiert jetzt 6 Argumente (inkl. self), wie von paho-mqtt v2 übergeben.
        """
        if reason_code == 0:
             # 0 indicates graceful disconnect by client call
             logging.info(f"Verbindung zum MQTT Broker bewusst getrennt.")
        else:
             logging.warning(f"Verbindung zum MQTT Broker unerwartet getrennt. Reason Code: {reason_code}")
             # Hier könnte man Logik für Reconnect-Versuche hinzufügen, falls paho-mqtt es nicht automatisch handhabt

    def _on_message(self, client, userdata, msg):
        """Standard-Callback für eingehende Nachrichten (wird oft überschrieben)."""
        logging.debug(f"Standard-Nachricht empfangen auf Topic '{msg.topic}': {msg.payload.decode()}")
        # Normalerweise wird dieser Callback durch set_message_callback ersetzt

    def set_message_callback(self, callback):
        """Setzt eine benutzerdefinierte Callback-Funktion für eingehende Nachrichten."""
        if self.mqtt_client:
            logging.info(f"Setze benutzerdefinierten Nachrichten-Callback: {callback.__name__}")
            # Stellt sicher, dass der Callback das erwartete Format hat (msg als einziges Argument)
            # Die Lambda-Funktion fängt die Standard-Argumente (client, userdata, msg) ab
            # und ruft den benutzerdefinierten Callback nur mit 'msg' auf.
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
            # connect() löst bei Fehlern Exceptions aus (z.B. ConnectionRefusedError)
            self.mqtt_client.connect(self.broker, self.port, 60)
            self.mqtt_client.loop_start()  # Startet einen Hintergrund-Thread für Netzwerkereignisse
            logging.info("MQTT Netzwerkschleife gestartet.")
        except Exception as e:
            logging.error(f"Fehler beim Verbinden oder Starten der MQTT-Schleife: {e}")
            # Hier könnte man entscheiden, ob das Programm beendet oder ein Reconnect versucht werden soll

    def disconnect(self):
        """Trennt die Verbindung zum MQTT Broker und stoppt die Netzwerkschleife."""
        if self.mqtt_client:
            try:
                logging.info("Trenne Verbindung zum MQTT Broker...")
                # loop_stop() wartet, bis der Netzwerk-Thread beendet ist
                rc = self.mqtt_client.loop_stop()
                if not rc == 0:
                     logging.warning(f"loop_stop() beendet mit rc={rc}")
                # disconnect() sendet die DISCONNECT-Nachricht
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
            # Konvertiere Payload zu Bytes, falls es noch kein Bytes-Objekt ist
            if not isinstance(payload, bytes):
                payload_bytes = str(payload).encode('utf-8')
            else:
                payload_bytes = payload

            logging.debug(f"Sende Nachricht auf Topic '{topic}': {payload_bytes[:100]}...") # Payload ggf. kürzen für Log
            # publish() gibt ein MQTTMessageInfo-Objekt zurück
            msg_info = self.mqtt_client.publish(topic, payload_bytes, retain=retain)
            # Optional: Auf Bestätigung warten (kann blockieren!)
            # msg_info.wait_for_publish(timeout=5)
            if msg_info.rc == paho_mqtt_client.MQTT_ERR_SUCCESS:
                logging.debug(f"Nachricht zur Veröffentlichung übergeben (mid={msg_info.mid}).")
            else:
                logging.warning(f"Problem beim Übergeben der Nachricht auf Topic '{topic}'. RC: {msg_info.rc} ({paho_mqtt_client.error_string(msg_info.rc)})")
            # Rückgabe des MessageInfo-Objekts, falls der Aufrufer es braucht
            return msg_info
        except Exception as e:
            logging.error(f"Fehler beim Senden der MQTT-Nachricht auf Topic '{topic}': {e}")
            return None # Rückgabe None bei Fehler

    def subscribe(self, topic, qos=0):
        """Abonniert das angegebene Topic."""
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            logging.warning(f"Kann Topic nicht abonnieren: MQTT Client nicht verbunden. Topic: {topic}")
            return None
        try:
            logging.info(f"Abonniere Topic: {topic} mit QoS={qos}")
            # subscribe() gibt ein Tupel (result, mid) zurück
            result, mid = self.mqtt_client.subscribe(topic, qos)
            if result == paho_mqtt_client.MQTT_ERR_SUCCESS:
                logging.debug(f"Topic '{topic}' erfolgreich zum Abonnieren angefragt (mid={mid}).")
            else:
                logging.warning(f"Problem beim Anfragen des Abonnements für Topic '{topic}'. RC: {result} ({paho_mqtt_client.error_string(result)})")
            return result, mid
        except Exception as e:
            logging.error(f"Fehler beim Abonnieren von Topic '{topic}': {e}")
            return None, None


# Beispiel für die Verwendung (kann entfernt oder auskommentiert werden)
if __name__ == '__main__':
    # Beispiel: Handler im Testmodus erstellen
    # Stellt sicher, dass die .env-Datei existiert und TEST_MODE gesetzt ist (z.B. TEST_MODE=True)
    # oder passe test_mode hier manuell an
    try:
        test_handler = MqttHandler(test_mode=REC_CONFIG["test_mode"])
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
        print("Warte 10 Sekunden auf eingehende Nachrichten oder Trennung...")
        time.sleep(10)

        test_handler.disconnect()
        print("Test beendet.")

    except KeyError as e:
         print(f"FEHLER: Konfigurationsschlüssel fehlt: {e}. Stelle sicher, dass config.py aktuell ist und .env geladen wurde.")
    except Exception as e:
         print(f"Ein unerwarteter Fehler ist im Beispiel aufgetreten: {e}")

