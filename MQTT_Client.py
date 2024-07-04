import tkinter as tk
import paho.mqtt.client as mqtt

# MQTT-Broker-Details
broker_address = "homeassistant.local"
broker_port = 1883
username = "nilsgollub"
password = "JhiswenP3003!"
topics = ["worx/control", "worx/gps", "worx/status"]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        status_label.config(text="Verbunden")
        for topic in topics:
            client.subscribe(topic)
    else:
        status_label.config(text="Verbindung fehlgeschlagen")

def on_message(client, userdata, msg):
    message_text.insert(tk.END, f"{msg.topic}: {msg.payload.decode()}\n")

def send_message(message):
    client.publish("worx/control", message)

# GUI erstellen
window = tk.Tk()
window.title("Worx Mower Steuerung")

buttons = [
    ("fakegps_off", "Fake GPS Aus"),
    ("fakegps_on", "Fake GPS An"),
    ("problem", "Problem"),
    ("restart", "Neustart"),
    ("start", "Start"),
    ("stop", "Stop")
]

for i, (message, label_text) in enumerate(buttons):
    button = tk.Button(window, text=label_text, command=lambda m=message: send_message(m))
    button.grid(row=i // 2, column=i % 2, padx=5, pady=5)

status_label = tk.Label(window, text="Nicht verbunden")
status_label.grid(row=len(buttons) // 2, column=0, columnspan=2, pady=10)

message_text = tk.Text(window)
message_text.grid(row=len(buttons) // 2 + 1, column=0, columnspan=2, padx=5, pady=5)

# MQTT Client erstellen und verbinden
client = mqtt.Client()
client.username_pw_set(username, password)
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker_address, broker_port)
client.loop_start()

window.mainloop()
