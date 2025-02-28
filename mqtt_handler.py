import paho.mqtt.client as mqtt
from config import MQTT_CONFIG, REC_CONFIG


class MqttHandler:
    def __init__(self):
        test_mode = REC_CONFIG["test_mode"]
        self.broker = MQTT_CONFIG["host_lokal"] if test_mode else MQTT_CONFIG[
            "host"]  # Korrektur: 'broker' durch 'host' und 'broker_lokal' durch 'host_lokal' ersetzt
        self.port = MQTT_CONFIG["port_lokal"] if test_mode else MQTT_CONFIG[
            "port"]  # Korrektur: 'port' und 'port_lokal' hinzugefügt
        self.user = MQTT_CONFIG["user_local"] if test_mode else MQTT_CONFIG["user"]
        self.password = MQTT_CONFIG["password_local"] if test_mode else MQTT_CONFIG["password"]
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.V2)  # Korrektur: Callback API Version 2

    def connect(self):
        if self.user and self.password:
            self.mqtt_client.username_pw_set(self.user, self.password)
        self.mqtt_client.connect(self.broker, self.port, 60)
        self.mqtt_client.loop_start()

    def disconnect(self):
        if self.mqtt_client:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
