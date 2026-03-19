import paho.mqtt.client as mqtt
import time
import os
import socket
import struct
from dotenv import load_dotenv

load_dotenv(override=True)

HOST = os.getenv("MQTT_HOST", "192.168.1.155")
PORT = int(os.getenv("MQTT_PORT", 1883))
USER = os.getenv("MQTT_USER", "Nils")
PASSWORD = os.getenv("MQTT_PASSWORD", "")

def encode_utf8(s):
    b = s.encode('utf-8')
    return struct.pack("!H", len(b)) + b

def encode_remaining_length(length):
    rl = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        rl.append(byte)
        if length == 0:
            break
    return bytes(rl)

def build_connect(client_id, username=None, password=None, keepalive=60, mqtt31=False):
    if mqtt31:
        proto_name = b'\x00\x06MQIsdp'
        proto_level = b'\x03'
    else:
        proto_name = b'\x00\x04MQTT'
        proto_level = b'\x04'
    flags = 0x02
    if username: flags |= 0x80
    if password: flags |= 0x40
    var_header = proto_name + proto_level + bytes([flags]) + struct.pack("!H", keepalive)
    payload = encode_utf8(client_id)
    if username: payload += encode_utf8(username)
    if password: payload += encode_utf8(password)
    remaining = var_header + payload
    return b'\x10' + encode_remaining_length(len(remaining)) + remaining

def raw_test(label, packet):
    print(f"\n{'='*50}")
    print(f"TEST: {label}")
    print(f"{'='*50}")
    print(f"  Packet ({len(packet)}b): {packet[:20].hex()}...")
    try:
        sock = socket.create_connection((HOST, PORT), timeout=5)
        sock.settimeout(5)
        sock.sendall(packet)
        try:
            data = sock.recv(64)
            if len(data) >= 4 and data[0] == 0x20:
                rc = data[3]
                print(f"  CONNACK rc={rc} ({'OK' if rc==0 else 'FAILED'})")
                return rc == 0
            else:
                print(f"  Unexpected: {data.hex()}")
        except socket.timeout:
            print(f"  TIMEOUT - no CONNACK")
        sock.close()
    except Exception as e:
        print(f"  EXCEPTION: {e}")
    return False

print(f"Target: {HOST}:{PORT}, User: '{USER}', PW: '{PASSWORD}' ({len(PASSWORD)} chars)")
print(f"PW hex: {PASSWORD.encode().hex()}")

import paho.mqtt.client as mqtt_lib

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"  [CONNECTED!] rc={rc}")

def on_disconnect(client, userdata, flags, rc, properties=None):
    print(f"  [disconnected] rc={rc}")

def on_log(client, userdata, level, buf):
    if "CONNECT" in buf or "CONNACK" in buf or "connection" in buf.lower() or "failed" in buf.lower():
        print(f"  [paho] {buf}")

print(f"Paho long-running test: connecting to {HOST}:{PORT} as '{USER}'")
print("Letting paho retry for 60 seconds...")

client = mqtt_lib.Client(mqtt_lib.CallbackAPIVersion.VERSION2, client_id=f"longtest_{int(time.time())}", protocol=mqtt_lib.MQTTv311)
client.username_pw_set(USER, PASSWORD)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_log = on_log
client.reconnect_delay_set(min_delay=1, max_delay=5)

try:
    client.connect_async(HOST, PORT, 60)
    client.loop_start()
    for i in range(60):
        time.sleep(1)
        connected = client.is_connected()
        if i % 10 == 0 or connected:
            print(f"  [{i+1}s] connected={connected}")
        if connected:
            print("  >>> SUCCESS! MQTT connected!")
            break
    else:
        print("  >>> FAILED after 60s - broker auth consistently hanging")
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"  EXCEPTION: {e}")

print("\n--- DONE ---")
