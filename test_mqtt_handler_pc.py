import logging
from mqtt_handler import MqttHandler
import time
from config import MQTT_CONFIG

logging.basicConfig(level=logging.INFO)

print(f"Versuche Verbindung zu: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}")

handler = MqttHandler(test_mode=False)
handler.connect()

time.sleep(5)
if handler.is_connected():
    print("SUCCESS: MqttHandler is connected!")
else:
    print("FAILURE: MqttHandler IS NOT connected.")

handler.disconnect()
