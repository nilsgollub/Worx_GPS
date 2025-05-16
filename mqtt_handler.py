# mqtt_handler.py
import logging
import time
import paho.mqtt.client as paho_mqtt_client
from config import MQTT_CONFIG, REC_CONFIG
from queue import Queue, Full, Empty  # Thread-sichere Warteschlange
import threading  # Für den Queue-Verarbeitungs-Thread
import os # Für os.getpid()

# Standard-Reconnect-Verzögerungen (in Sekunden)
DEFAULT_INITIAL_RECONNECT_DELAY = 1
DEFAULT_MAX_RECONNECT_DELAY = 60
# DEFAULT_RECONNECT_RATE = 2 # Nicht direkt von Paho verwendet, aber für eigene Logik nlich
DEFAULT_MAX_QUEUE_SIZE = 1000  # Maximale Anzahl Nachrichten in der Warteschlange, 0 für unbegrenzt


class MqttHandler:
    """
    Verwaltet die MQTT-Verbindung, Abonnements und das Senden/Empfangen von Nachrichten.
    Implementiert automatische Wiederverbindungslogik mit exponentiellem Backoff
    und eine Warteschlange für ausgehende Nachrichten, um Datenverlust bei
    Verbindungsunterbrechungen zu minimieren.
    """
    # --- MODIFIZIERTE __init__ ---
    def __init__(self, test_mode=False, lwt_payload=None, lwt_topic=None, lwt_qos=1, lwt_retain=True):
        """
        Initialisiert den MQTT-Handler.

        Args:
            test_mode (bool): Wenn True, wird ein Präfix zu den Topics hinzugefügt.
            lwt_payload (str, optional): Die Payload für die Last Will and Testament Nachricht.
                                         Wenn None, wird kein LWT gesetzt, es sei denn,
                                         es ist ein Default in der Klasse definiert.
            lwt_topic (str, optional): Das Topic für die LWT Nachricht. Default ist topic_status.
            lwt_qos (int, optional): QoS für LWT. Default ist 1.
            lwt_retain (bool, optional): Retain-Flag für LWT. Default ist True.
        """
        self.test_mode = test_mode
        self._host = MQTT_CONFIG.get("host", "localhost")
        self._port = MQTT_CONFIG.get("port", 1883)
        self._keepalive = MQTT_CONFIG.get("keepalive", 60)
        self._username = MQTT_CONFIG.get("user")
        self._password = MQTT_CONFIG.get("password")

        # Reconnect-Parameter
        self._initial_reconnect_delay = MQTT_CONFIG.get("initial_reconnect_delay", DEFAULT_INITIAL_RECONNECT_DELAY)
        self._max_reconnect_delay = MQTT_CONFIG.get("max_reconnect_delay", DEFAULT_MAX_RECONNECT_DELAY)
        # self._reconnect_rate = MQTT_CONFIG.get("reconnect_rate", DEFAULT_RECONNECT_RATE) # Nicht direkt von Paho verwendet

        # Queue-Parameter
        self._max_queue_size = MQTT_CONFIG.get("max_queue_size", DEFAULT_MAX_QUEUE_SIZE)
        # Initialisiere die thread-sichere Warteschlange
        self._message_queue = Queue(maxsize=self._max_queue_size)
        self._queue_processing_thread = None
        self._stop_queue_processing = threading.Event()  # Zum Stoppen des Threads

        # Topics
        topic_prefix = "test/" if self.test_mode else ""
        self.topic_control = f"{topic_prefix}{MQTT_CONFIG.get('topic_control', 'worx/control')}"
        self.topic_status = f"{topic_prefix}{MQTT_CONFIG.get('topic_status', 'worx/status')}"
        self.topic_data = f"{topic_prefix}{MQTT_CONFIG.get('topic_data', 'worx/data')}"
        self.topic_problem = f"{topic_prefix}{MQTT_CONFIG.get('topic_problem', 'worx/problem')}"
        self.topic_gps = f"{topic_prefix}{MQTT_CONFIG.get('topic_gps', 'worx/gps')}"

        # Client-Setup
        # Eindeutigere Client-ID, um Konflikte zu vermeiden, wenn mehrere Instanzen laufen
        # (z.B. Worx_GPS_Rec und WebUI)
        client_id = f"worx_gps_client_{os.getpid()}_{int(time.time()) % 1000}"
        self.client = paho_mqtt_client.Client(client_id=client_id, callback_api_version=paho_mqtt_client.CallbackAPIVersion.VERSION2)

        if self._username and self._password:
            self.client.username_pw_set(self._username, self._password)
            logging.info("MQTT-Authentifizierung konfiguriert.")

        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_log = self._on_log

        # --- LWT Konfiguration basierend auf Parametern ---
        actual_lwt_topic = lwt_topic if lwt_topic is not None else self.topic_status
        
        if actual_lwt_topic and lwt_payload:
            self.client.will_set(actual_lwt_topic, payload=lwt_payload, qos=lwt_qos, retain=lwt_retain)
            logging.info(f"MQTT Will für Client '{client_id}' gesetzt: Topic='{actual_lwt_topic}', Payload='{lwt_payload}'")
        elif actual_lwt_topic and not lwt_payload:
            logging.info(f"Kein LWT-Payload für Client '{client_id}' angegeben, es wird kein LWT gesetzt.")
        else:
            logging.info(f"Kein LWT-Topic für Client '{client_id}' angegeben, es wird kein LWT gesetzt.")

        self._user_message_callback = None
        self._is_connected = False

        # Automatische Wiederverbindung konfigurieren
        self.client.reconnect_delay_set(min_delay=self._initial_reconnect_delay, max_delay=self._max_reconnect_delay)

        logging.info(f"MqttHandler initialisiert für Broker {self._host}:{self._port}")
        logging.info(f"  Control Topic: {self.topic_control}")
        logging.info(f"  Status Topic: {self.topic_status}")
        logging.info(f"  Data Topic: {self.topic_data}")
        logging.info(f"  Problem Topic: {self.topic_problem}")
        logging.info(f"  Reconnect Delays: min={self._initial_reconnect_delay}s, max={self._max_reconnect_delay}s")
        logging.info(
            f"  Ausgehende Nachrichten-Queue Größe: {self._max_queue_size if self._max_queue_size > 0 else 'Unbegrenzt'}")

    # --- Standard Callbacks (on_log, on_message, on_publish bleiben gleich) ---
    def _on_log(self, client, userdata, level, buf):
        """Leitet Paho-Logmeldungen an das Python-Logging weiter."""
        if level == paho_mqtt_client.MQTT_LOG_INFO:
            log_level = logging.INFO
        elif level == paho_mqtt_client.MQTT_LOG_NOTICE:
            log_level = logging.INFO
        elif level == paho_mqtt_client.MQTT_LOG_WARNING:
            log_level = logging.WARNING
        elif level == paho_mqtt_client.MQTT_LOG_ERR:
            log_level = logging.ERROR
        elif level == paho_mqtt_client.MQTT_LOG_DEBUG:
            log_level = logging.DEBUG
        else:
            log_level = logging.DEBUG
        if logging.getLogger().isEnabledFor(log_level):
            logging.log(log_level, f"[PahoMQTT] {buf}")

    def _on_message(self, client, userdata, msg):
        """Callback, der bei Empfang einer Nachricht aufgerufen wird."""
        logging.debug(
            f"MQTT Nachricht empfangen - Topic: '{msg.topic}', Payload: '{msg.payload[:50]}...' (Retain: {msg.retain})")
        if self._user_message_callback:
            try:
                self._user_message_callback(msg)
            except Exception as e:
                logging.error(f"Fehler im benutzerdefinierten MQTT-Nachrichten-Callback: {e}", exc_info=True)
        else:
            logging.debug("Kein benutzerdefinierter Callback für MQTT-Nachrichten gesetzt.")

    def _on_publish(self, client, userdata, mid, reason_code, properties=None):
        """
        Callback, der nach erfolgreichem Senden einer Nachricht mit QoS > 0 aufgerufen wird.
        (Paho MQTT v2.x Signatur)
        """
        if reason_code == 0: # MQTT_ERR_SUCCESS
            logging.debug(f"MQTT Nachricht (mid={mid}) erfolgreich veröffentlicht.")
        else:
            logging.warning(f"MQTT Nachricht (mid={mid}) Veröffentlichung fehlgeschlagen mit Code {reason_code}.")
        # Hier könnte man komplexere Logik für QoS 1/2 Bestätigungen einbauen,
        # z.B. Nachrichten aus einer "pending confirmation" Liste entfernen.

    # --- Angepasste Callbacks für Verbindungsstatus und Queue ---
    # In mqtt_handler.py -> _on_connect Methode

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback, der bei erfolgreicher Verbindung zum Broker aufgerufen wird.
        
        Der properties-Parameter wird für MQTT 5.0 verwendet und ist in MQTT 3.1.1 nicht vorhanden.
        """
        if rc == 0:
            self._is_connected = True
            logging.info("MQTT erfolgreich verbunden.")
            # --- Korrektur: Alle relevanten Topics abonnieren ---
            topics_to_subscribe = [
                (self.topic_control, 1),  # Control mit QoS 1
                (self.topic_gps, 0),  # GPS Daten mit QoS 0 (Standard)
                (self.topic_status, 0)  # Status auch mit QoS 0
            ]
            try:
                # subscribe kann eine Liste von Tupeln (topic, qos) verarbeiten
                result, mid = self.client.subscribe(topics_to_subscribe)
                if result == paho_mqtt_client.MQTT_ERR_SUCCESS:
                    subscribed_topics_str = ", ".join([f"'{t[0]}'(QoS {t[1]})" for t in topics_to_subscribe])
                    logging.info(f"Erfolgreich Topics abonniert: {subscribed_topics_str} (mid={mid}).")
                else:
                    logging.error(f"Fehler beim Abonnieren von Topics: {paho_mqtt_client.error_string(result)}")
            except Exception as e:
                logging.error(f"Ausnahme beim Abonnieren von Topics: {e}", exc_info=True)

            # Status "online" senden (verwende die Methode, um Queue-Logik zu nutzen)
            self.publish_message(self.topic_status, "recorder_online", qos=1, retain=True)

            # Starte den Thread zur Verarbeitung der Warteschlange, falls nicht schon läuft
            self._start_queue_processing()

        else:
            self._is_connected = False
            logging.error(f"MQTT-Verbindungsfehler mit Code {rc}: {paho_mqtt_client.connack_string(rc)}")
            # Paho's loop kümmert sich um Reconnect

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback, der bei Verbindungsverlust aufgerufen wird.
        
        Der properties-Parameter wird für MQTT 5.0 verwendet und ist in MQTT 3.1.1 nicht vorhanden.
        """
        # was_connected = self._is_connected # Merken, ob wir vorher verbunden waren
        self._is_connected = False
        if rc == 0:
            logging.info("MQTT-Verbindung ordnungsgemäß getrennt.")
        else:
            logging.warning(
                f"MQTT unerwartet getrennt mit Code {rc}: {paho_mqtt_client.error_string(rc)}. Automatische Wiederverbindung wird versucht...")

        # Stoppe den Queue-Processing-Thread nicht hier bei unerwartetem Disconnect,
        # damit er weiterlaufen und Nachrichten senden kann, sobald die Verbindung wieder steht.
        # Er wird in disconnect() gestoppt.

    # --- Methoden für Queue-Verarbeitung ---
    def _start_queue_processing(self):
        """Startet den Hintergrundthread zur Verarbeitung der Nachrichten-Queue."""
        if self._queue_processing_thread and self._queue_processing_thread.is_alive():
            logging.debug("Queue-Verarbeitungs-Thread läuft bereits.")
            return

        self._stop_queue_processing.clear()  # Signal zurücksetzen
        self._queue_processing_thread = threading.Thread(target=self._process_queue, daemon=True,
                                                         name="MqttQueueProcessor")
        self._queue_processing_thread.start()
        logging.info("Queue-Verarbeitungs-Thread gestartet.")

    def _stop_queue_processing_thread(self):
        """Signalisiert dem Queue-Verarbeitungs-Thread, dass er anhalten soll und wartet."""
        if self._queue_processing_thread and self._queue_processing_thread.is_alive():
            logging.info("Stoppe Queue-Verarbeitungs-Thread...")
            self._stop_queue_processing.set()  # Signal setzen
            # Wecke den Thread auf, falls er in wait() oder get() blockiert
            self._message_queue.put(None)  # Sentinel-Wert einfügen, um get() zu deblockieren

            self._queue_processing_thread.join(timeout=5.0)  # Warte auf Beendigung
            if self._queue_processing_thread.is_alive():
                logging.warning("Queue-Verarbeitungs-Thread konnte nicht innerhalb des Timeouts gestoppt werden.")
            else:
                logging.info("Queue-Verarbeitungs-Thread gestoppt.")
        self._queue_processing_thread = None
        self._stop_queue_processing.clear()  # Signal für nächsten Start zurücksetzen

    def _process_queue(self):
        """Verarbeitet Nachrichten aus der Warteschlange (läuft in eigenem Thread)."""
        logging.info("Starte Verarbeitung der Nachrichten-Warteschlange...")
        while not self._stop_queue_processing.is_set():
            if not self._is_connected:
                # Wenn nicht verbunden, kurz warten und erneut prüfen
                logging.debug("Queue-Verarbeitung pausiert (nicht verbunden).")
                # Warte auf Stop-Signal oder Timeout
                self._stop_queue_processing.wait(timeout=self._initial_reconnect_delay)
                continue

            message_item = None
            try:
                # Versuche, eine Nachricht aus der Queue zu holen (blockierend mit Timeout)
                # Timeout, um regelmäßig auf _stop_queue_processing prüfen zu können
                message_item = self._message_queue.get(block=True, timeout=1.0)

                # Prüfe auf Sentinel-Wert zum Beenden
                if message_item is None:
                    logging.debug("Sentinel-Wert in Queue empfangen, beende Verarbeitung.")
                    break  # Schleife verlassen

                topic, payload_bytes, qos, retain = message_item
                logging.debug(f"Verarbeite Nachricht aus Queue: Topic={topic}, QoS={qos}, Retain={retain}")

                # Versuche, die Nachricht zu senden
                msg_info = self.client.publish(topic, payload_bytes, qos=qos, retain=retain)

                if msg_info.rc == paho_mqtt_client.MQTT_ERR_SUCCESS:
                    logging.debug(f"Nachricht (mid={msg_info.mid}) aus Queue erfolgreich an Paho übergeben.")
                    self._message_queue.task_done()  # Markiere Aufgabe als erledigt
                elif msg_info.rc == paho_mqtt_client.MQTT_ERR_QUEUE_SIZE:
                    logging.warning(
                        f"Paho-interne Warteschlange voll beim Senden aus externer Queue (mid={msg_info.mid}). Nachricht zurück ans Ende der Queue.")
                    # Nachricht zurück ans Ende der Queue legen
                    try:
                        self._message_queue.put(message_item)  # Zurück ans Ende
                    except Full:
                        logging.error(
                            "Externe Nachrichten-Queue ist voll, konnte Nachricht nicht zurücklegen. Nachricht geht verloren!")
                        self._message_queue.task_done()  # Trotzdem als erledigt markieren, um Blockade zu verhindern
                    # Kurze Pause, um Paho Zeit zu geben
                    time.sleep(0.5)
                else:
                    # Anderer Fehler beim Senden aus der Queue
                    logging.error(
                        f"Fehler beim Senden der Nachricht aus Queue (mid={msg_info.mid}): {paho_mqtt_client.error_string(msg_info.rc)}. Nachricht wird verworfen.")
                    self._message_queue.task_done()  # Als erledigt markieren, um Blockade zu verhindern

            except Empty:
                # Queue ist leer, warte auf neue Nachrichten oder Stop-Signal (passiert durch get mit Timeout)
                logging.debug("Nachrichten-Queue ist leer. Warte auf neue Einträge oder Stop...")
                continue  # Nächste Iteration der while-Schleife

            except Exception as e:
                logging.error(f"Unerwarteter Fehler in der Queue-Verarbeitung: {e}", exc_info=True)
                if message_item and message_item is not None:
                    # Versuche, die Aufgabe trotzdem als erledigt zu markieren, um Blockaden zu vermeiden
                    try:
                        self._message_queue.task_done()
                    except ValueError:
                        pass  # task_done() wurde vielleicht schon aufgerufen
                # Kurze Pause, um CPU-Last bei Dauerfehlern zu vermeiden
                time.sleep(1)

        logging.info("Verarbeitung der Nachrichten-Warteschlange beendet.")

    # --- Öffentliche Methoden (set_message_callback, is_connected bleiben gleich) ---
    def set_message_callback(self, callback_func):
        """Setzt die Callback-Funktion für eingehende Nachrichten."""
        if callable(callback_func):
            self._user_message_callback = callback_func
            logging.info("Benutzerdefinierter MQTT-Nachrichten-Callback gesetzt.")
        else:
            logging.warning("Versuch, einen nicht aufrufbaren MQTT-Nachrichten-Callback zu setzen.")
                
    def set_connect_callback(self, callback_func):
            """Setzt die Callback-Funktion für erfolgreiche Verbindung."""
            if callable(callback_func):
                self._user_connect_callback = callback_func
                self._mqtt_client.on_connect = self._on_connect_wrapper
                logging.info("Benutzerdefinierter MQTT-Connect-Callback gesetzt.")
            else:
                logging.warning("Versuch, einen nicht aufrufbaren MQTT-Connect-Callback zu setzen.")
                
    def set_disconnect_callback(self, callback_func):
            """Setzt die Callback-Funktion für Verbindungstrennung."""
            if callable(callback_func):
                self._user_disconnect_callback = callback_func
                self._mqtt_client.on_disconnect = self._on_disconnect_wrapper
                logging.info("Benutzerdefinierter MQTT-Disconnect-Callback gesetzt.")
            else:
                logging.warning("Versuch, einen nicht aufrufbaren MQTT-Disconnect-Callback zu setzen.")
                
    def _on_connect_wrapper(self, client, userdata, flags, rc, properties=None):
            """Wrapper für den Connect-Callback, ruft auch benutzerdefinierten Callback auf."""
            # properties Parameter nur übergeben, wenn er vorhanden ist
            self._on_connect(client, userdata, flags, rc, properties)
            if hasattr(self, '_user_connect_callback') and self._user_connect_callback:
                try:
                    self._user_connect_callback()
                except Exception as e:
                    logging.error(f"Fehler im benutzerdefinierten Connect-Callback: {e}")
                    
    def _on_disconnect_wrapper(self, client, userdata, rc, properties=None):
            """Wrapper für den Disconnect-Callback, ruft auch benutzerdefinierten Callback auf."""
            self._on_disconnect(client, userdata, rc, properties)
            if hasattr(self, '_user_disconnect_callback') and self._user_disconnect_callback:
                try:
                    self._user_disconnect_callback()
                except Exception as e:
                    logging.error(f"Fehler im benutzerdefinierten Disconnect-Callback: {e}")

    def is_connected(self) -> bool:
        """Gibt zurück, ob der Client aktuell mit dem MQTT-Broker verbunden ist."""
        return self._is_connected

    # --- Angepasste connect / disconnect Methoden ---
    def connect(self):
        """Stellt die Verbindung her und startet die Netzwerkschleife."""
        # Queue Processing wird in _on_connect gestartet
        if self._is_connected:
            logging.warning("Bereits mit MQTT verbunden.")
            return

        logging.info(f"Versuche, zu MQTT Broker {self._host}:{self._port} zu verbinden...")
        try:
            self.client.connect_async(self._host, self._port, self._keepalive)
            self.client.loop_start()  # Startet Paho's Netzwerk-Thread (inkl. Reconnect)
            logging.info("MQTT Netzwerkschleife gestartet (loop_start).")
        except (OSError, ConnectionRefusedError) as e:
            logging.error(f"Fehler beim initialen MQTT-Verbindungsversuch: {e}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Starten der MQTT-Verbindung: {e}", exc_info=True)
            # Versuche trotzdem, die Schleife zu starten, falls möglich
            try:
                # Prüfen, ob loop_start() vielleicht doch schon lief oder gestartet werden kann
                if not self.client.is_connected() and self.client._thread is None:
                    self.client.loop_start()
                    logging.info("MQTT Netzwerkschleife nach Fehler gestartet.")
            except Exception as loop_e:
                logging.error(f"Konnte MQTT Netzwerkschleife nach Fehler nicht starten: {loop_e}")

    def disconnect(self):
        """Stoppt Queue-Verarbeitung, trennt Verbindung und stoppt Netzwerkschleife."""
        logging.info("Trenne MQTT-Verbindung...")

        # 1. Stoppe den Queue-Processing-Thread zuerst
        self._stop_queue_processing_thread()

        # 2. Versuche, letzte Will-Nachricht zu senden (optional)
        if self._is_connected:
            try:
                logging.info("Sende 'recorder_offline' Status vor dem Trennen...")
                # Verwende publish direkt, nicht die Methode mit Queue-Logik
                msg_info = self.client.publish(self.topic_status, "recorder_offline", qos=1, retain=True)
                if msg_info.rc == paho_mqtt_client.MQTT_ERR_SUCCESS:
                    # Warte kurz, damit die Nachricht eine Chance hat, gesendet zu werden
                    # Dies ist keine Garantie, besonders bei Netzwerkproblemen
                    time.sleep(1.0)
                else:
                    logging.warning(
                        f"Konnte 'recorder_offline' Status vor dem Trennen nicht senden: {paho_mqtt_client.error_string(msg_info.rc)}")
            except Exception as e:
                logging.warning(f"Fehler beim Senden des Offline-Status: {e}")

        # 3. Stoppe Paho's Netzwerkschleife
        try:
            self.client.loop_stop()
            logging.info("MQTT Netzwerkschleife gestoppt (loop_stop).")
        except Exception as e:
            logging.error(f"Fehler beim Stoppen der MQTT Netzwerkschleife: {e}", exc_info=True)

        # 4. Trenne die Verbindung zum Broker
        try:
            self.client.disconnect()
            # _on_disconnect wird aufgerufen und setzt _is_connected = False
            logging.info("MQTT disconnect() aufgerufen.")
        except Exception as e:
            logging.error(f"Fehler beim Trennen der MQTT-Verbindung: {e}", exc_info=True)
        finally:
            # Sicherstellen, dass der Status als nicht verbunden markiert wird
            self._is_connected = False
            logging.info("MQTT-Verbindung getrennt.")

    # --- Angepasste publish_message Methode ---
    def publish_message(self, topic, payload, qos=0, retain=False):
        """
        Veröffentlicht eine Nachricht oder stellt sie in die Warteschlange,
        wenn die Verbindung nicht besteht oder das Senden fehlschlägt.

        Args:
            topic (str): Das MQTT-Topic.
            payload (str or bytes): Die zu sendende Nachricht.
            qos (int): Quality of Service Level (0, 1 oder 2).
            retain (bool): Ob die Nachricht als Retained Message gesendet werden soll.

        Returns:
            bool: True, wenn die Nachricht erfolgreich gesendet oder in die Queue gestellt wurde,
                  False, wenn die Queue voll war.
        """
        try:
            # Konvertiere Payload zu Bytes
            if isinstance(payload, str):
                payload_bytes = payload.encode('utf-8')
            elif isinstance(payload, bytes):
                payload_bytes = payload
            else:
                logging.warning(f"Ungültiger Payload-Typ ({type(payload)}) für Topic '{topic}'. Konvertiere zu String.")
                payload_bytes = str(payload).encode('utf-8')

            # Bereite das Queue-Item vor
            queue_item = (topic, payload_bytes, qos, retain)

            if self._is_connected:
                # Wenn verbunden, versuche direkt zu senden
                logging.debug(f"Versuche direkte Veröffentlichung: Topic={topic}, QoS={qos}, Retain={retain}")
                msg_info = self.client.publish(topic, payload_bytes, qos=qos, retain=retain)

                if msg_info.rc == paho_mqtt_client.MQTT_ERR_SUCCESS:
                    logging.debug(f"Nachricht (mid={msg_info.mid}) direkt an Paho übergeben.")
                    return True  # Erfolgreich gesendet (oder an Paho übergeben)
                elif msg_info.rc == paho_mqtt_client.MQTT_ERR_QUEUE_SIZE:
                    logging.warning(
                        f"Paho-interne Warteschlange voll bei direktem Sendeversuch (mid={msg_info.mid}). Nachricht wird in externe Queue gestellt.")
                    # Fällt durch zur Queue-Logik unten
                else:
                    # Anderer Fehler beim direkten Senden
                    logging.error(
                        f"Fehler bei direktem Sendeversuch (mid={msg_info.mid}): {paho_mqtt_client.error_string(msg_info.rc)}. Nachricht wird in externe Queue gestellt.")
                    # Fällt durch zur Queue-Logik unten
            else:
                logging.warning(f"MQTT nicht verbunden. Nachricht für Topic '{topic}' wird in die Queue gestellt.")
                # Fällt durch zur Queue-Logik unten

            # --- Fallback: Nachricht in die Queue stellen ---
            try:
                self._message_queue.put_nowait(queue_item)
                logging.info(
                    f"Nachricht für Topic '{topic}' in die Warteschlange gestellt (Größe: {self._message_queue.qsize()}).")
                # Starte den Verarbeitungs-Thread, falls er nicht läuft (z.B. nach manuellem Stop)
                self._start_queue_processing()
                return True
            except Full:
                logging.error(
                    f"Nachrichten-Warteschlange ist voll (max: {self._max_queue_size}). Nachricht für Topic '{topic}' kann nicht hinzugefügt werden und geht verloren!")
                return False

        except Exception as e:
            logging.error(f"Unerwarteter Fehler in publish_message für Topic '{topic}': {e}", exc_info=True)
            return False  # Im Fehlerfall als nicht erfolgreich betrachten
