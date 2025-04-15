# mqtt_handler.py

import paho.mqtt.client as paho_mqtt_client
from paho.mqtt.enums import CallbackAPIVersion
# Assuming REC_CONFIG might be needed if test_mode influences more than just broker details
from config import MQTT_CONFIG, REC_CONFIG
import logging
import inspect

# import random # Optional für eindeutige Client IDs

# Logging konfigurieren
# Stelle sicher, dass das Level auf DEBUG steht, um alle Meldungen zu sehen
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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

        # --- Debug Info CallbackAPIVersion (kann später entfernt werden) ---
        # print("--- Debug Info CallbackAPIVersion (mqtt_handler.py) ---")
        # print(f"Typ von CallbackAPIVersion: {type(CallbackAPIVersion)}")
        # try:
        #     print(f"Modul von CallbackAPIVersion: {inspect.getmodule(CallbackAPIVersion)}")
        #     print(f"Datei von CallbackAPIVersion: {inspect.getfile(CallbackAPIVersion)}")
        # except Exception as inspect_e:
        #     print(f"Konnte Details zu CallbackAPIVersion nicht ermitteln: {inspect_e}")
        # print(f"Attribute in CallbackAPIVersion: {dir(CallbackAPIVersion)}")
        # print("--- Zusätzliches Debugging Ende ---")
        # --- Ende Debug Info ---

        # MQTT Client initialisieren mit Callback API Version 2
        try:
            # Client ID hinzufügen, um sicherzustellen, dass Broker sie unterscheiden kann (optional aber gut)
            # client_id = f"worx_handler_{random.randint(0, 1000)}" # Wenn mehrere Instanzen laufen könnten
            self.mqtt_client = paho_mqtt_client.Client(CallbackAPIVersion.VERSION2)  # , client_id=client_id)
            logging.info("MQTT Client mit CallbackAPIVersion.VERSION2 initialisiert.")
        except AttributeError as e:
            logging.error(f"FEHLER bei Initialisierung von mqtt.Client: {e}")
            logging.error(
                "Stellen Sie sicher, dass paho-mqtt >= 2.0.0 installiert ist und kein Namenskonflikt (mqtt.py/paho/) vorliegt.")
            raise RuntimeError("Konnte MQTT Client nicht korrekt initialisieren.") from e

        # Callbacks setzen
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message  # Standard-Nachrichtenhandler

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Interner Callback für erfolgreiche Verbindung (V2 Signatur)."""
        if reason_code == 0:
            logging.info(f"Erfolgreich mit MQTT Broker verbunden: {self.broker}:{self.port}")
            logging.debug("Callback _on_connect: Verbindung erfolgreich (rc=0). Versuche Topics zu abonnieren...")
            try:
                # --- JETZT ALLE DEFINIERTEN TOPICS ABONNIEREN ---
                topics_to_subscribe = [
                    self.topic_control,
                    self.topic_gps,
                    self.topic_status
                ]
                for topic in topics_to_subscribe:
                    if topic:  # Nur abonnieren, wenn Topic in Config definiert ist
                        logging.debug(f"Callback _on_connect: Rufe self.subscribe für {topic} auf...")
                        self.subscribe(topic)
                        logging.debug(f"Callback _on_connect: self.subscribe für {topic} beendet.")
                    else:
                        # Finde heraus, welcher Key fehlt (für bessere Fehlermeldung)
                        missing_key = "Unbekannt"
                        for key, value in MQTT_CONFIG.items():
                            if value == topic:  # Findet den Key, dessen Wert None oder leer ist
                                missing_key = key
                                break
                        logging.warning(
                            f"Callback _on_connect: Topic '{missing_key}' ist in der MQTT-Konfiguration nicht definiert oder leer!")
                # --- ENDE ALLE TOPICS ABONNIEREN ---
            except Exception as sub_err:
                logging.error(f"Callback _on_connect: Fehler während des Abonnierens: {sub_err}", exc_info=True)
            logging.debug("Callback _on_connect: Abonnier-Logik beendet.")
        else:
            logging.error(f"Verbindung zum MQTT Broker fehlgeschlagen mit Reason Code: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Interner Callback für Verbindungsabbruch (V2 Signatur)."""
        if reason_code == 0:
            logging.info(f"Verbindung zum MQTT Broker bewusst getrennt.")
        else:
            logging.warning(f"Verbindung zum MQTT Broker unerwartet getrennt. Reason Code: {reason_code}")

    def _on_message(self, client, userdata, msg):
        """Standard-Callback für eingehende Nachrichten."""
        # Versuche Payload zu dekodieren, logge Fehler bei Misserfolg
        try:
            payload_str = msg.payload.decode()
            logging.debug(f"Standard-Nachricht empfangen auf Topic '{msg.topic}': {payload_str}")
        except UnicodeDecodeError:
            logging.warning(f"Standard-Nachricht auf Topic '{msg.topic}' konnte nicht dekodiert werden.")

    def set_message_callback(self, callback):
        """Setzt eine benutzerdefinierte Callback-Funktion für eingehende Nachrichten."""
        if self.mqtt_client:
            logging.info(f"Setze benutzerdefinierten Nachrichten-Callback: {callback.__name__}")

            # Wrapper, um sicherzustellen, dass der Callback nur aufgerufen wird, wenn msg existiert
            def safe_callback_wrapper(client, userdata, msg):
                if msg:
                    callback(msg)
                else:
                    logging.warning("Leere Nachricht (None) im on_message Wrapper empfangen.")

            self.mqtt_client.on_message = safe_callback_wrapper
        else:
            logging.error("MQTT Client nicht initialisiert, Callback kann nicht gesetzt werden.")

    def connect(self):
        """Stellt die Verbindung zum MQTT Broker her und startet die Netzwerkschleife."""
        if not self.mqtt_client:
            logging.error("MQTT Client nicht initialisiert, Verbindung nicht mglich.")
            return
        try:
            if self.user and self.password:
                self.mqtt_client.username_pw_set(self.user, self.password)
                logging.info("MQTT Benutzername und Passwort gesetzt.")
            logging.info(f"Verbinde mit MQTT Broker: {self.broker}:{self.port}")
            self.mqtt_client.connect(self.broker, self.port, 60)
            self.mqtt_client.loop_start()
            logging.info("MQTT Netzwerkschleife gestartet.")
        except Exception as e:
            logging.error(f"Fehler beim Verbinden oder Starten der MQTT-Schleife: {e}",
                          exc_info=True)  # exc_info hinzugefügt

    def disconnect(self):
        """Trennt die Verbindung zum MQTT Broker und stoppt die Netzwerkschleife."""
        if self.mqtt_client:
            try:
                logging.info("Trenne Verbindung zum MQTT Broker...")
                rc = self.mqtt_client.loop_stop()  # Stoppt den Netzwerk-Thread
                if not rc == 0:
                    logging.warning(f"loop_stop() beendet mit rc={rc}")
                # Warte kurz, damit der Thread sicher beendet wird (optional, kann helfen)
                # import time
                # time.sleep(0.1)
                self.mqtt_client.disconnect()  # Sendet DISCONNECT-Paket
                logging.info("MQTT Verbindung getrennt und Schleife gestoppt.")
            except Exception as e:
                logging.error(f"Fehler beim Trennen der MQTT-Verbindung: {e}")

    def publish_message(self, topic, payload, retain=False):
        """Veröffentlicht eine Nachricht auf dem angegebenen Topic."""
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            logging.warning(f"Kann Nachricht nicht senden: MQTT Client nicht verbunden. Topic: {topic}")
            return None
        try:
            if not isinstance(payload, bytes):
                payload_bytes = str(payload).encode('utf-8')
            else:
                payload_bytes = payload
            logging.debug(f"Sende Nachricht auf Topic '{topic}': {payload_bytes[:100]}...")  # Payload gekürzt für Log
            msg_info = self.mqtt_client.publish(topic, payload_bytes, retain=retain)
            if msg_info.rc == paho_mqtt_client.MQTT_ERR_SUCCESS:
                logging.debug(f"Nachricht zur Veröffentlichung übergeben (mid={msg_info.mid}).")
            else:
                logging.warning(
                    f"Problem beim Übergeben der Nachricht auf Topic '{topic}'. RC: {msg_info.rc} ({paho_mqtt_client.error_string(msg_info.rc)})")
            return msg_info
        except Exception as e:
            logging.error(f"Fehler beim Senden der MQTT-Nachricht auf Topic '{topic}': {e}")
            return None

    def subscribe(self, topic, qos=0):
        """Abonniert das angegebene Topic."""
        # Zusätzliche Prüfung, auch wenn es von _on_connect aufgerufen wird
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            # Diese Warnung sollte jetzt nicht mehr erscheinen, wenn es von _on_connect kommt
            logging.warning(f"Kann Topic nicht abonnieren (im subscribe): MQTT Client nicht verbunden. Topic: {topic}")
            return None, None
        try:
            logging.info(f"Abonniere Topic: {topic} mit QoS={qos}")  # INFO statt DEBUG, um es sicher zu sehen
            result, mid = self.mqtt_client.subscribe(topic, qos)
            if result == paho_mqtt_client.MQTT_ERR_SUCCESS:
                logging.info(f"Topic '{topic}' erfolgreich zum Abonnieren angefragt (mid={mid}).")  # INFO statt DEBUG
            else:
                logging.warning(
                    f"Problem beim Anfragen des Abonnements für Topic '{topic}'. RC: {result} ({paho_mqtt_client.error_string(result)})")
            return result, mid
        except Exception as e:
            logging.error(f"Fehler beim Abonnieren von Topic '{topic}': {e}")
            return None, None


# Beispiel für die Verwendung (kann entfernt oder auskommentiert werden)
if __name__ == '__main__':
    try:
        test_handler = MqttHandler(test_mode=REC_CONFIG["test_mode"])
        test_handler.connect()


        def my_callback(msg):
            print(f"CALLBACK EMPFANGEN - Topic: {msg.topic}, Payload: {msg.payload.decode()}")


        test_handler.set_message_callback(my_callback)
        # Subscription erfolgt jetzt automatisch in _on_connect
        import time

        time.sleep(2)
        test_handler.publish_message(test_handler.topic_status, "Handler gestartet (Test)")
        print("Warte 10 Sekunden auf eingehende Nachrichten oder Trennung...")
        time.sleep(10)
        test_handler.disconnect()
        print("Test beendet.")
    except KeyError as e:
        print(
            f"FEHLER: Konfigurationsschlüssel fehlt: {e}. Stelle sicher, dass config.py aktuell ist und .env geladen wurde.")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist im Beispiel aufgetreten: {e}")
