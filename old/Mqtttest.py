import paho.mqtt.client as mqtt
import time
import uuid

# --- KONFIGURATION ---
MQTT_HOST = "192.168.1.155"
MQTT_USER = "worxtest"
MQTT_PASS = "robot2026!"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ VERBUNDEN! (Zeit: {time.strftime('%H:%M:%S')})")
        client.subscribe("worx/test/command")
        print("Abonniert auf: worx/test/command")
    else:
        print(f"❌ Fehler beim Verbinden: {rc}")

def on_message(client, userdata, msg):
    print(f"📩 Nachricht empfangen auf {msg.topic}: {msg.payload.decode()}")

# Client Setup
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"Worx_Surface_{uuid.uuid4().hex[:4]}")
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

try:
    print(f"Starte Dauertest zu {MQTT_HOST}...")
    client.connect(MQTT_HOST, 1883, keepalive=60)
    
    # loop_start() lässt den Netzwerk-Teil in einem eigenen Thread laufen
    client.loop_start()

    count = 0
    while True:
        count += 1
        msg = f"Surface Lebenszeichen #{count} um {time.strftime('%H:%M:%S')}"
        client.publish("worx/test/status", msg)
        print(f"📤 Gesendet: {msg}")
        
        # Wir warten 10 Sekunden, damit wir die 20s Marke mehrfach testen
        time.sleep(10)

except KeyboardInterrupt:
    print("\nTest durch Nutzer beendet.")
    client.loop_stop()
    client.disconnect()