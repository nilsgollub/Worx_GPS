# web_ui/mqtt_service.py
import logging
import sys
import os

# Füge das übergeordnete Verzeichnis zum Suchpfad hinzu, um auf MqttHandler und config zugreifen zu können
project_root_ui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# project_root_ui ist das Verzeichnis 'Worx_GPS', das mqtt_handler.py und config.py enthält.
if project_root_ui not in sys.path:
    sys.path.insert(0, project_root_ui)

try:
    from mqtt_handler import MqttHandler
    import config # Importiere die Haupt-Konfigurationsdatei
except ImportError as e:
    logging.error(f"Fehler beim Importieren von Modulen in mqtt_service.py: {e}")
    logging.error(f"Aktueller sys.path: {sys.path}")
    # Fallback, falls das Skript direkt im web_ui Verzeichnis ausgeführt wird und der Pfad nicht korrekt ist
    # Dies ist eher für Entwicklungszwecke und sollte in einer produktiven Umgebung nicht nötig sein.
    if project_root_ui not in sys.path:
        sys.path.insert(0, project_root_ui) # Fügt web_ui hinzu
        # Versuche erneut zu importieren
        # from mqtt_handler import MqttHandler # Wird nicht gefunden, da es im Root liegt
        # import config
    raise

logger = logging.getLogger(__name__)

class MqttService:
    def __init__(self, app_config, pi_status_config_topic=None):
        """
        Initialisiert den MQTT Service.
        Args:
            app_config (dict): Die MQTT_CONFIG aus der Haupt-config.py.
            pi_status_config_topic (str, optional): Das spezifische Pi-Status-Topic.
        """
        self.mqtt_config = app_config
        
        # Wende den Testmodus-Präfix auf das Pi-Status-Topic für den Vergleich an
        topic_prefix = "test/" if config.REC_CONFIG.get("test_mode", False) else ""
        self.pi_status_topic_for_comparison = f"{topic_prefix}{pi_status_config_topic}" if pi_status_config_topic else None

        # --- NEU: Liste der zu abonnierenden Topics erstellen ---
        # Basis-Topics (ohne Präfix, da MqttHandler den Präfix basierend auf test_mode selbst anwendet,
        # oder wir den Präfix hier explizit anwenden und test_mode=False an MqttHandler übergeben,
        # um doppelte Präfixe zu vermeiden. Letzteres ist sauberer.)
        
        # Holen der Basis-Topic-Namen aus der MQTT_CONFIG
        base_topic_control = config.MQTT_CONFIG.get('topic_control', 'worx/control')
        base_topic_gps = config.MQTT_CONFIG.get('topic_gps', 'worx/gps') # WebUI braucht GPS-Rohdaten evtl. nicht
        base_topic_status = config.MQTT_CONFIG.get('topic_status', 'worx/status')

        subscribe_list_with_qos = [
            (f"{topic_prefix}{base_topic_control}", 1),
            (f"{topic_prefix}{base_topic_status}", 0)
            # (f"{topic_prefix}{base_topic_gps}", 0), # Auskommentiert, falls WebUI keine GPS-Rohdaten braucht
        ]
        if pi_status_config_topic: # pi_status_config_topic ist bereits der Basisname
            subscribe_list_with_qos.append((f"{topic_prefix}{pi_status_config_topic}", 0))
        
        # Der MqttHandler wird mit test_mode initialisiert, um LWT korrekt zu setzen.
        # Die subscribe_list_with_qos enthält bereits die korrekten (ggf. gepräfixten) Topics.
        self.handler = MqttHandler(
            test_mode=config.REC_CONFIG.get("test_mode", False),
            lwt_payload="webui_offline", # Spezifisches LWT für die WebUI
            lwt_topic=base_topic_status, # Übergib das Basis-Topic; MqttHandler kümmert sich um Präfix
            lwt_qos=1,
            lwt_retain=True, # Komma hier hinzugefügt
            subscribe_topics_with_qos=subscribe_list_with_qos # NEU
        )

        self._on_status_message_callback = None
        self._on_pi_status_message_callback = None
        self._on_gps_message_callback = None # Für GPS Rohdaten, falls benötigt

        self.handler.set_message_callback(self._internal_on_message)
        logger.info("MqttService initialisiert.")

    def _internal_on_message(self, msg):
        """Interner Callback, der Nachrichten an spezifischere Callbacks weiterleitet."""
        try:
            payload = msg.payload.decode('utf-8')
            logger.debug(f"MqttService: Nachricht empfangen auf Topic '{msg.topic}': {payload[:100]}...")

            # Vergleiche mit den Topics, die der MqttHandler abonniert hat
            if msg.topic == self.handler.topic_status:
                if self._on_status_message_callback:
                    self._on_status_message_callback(payload)
            elif msg.topic == self.handler.topic_gps: 
                if self._on_gps_message_callback:
                    self._on_gps_message_callback(payload)
            elif self.pi_status_topic_for_comparison and msg.topic == self.pi_status_topic_for_comparison: # NEU: Vergleich mit präfixbehaftetem Topic
                if self._on_pi_status_message_callback:
                    self._on_pi_status_message_callback(payload)
            else:
                logger.debug(f"MqttService: Nachricht auf unbehandeltem Topic '{msg.topic}'")

        except UnicodeDecodeError:
            logger.warning(f"MqttService: Konnte Payload auf Topic '{msg.topic}' nicht als UTF-8 dekodieren.")
        except Exception as e:
            logger.error(f"MqttService: Fehler in _internal_on_message: {e}", exc_info=True)

    def set_status_update_callback(self, callback):
        self._on_status_message_callback = callback

    def set_pi_status_update_callback(self, callback):
        self._on_pi_status_message_callback = callback

    def set_gps_update_callback(self, callback):
        self._on_gps_message_callback = callback

    def connect(self):
        logger.info("MqttService: Verbinde zum Broker...")
        self.handler.connect()

    def disconnect(self):
        logger.info("MqttService: Trenne Verbindung zum Broker...")
        self.handler.disconnect()

    def is_connected(self):
        return self.handler.is_connected()

    def publish_command(self, command_str):
        """Sendet einen Steuerbefehl an das Control-Topic."""
        if self.is_connected():
            logger.info(f"MqttService: Sende Befehl '{command_str}' an Topic '{self.handler.topic_control}'")
            # Der MqttHandler hat eine publish_message Methode
            self.handler.publish_message(self.handler.topic_control, command_str, qos=1)
            return True
        else:
            logger.error(f"MqttService: Kann Befehl '{command_str}' nicht senden, nicht verbunden.")
            return False