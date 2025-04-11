
# Worx_GPS_Rec.py
import sys
import pkg_resources

print(f"--- Debug Info ---")
print(f"Python Executable: {sys.executable}")
try:
    paho_version = pkg_resources.get_distribution("paho-mqtt").version
    print(f"Paho-MQTT Version: {paho_version}")
except pkg_resources.DistributionNotFound:
    print("Paho-MQTT Version: Not Found!")
print(f"--- End Debug Info ---")
from mqtt_handler import MqttHandler
from gps_handler import GpsHandler
from data_recorder import DataRecorder
from problem_detection import ProblemDetector
from config import REC_CONFIG
import time
import subprocess


class WorxGpsRec:
    def __init__(self):
        self.test_mode = REC_CONFIG["test_mode"]
        self.mqtt_handler = MqttHandler(self.test_mode)
        self.gps_handler = GpsHandler()
        self.data_recorder = DataRecorder(mqtt_handler=self.mqtt_handler,baud_rate=REC_CONFIG["baudrate"],mqtt_broker=self.mqtt_handler.broker, # Broker vom Handler holenmqtt_port=self.mqtt_handler.port      # Port vom Handler holen
        )
        self.problem_detector = ProblemDetector(self.mqtt_handler)
        self.is_recording = False
        self.mqtt_handler.set_message_callback(self.on_mqtt_message)
        self.mqtt_handler.connect()

    def on_mqtt_message(self, msg):
        if msg.topic == self.mqtt_handler.topic_control:
            payload = msg.payload.decode()
            if payload == "start":
                self.start_recording()
            elif payload == "stop" and self.is_recording:
                self.stop_recording()
            elif payload == "problem":
                self.send_problem_message()
            elif payload == "fakegps_on":
                self.gps_handler.change_gps_mode("fake_route")
            elif payload == "fakegps_off":
                self.gps_handler.change_gps_mode("real")
            elif payload == "start_route":
                self.gps_handler.change_gps_mode("fake_route")
            elif payload == "stop_route":
                self.gps_handler.change_gps_mode("fake_random")
            elif payload == "random_points":
                self.gps_handler.change_gps_mode("fake_random")
            elif payload == "shutdown":
                print("Shutdown-Befehl empfangen. Fahre Raspberry Pi herunter...")
                subprocess.call(["sudo", "shutdown", "-h", "now"])
            else:
                self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_command")

    def start_recording(self):
        self.is_recording = True
        self.data_recorder.clear_buffer()  # Puffer leeren beim Start
        self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording started")

    def stop_recording(self):
        self.is_recording = False
        self.data_recorder.send_buffer_data()
        self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "recording stopped")

    def send_problem_message(self):
        gps_data = self.gps_handler.get_gps_data()
        if gps_data:
            problem_data = f"problem,{gps_data['lat']},{gps_data['lon']}"
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, problem_data)
        else:
            self.mqtt_handler.publish_message(self.mqtt_handler.topic_status, "error_gps")

    def main_loop(self):
        last_status_send = time.time() - 10  # Sicherstellen, dass der erste Status sofort gesendet wird
        while True:
            if self.is_recording:
                gps_data = self.gps_handler.get_gps_data()
                if gps_data:  # Nur wenn gültige GPS-Daten vorhanden sind
                    # Überprüfen, ob die GPS-Daten innerhalb der Grundstücksgrenzen liegen
                    if self.gps_handler.is_inside_boundaries(gps_data["lat"], gps_data["lon"]) or self.test_mode:
                        # Daten im Puffer sammeln (immer, auch im Testmodus)
                        self.data_recorder.add_gps_data(gps_data)
                        # Neue Position an Problem Detector senden
                        self.problem_detector.add_position(gps_data)
                    else:
                        print(f"Koordinaten ({gps_data['lat']},{gps_data['lon']}) liegen außerhalb des Grundstücks.")
                else:
                    print("Keine gültigen GPS-Daten.")

            # Auch wenn keine Aufzeichnung läuft, Status-Updates senden (alle 10 Sekunden)
            if time.time() - last_status_send >= 10:
                gps_data = self.gps_handler.get_gps_data()
                if gps_data:
                    status_message = f"{gps_data['lat']},{gps_data['lon']},{gps_data['timestamp']},{gps_data['satellites']}"  # Statusmeldung erstellen (ohne mode)
                    self.mqtt_handler.publish_message(self.mqtt_handler.topic_status,
                                                      status_message)  # Statusmeldung senden
                else:
                    print("Keine gültigen GPS-Daten für Statusmeldung.")
                last_status_send = time.time()
            # AssistNow Offline-Daten aktualisieren (einmal täglich)
            self.gps_handler.check_assist_now()
            time.sleep(REC_CONFIG["storage_interval"])  # Speicherintervall von 2 Sekunden


if __name__ == "__main__":
    worx_gps_rec = WorxGpsRec()
    worx_gps_rec.main_loop()
