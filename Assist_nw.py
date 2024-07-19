import requests
import os
from dotenv import load_dotenv
from pyubx2 import UBXMessage

load_dotenv(".env")  # Laden der Umgebungsvariablen

# AssistNow Offline Einstellungen
assist_now_token = os.getenv("ASSIST_NOW_TOKEN")
assist_now_offline_url = "https://offline-live1.services.u-blox.com/GetOfflineData.ashx"
assist_now_enabled = os.getenv("ASSIST_NOW_ENABLED", "False").lower() == "true"
assist_now_path = "/dev/ttyACM0"  # Pfad zur seriellen Schnittstelle

# Funktion zum Herunterladen von AssistNow Offline-Daten
def download_assist_now_data():
    try:
        headers = {"useragent": "Thingstream Client"}
        params = {
            "token": assist_now_token,
            "gnss": "gps",
            "alm": "gps",
            "days": 7,
            "resolution": 1
        }
        response = requests.get(assist_now_offline_url, headers=headers, params=params)
        response.raise_for_status()  # Fehler auslösen, wenn der Download fehlschlägt
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Herunterladen der AssistNow Offline-Daten: {e}")
        return None  # Rückgabewert None bei Fehler

# Funktion zum Senden von AssistNow Offline-Daten an das GPS-Modul
def send_assist_now_data(data):
    try:
        with open(assist_now_path, "wb") as f:  # Pfad zur seriellen Schnittstelle anpassen
            f.write(data)  # UBX-Daten direkt senden
        print("AssistNow Offline-Daten erfolgreich gesendet.")
    except Exception as e:
        print(f"Fehler beim Senden der AssistNow Offline-Daten: {e}")

if __name__ == "__main__":
    if assist_now_enabled:
        data = download_assist_now_data()
        if data is not None:
            send_assist_now_data(data)
        else:
            print("AssistNow Offline-Daten konnten nicht heruntergeladen werden.")
    else:
        print("AssistNow Offline ist deaktiviert.")
