# web_ui/mqtt_service.py
import logging
import sys
import os
import json

# Füge das übergeordnete Verzeichnis zum Suchpfad hinzu, um auf MqttHandler und config zugreifen zu können
project_root_ui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root_ui not in sys.path:
    sys.path.insert(0, project_root_ui)

try:
    from mqtt_handler import MqttHandler
    import config # Importiere die Haupt-Konfigurationsdatei
except ImportError as e:
    logging.error(f"Fehler beim Importieren von Modulen in mqtt_service.py: {e}")
    raise

logger = logging.getLogger(__name__)

class MqttService:
    def __init__(self, app_config, pi_status_config_topic=None):
        """
        Initialisiert den MQTT Service.
        """
        self.mqtt_config = app_config
        
        # Wende den Testmodus-Präfix auf das Pi-Status-Topic für den Vergleich an
        topic_prefix = "test/" if config.REC_CONFIG.get("test_mode", False) else ""
        self.pi_status_topic_for_comparison = f"{topic_prefix}{pi_status_config_topic}" if pi_status_config_topic else None
        
        # Holen der Basis-Topic-Namen aus der MQTT_CONFIG
        base_topic_control = config.MQTT_CONFIG.get('topic_control', 'worx/control')
        base_topic_gps = config.MQTT_CONFIG.get('topic_gps', 'worx/gps')
        base_topic_status = config.MQTT_CONFIG.get('topic_status', 'worx/status')
        base_topic_logs = config.MQTT_CONFIG.get('topic_logs', 'worx/logs')

        subscribe_list_with_qos = [
            (f"{topic_prefix}{base_topic_control}", 1),
            (f"{topic_prefix}{base_topic_status}", 0),
            (f"{topic_prefix}{base_topic_gps}", 0),
            (f"{topic_prefix}{base_topic_logs}", 0),  # Logs von Pi
        ]
        if pi_status_config_topic:
            subscribe_list_with_qos.append((f"{topic_prefix}{pi_status_config_topic}", 0))
        
        self.handler = MqttHandler(
            test_mode=config.REC_CONFIG.get("test_mode", False),
            lwt_payload="webui_offline",
            lwt_topic=base_topic_status,
            lwt_qos=1,
            lwt_retain=True,
            subscribe_topics_with_qos=subscribe_list_with_qos
        )

        self._on_status_message_callback = None
        self._on_pi_status_message_callback = None
        self._on_gps_message_callback = None
        self._on_logs_message_callback = None

        self.handler.set_message_callback(self._internal_on_message)
        logger.info("MqttService initialisiert.")

    def _internal_on_message(self, msg):
        """Interner Callback, der Nachrichten an spezifischere Callbacks weiterleitet."""
        try:
            payload = msg.payload.decode('utf-8')
            logger.debug(f"MqttService: Nachricht empfangen auf Topic '{msg.topic}': {payload[:100]}...")

            if msg.topic == self.handler.topic_status:
                if self._on_status_message_callback:
                    self._on_status_message_callback(payload)
            elif msg.topic == self.handler.topic_gps: 
                if self._on_gps_message_callback:
                    self._on_gps_message_callback(payload)
            elif msg.topic == self.handler.topic_logs:
                if self._on_logs_message_callback:
                    self._on_logs_message_callback(payload)
            elif self.pi_status_topic_for_comparison and msg.topic == self.pi_status_topic_for_comparison:
                if self._on_pi_status_message_callback:
                    self._on_pi_status_message_callback(payload)
        except Exception as e:
            logger.error(f"MqttService: Fehler in _internal_on_message: {e}")

    def set_status_update_callback(self, callback):
        self._on_status_message_callback = callback

    def set_pi_status_update_callback(self, callback):
        self._on_pi_status_message_callback = callback

    def set_gps_update_callback(self, callback):
        self._on_gps_message_callback = callback

    def set_logs_update_callback(self, callback):
        self._on_logs_message_callback = callback

    def connect(self):
        self.handler.connect()

    def disconnect(self):
        self.handler.disconnect()

    def is_connected(self):
        return self.handler.is_connected()

    def publish_command(self, command_str):
        """Sendet einen Steuerbefehl an das Control-Topic."""
        return self.publish(self.handler.topic_control, command_str, qos=1)

    def publish(self, topic, payload, qos=0, retain=False):
        """Publiziert eine Nachricht auf einem beliebigen Topic (mit automatischem Test-Präfix)."""
        if self.is_connected():
            topic_prefix = "test/" if config.REC_CONFIG.get("test_mode", False) else ""
            final_topic = topic
            if topic_prefix and not topic.startswith(topic_prefix):
                final_topic = f"{topic_prefix}{topic}"
                
            logger.debug(f"MqttService: Publizierte Nachricht auf Topic '{final_topic}': {str(payload)[:50]}...")
            return self.handler.publish_message(final_topic, payload, qos=qos, retain=retain)
        return False