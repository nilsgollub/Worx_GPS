# mqtt_handler.py
import paho.mqtt.client as mqtt
import time
from config import MQTT_CONFIG


class MqttHandler:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.broker = MQTT_CONFIG["broker_lokal"] if test_mode else MQTT_CONFIG["broker"]
        self.port = MQTT_CONFIG["port_lokal"] if test_mode else MQTT_CONFIG["port"]
        self.user = MQTT_CONFIG["user_local"] if test_mode else MQTT_CONFIG["user"]
        self.password = MQTT_CONFIG["password_local"] if test_mode else MQTT_CONFIG["password"]
        self.topic_control = MQTT_CONFIG["topic_control"]
        self.topic_gps = MQTT_CONFIG["topic_gps"]
        self.topic_status = MQTT_CONFIG["topic_status"]
        self.client = mqtt.Client()
        self.client.username_pw_set(self.user, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.is_connected = False
        self.message_callback = None

    def connect(self):
        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
        except ConnectionRefusedError:
            print(f"Verbindung mit MQTT-Broker fehlgeschlagen ({self.broker}:{self.port}).")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.is_connected = True
            print(f"Verbunden mit MQTT Broker: {self.broker}:{self.port}")
            self.client.subscribe(self.topic_control)
            self.client.subscribe(self.topic_gps)
            self.client.subscribe(self.topic_status)
        else:
            print(f"MQTT-Verbindung fehlgeschlagen (Code: {rc})")
            self.is_connected = False

    def on_message(self, client, userdata, msg):
        if self.message_callback:
            self.message_callback(msg)

    def set_message_callback(self, callback):
        self.message_callback = callback

    def publish_message(self, topic, payload):
        if self.is_connected:
            try:
                self.client.publish(topic, payload)
                print(f"MQTT-Nachricht gesendet an {topic}: {payload}")
            except Exception as e:
                print(f"Fehler beim Senden der MQTT-Nachricht: {e}")
        else:
            print("MQTT nicht verbunden. Nachricht nicht gesendet.")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
