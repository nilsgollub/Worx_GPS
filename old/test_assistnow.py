# test_assistnow.py
import requests
import os
from dotenv import load_dotenv

# Konfiguration laden
load_dotenv(override=True)

TOKEN = os.getenv("ASSIST_NOW_TOKEN")
URL = "https://api.thingstream.io/location/services/assistnow/online" # Erweiterter Pfad

def test_connection():
    if not TOKEN or "dein_neuer_token" in TOKEN:
        print("\n[!] FEHLER: Kein gültiger TOKEN in der .env gefunden.")
        print("Bitte trage den Token aus deinem Thingstream-Account (z.B. sKbn...) in die .env Datei ein.")
        return

    print(f"\n[*] Teste AssistNow MGA Verbindung...")
    print(f"[*] Ziel: {URL}")
    print(f"[*] Token (verkürzt): {TOKEN[:5]}...")

    params = {
        "token": TOKEN,
        "gnss": "gps",
        "format": "mga"
    }
    
    headers = {"useragent": "Thingstream Test Client"}

    try:
        response = requests.get(URL, params=params, headers=headers, timeout=10)
        
        # Prüfe auf HTTP-Fehler
        if response.status_code == 200:
            if response.content:
                print(f"\n[OK] Erfolg! {len(response.content)} Bytes an GPS-Hilfsdaten empfangen.")
                print("AssistNow ist korrekt konfiguriert und liefert MGA-Daten aus.")
            else:
                print("\n[!] WARNUNG: Verbindung erfolgreich, aber u-blox hat 0 Bytes gesendet.")
        elif response.status_code == 403:
            print(f"\n[!] FEHLER: Zugriff verweigert (403). Dein Token ist wahrscheinlich falsch oder der Plan nicht aktiv.")
        elif response.status_code == 429:
            print(f"\n[!] FEHLER: Rate-Limit erreicht (429). Zu viele Anfragen.")
        else:
            print(f"\n[!] FEHLER: Server antwortete mit Status {response.status_code}.")
            print(f"Antwort: {response.text}")

    except Exception as e:
        print(f"\n[!] UNERWARTETER FEHLER: {str(e)}")

if __name__ == "__main__":
    test_connection()
