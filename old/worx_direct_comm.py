# worx_direct_comm.py
import os
import json
import time
import uuid
import logging
import threading
import ssl 
from datetime import datetime

import requests
import paho.mqtt.client as mqtt
import jwt # Für JWT-Dekodierung
import certifi 
from dotenv import load_dotenv

# --- Konfiguration ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s') # Set to DEBUG for verbose Paho logs
logger = logging.getLogger(__name__)

load_dotenv() # Lädt Variablen aus einer .env Datei

# Positec API Konfiguration (aus Umgebungsvariablen laden)
WORX_AUTH_BASE_URL = os.getenv("WORX_AUTH_BASE_URL")
WORX_CLIENT_ID = os.getenv("WORX_CLIENT_ID")
WORX_PRODUCT_API_URL = os.getenv("WORX_PRODUCT_API_URL")
WORX_SCOPE = os.getenv("WORX_SCOPE")
WORX_MQTT_API_PREFIX = os.getenv("WORX_MQTT_API_PREFIX")

# Benutzeranmeldeinformationen (aus Umgebungsvariablen laden)
WORX_EMAIL = os.getenv("WORX_EMAIL")
WORX_PASSWORD = os.getenv("WORX_PASSWORD")

required_env_vars = ["WORX_EMAIL", "WORX_PASSWORD", "WORX_AUTH_BASE_URL", "WORX_CLIENT_ID", "WORX_PRODUCT_API_URL", "WORX_SCOPE", "WORX_MQTT_API_PREFIX"]
missing_vars = [var for var in required_env_vars if os.getenv(var) is None]

if missing_vars:
    logger.error(f"Fehlende Umgebungsvariablen in .env Datei oder Umgebung: {', '.join(missing_vars)}")
    logger.info("Bitte erstelle eine .env Datei im Projektverzeichnis mit:")
    logger.info("WORX_EMAIL=deine_email@example.com")
    logger.info("WORX_PASSWORD=dein_passwort")
    logger.info("WORX_AUTH_BASE_URL=...")
    logger.info("WORX_CLIENT_ID=...")
    logger.info("WORX_PRODUCT_API_URL=...")
    logger.info("WORX_SCOPE=...")
    logger.info("WORX_MQTT_API_PREFIX=...")
    exit()

class PositecCloudClient:
    """
    Kümmert sich um die Authentifizierung und den Abruf von Produktinformationen
    von der Positec (Worx) Cloud API.
    """
    def __init__(self, auth_base_url, client_id, product_api_url, scope):
        self.auth_base_url = auth_base_url
        self.client_id = client_id
        self.product_api_url = product_api_url
        self.scope = scope
        self.access_token = None
        self.refresh_token = None
        self.id_token = None
        self.user_id = None
        self.token_expires_at = 0
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _decode_id_token(self):
        """
        Versucht, die Benutzer-ID aus dem ID-Token zu extrahieren, falls vorhanden.
        Wird nicht mehr als primäre Quelle für die User-ID verwendet.
        """
        if not self.id_token:
            return None
        try:
            decoded_token = jwt.decode(self.id_token, options={"verify_signature": False})
            self.user_id = decoded_token.get("sub") # 'sub' ist typischerweise die User-ID
            logger.info(f"Benutzer-ID aus Token extrahiert: {self.user_id}")
            return self.user_id
        except jwt.ExpiredSignatureError:
            logger.error("ID-Token ist abgelaufen.")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Ungültiges ID-Token: {e}")
            return None

    def _fetch_user_id_from_api(self):
        """
        Versucht, die Benutzer-ID aus den Produktinformationen zu extrahieren.
        Diese Methode wird aufgerufen, nachdem die Produkte erfolgreich abgerufen wurden.
        """
        logger.debug("_fetch_user_id_from_api ist nicht mehr für den primären User-ID-Abruf zuständig.")
        if self.user_id: 
            return True
        
        if self.id_token:
            logger.info("Versuche User-ID aus vorhandenem ID-Token als Fallback zu extrahieren.")
            return self._decode_id_token() is not None
            
        return False

    def login(self, email, password):
        """Führt den OAuth2 Login durch."""
        token_url = f"{self.auth_base_url}oauth/token"
        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": email,
            "password": password,
            "scope": self.scope
        }
        try:
            response = self.session.post(token_url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
            response.raise_for_status() 
            token_data = response.json()

            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")
            self.id_token = token_data.get("id_token") 
            expires_in = token_data.get("expires_in", 3600) 
            self.token_expires_at = time.time() + expires_in - 60 

            if not self.access_token: 
                logger.error("Login fehlgeschlagen: Access Token nicht im Response.")
                return False

            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
            logger.info("Access Token erfolgreich erhalten.")
            logger.info("Erfolgreich bei der Positec Cloud angemeldet.")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Fehler beim Login: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler bei der Anfrage während des Logins: {e}")
        except json.JSONDecodeError:
            logger.error("Fehler beim Parsen der JSON-Antwort vom Login-Endpunkt.")
        return False

    def _ensure_token_valid(self):
        """Stellt sicher, dass das Token gültig ist, erneuert es ggf."""
        if time.time() >= self.token_expires_at:
            logger.info("Access Token ist abgelaufen oder läuft bald ab. Erneuere Token...")
            return self._refresh_access_token()
        return True

    def _refresh_access_token(self):
        """Erneuert das Access Token mit dem Refresh Token."""
        if not self.refresh_token:
            logger.error("Kein Refresh Token vorhanden, um das Access Token zu erneuern.")
            return False

        token_url = f"{self.auth_base_url}oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": self.refresh_token,
        }
        try:
            response = self.session.post(token_url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data.get("access_token")
            self.id_token = token_data.get("id_token") 
            new_refresh_token = token_data.get("refresh_token")
            if new_refresh_token:
                self.refresh_token = new_refresh_token

            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = time.time() + expires_in - 60

            if not self.access_token:
                logger.error("Token-Erneuerung fehlgeschlagen: Access Token nicht im Response.")
                return False

            if self.id_token: 
                self._decode_id_token()
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
            logger.info("Access Token erfolgreich erneuert.")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Fehler bei Token-Erneuerung: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler bei der Anfrage während der Token-Erneuerung: {e}")
        return False

    def get_products(self):
        """Ruft die Liste der Produkte (Mäher) des Benutzers ab."""
        if not self._ensure_token_valid():
            return None

        products_url = f"{self.product_api_url}product-items"
        try:
            response = self.session.get(products_url)
            response.raise_for_status()
            products = response.json()
            logger.info(f"Produkte erfolgreich abgerufen: {len(products)} Gerät(e) gefunden.")
            return products
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Fehler beim Abrufen der Produkte: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler bei der Anfrage während des Produktabrufs: {e}")
        except json.JSONDecodeError:
            logger.error("Fehler beim Parsen der JSON-Antwort vom Produkt-Endpunkt.")
        return None

class WorxLandroidMQTTClient:
    """
    Verwaltet die MQTT-Verbindung zum Worx Landroid Mäher.
    """
    def __init__(self, broker_url, broker_port, mqtt_api_prefix, user_id, access_token, product_info):
        self.broker_url = broker_url
        self.broker_port = int(broker_port)
        self.product_info = product_info
        self.serial_number = product_info.get("serial_number")
        self.command_in_topic = product_info.get("mqtt_topics", {}).get("command_in")
        self.command_out_topic = product_info.get("mqtt_topics", {}).get("command_out")

        app_instance_id = str(uuid.uuid4()) 
        self.client_id = f"{mqtt_api_prefix}/USER/{user_id}/Landroid/{app_instance_id}" 

        token_parts = access_token.split('.')
        if len(token_parts) == 3: 
            self.mqtt_username = f"da?jwt={token_parts[0]}.{token_parts[1]}"
            self.mqtt_password = token_parts[2]
            logger.debug(f"MQTT Username derived: {self.mqtt_username}") 
        else:
            logger.error("Ungültiges Access Token Format für MQTT Credentials.")
            self.mqtt_username = None
            self.mqtt_password = None

        self.mqtt_client = mqtt.Client(client_id=self.client_id, 
                                       protocol=mqtt.MQTTv311, 
                                       callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                       clean_session=True) 
        
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_log = self._on_log 
        
        if self.broker_port == 443:
            self.mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2) 
            
            keylog_filename = os.getenv("SSLKEYLOGFILE")
            if keylog_filename and hasattr(self.mqtt_client, '_ssl_context') and self.mqtt_client._ssl_context:
                self.mqtt_client._ssl_context.keylog_filename = keylog_filename
                logger.info(f"SSL Key Logging aktiviert. Schlüssel werden in '{keylog_filename}' geschrieben.")
            elif keylog_filename:
                logger.warning("SSLKEYLOGFILE gesetzt, aber _ssl_context nicht verfügbar für Key Logging.")

            logger.debug("MQTT TLS enabled using Paho's tls_set() with TLSv1.2.")
            
            self.mqtt_client.tls_insecure_set(True)
            logger.warning("!!! MQTT TLS-Verifizierung für Diagnosezwecke deaktiviert (tls_insecure_set(True)) !!!")

        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            logger.debug("MQTT username and password set.")

        will_topic = f"{mqtt_api_prefix}/USER/{user_id}/Landroid/{app_instance_id}/status"
        will_payload = json.dumps({"online": False}) 
        self.mqtt_client.will_set(will_topic, payload=will_payload, qos=1, retain=True)
        logger.info(f"MQTT Will gesetzt: Topic='{will_topic}', Payload='{will_payload}'")

        self._stop_event = threading.Event()

    def _on_log(self, client, userdata, level, buf):
        logger.info(f"MQTT Log (Paho Level {level}): {buf}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        logger.debug(f"on_connect callback called. Reason Code: {reason_code}, Properties: {properties}")
        if reason_code == 0:
            logger.info(f"Erfolgreich mit MQTT Broker {self.broker_url} verbunden.")
            if self.command_out_topic:
                try:
                    result, mid = client.subscribe(self.command_out_topic)
                    if result == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(f"Abonnementanfrage für Topic '{self.command_out_topic}' gesendet (MID: {mid}).")
                    else:
                        logger.error(f"Fehler beim Senden der Abonnementanfrage für Topic '{self.command_out_topic}'. Code: {result}")
                except Exception as e:
                    logger.error(f"Ausnahme beim Abonnieren von Topic '{self.command_out_topic}': {e}", exc_info=True)
            else:
                logger.error("Kein 'command_out_topic' für diesen Mäher definiert.")
        else:
            logger.error(f"Verbindung zum MQTT Broker fehlgeschlagen. Code: {reason_code}")
            if hasattr(reason_code, 'getName'): 
                 logger.error(f"Broker Reason Name: {reason_code.getName()}")
            if reason_code == mqtt.MQTT_ERR_CONN_REFUSED:
                 logger.error("MQTT Connection Refused: Überprüfe Broker-Adresse, Port und Client-ID.")
            elif reason_code == mqtt.MQTT_ERR_AUTH:
                 logger.error("MQTT Authentication Failed: Überprüfe Username/Passwort (abgeleitet vom Token).")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode('utf-8')
            logger.info(f"--- Nachricht von Mäher ({self.serial_number}) auf Topic '{msg.topic}' ---")
            try:
                data = json.loads(payload_str)
                logger.info(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                logger.info(f"Roh-Payload (kein valides JSON): {payload_str}")
            logger.info("--------------------------------------------------------------------")
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der MQTT Nachricht: {e}", exc_info=True)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0: 
            logger.info("Verbindung zum MQTT Broker sauber getrennt.")
            return

        reason_description = "N/A"
        if isinstance(reason_code, int): 
            if reason_code == mqtt.MQTT_ERR_SUCCESS: 
                 reason_description = "MQTT_ERR_SUCCESS (Unexpected)"
            elif reason_code == mqtt.MQTT_ERR_NOMEM:
                 reason_description = "MQTT_ERR_NOMEM (Out of memory)"
            elif reason_code == mqtt.MQTT_ERR_PROTOCOL:
                 reason_description = "MQTT_ERR_PROTOCOL (A network protocol error occurred)"
            elif reason_code == mqtt.MQTT_ERR_INVAL:
                 reason_description = "MQTT_ERR_INVAL (Invalid input parameters)"
            else:
                 reason_description = f"Paho Client Error Code {reason_code}"
        elif hasattr(reason_code, 'getName'): 
            reason_description = f"Broker Reason: {reason_code.getName()} (Value: {reason_code.value})"
        else: 
            reason_description = str(reason_code)

        logger.warning(f"Unerwartet vom MQTT Broker getrennt. Reason: {reason_description}. Typ: {type(reason_code)}. Versuche Reconnect...")
    
    def connect_and_loop(self):
        if not self.mqtt_username or not self.command_out_topic:
            logger.error("MQTT Verbindung kann nicht hergestellt werden: Fehlende Credentials oder Topic.")
            return

        try:
            logger.info(f"Versuche MQTT-Verbindung zu {self.broker_url}:{self.broker_port} mit Client ID: {self.client_id}, Keepalive: 60s")
            
            target_host_for_connect = self.broker_url # Standardmäßig Hostname
            try:
                broker_ip = socket.gethostbyname(self.broker_url)
                logger.debug(f"IP Adresse für {self.broker_url} ist {broker_ip}")
                target_host_for_connect = broker_ip # Explizit die aufgelöste IPv4-Adresse verwenden
            except socket.gaierror:
                logger.error(f"Konnte IP für {self.broker_url} nicht auflösen.")
            
            try: # Experimenteller Socket-Keepalive-Test
                sock_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock_test.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                sock_test.close() 
                logger.debug("Experimenteller Socket-Keepalive-Options-Test durchgeführt (Socket wieder geschlossen).")
            except Exception as e_sock:
                logger.warning(f"Experimenteller Socket-Options-Test fehlgeschlagen: {e_sock}")

            # Verwende connect_async()
            logger.info(f"Paho MQTT connect_async() wird initiiert zu Host/IP: {target_host_for_connect} Port: {self.broker_port}")
            self.mqtt_client.connect_async(target_host_for_connect, self.broker_port, keepalive=60)
            
            self.mqtt_client.loop_start() 
            logger.info("MQTT Client Loop gestartet. Warte auf Nachrichten...")

            while not self._stop_event.is_set():
                time.sleep(1)
        except ssl.SSLError as e:
            logger.error(f"Ein SSL-Fehler ist während des Verbindungsaufbaus aufgetreten: {e}", exc_info=True)
        except ConnectionRefusedError:
            logger.error(f"MQTT Connection Refused: Der Broker unter {self.broker_url}:{self.broker_port} hat die Verbindung abgelehnt.")
        except socket.gaierror: 
            logger.error(f"MQTT Broker Hostname {self.broker_url} konnte nicht aufgelöst werden.")
        except Exception as e:
            logger.error(f"Fehler beim Verbinden oder im MQTT Loop: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        logger.info("Stoppe MQTT Client...")
        self._stop_event.set()
        if self.mqtt_client:
            self.mqtt_client.loop_stop() 
            self.mqtt_client.disconnect()
            logger.info("MQTT Client getrennt.")

def main():
    logger.info("Starte Worx Landroid Direktkommunikations-Skript...")

    cloud_client = PositecCloudClient(
        auth_base_url=WORX_AUTH_BASE_URL,
        client_id=WORX_CLIENT_ID,
        product_api_url=WORX_PRODUCT_API_URL,
        scope=WORX_SCOPE
    )
    if not cloud_client.login(WORX_EMAIL, WORX_PASSWORD):
        logger.error("Login fehlgeschlagen. Skript wird beendet.")
        return

    products = cloud_client.get_products()
    if not products:
        logger.error("Keine Produkte (Mäher) gefunden oder Fehler beim Abrufen. Skript wird beendet.")
        return

    if not products: 
        logger.info("Keine Mäher mit diesem Konto verknüpft.")
        return

    selected_mower_info = None
    if len(products) == 1:
        selected_mower_info = products[0]
        logger.info(f"Ein Mäher gefunden: {selected_mower_info.get('name', 'Unbekannt')} (SN: {selected_mower_info.get('serial_number', 'N/A')})")
    else:
        logger.info("Mehrere Mäher gefunden. Bitte wähle einen aus:")
        for i, product in enumerate(products):
            logger.info(f"  {i+1}: {product.get('name', 'Unbekannt')} (SN: {product.get('serial_number', 'N/A')})")
        while True:
            try:
                choice = int(input("Gib die Nummer des Mähers ein: ")) - 1
                if 0 <= choice < len(products):
                    selected_mower_info = products[choice]
                    break
                else:
                    logger.warning("Ungültige Auswahl.")
            except ValueError:
                logger.warning("Bitte eine Zahl eingeben.")

    if not selected_mower_info:
        logger.error("Kein Mäher ausgewählt. Skript wird beendet.")
        return

    user_id_from_product = selected_mower_info.get("user_id")
    if user_id_from_product:
        cloud_client.user_id = str(user_id_from_product) 
        logger.info(f"Benutzer-ID aus Produktdaten extrahiert: {cloud_client.user_id}")
    else:
        logger.error("Konnte 'user_id' nicht in den Produktdaten des ausgewählten Mähers finden. Skript wird beendet.")
        return
    logger.info(f"Ausgewählter Mäher: {selected_mower_info.get('name')} - SN: {selected_mower_info.get('serial_number')}")
    logger.debug(f"Mäher Details: {json.dumps(selected_mower_info, indent=2)}")

    mqtt_broker_url = selected_mower_info.get("mqtt_endpoint")
    mqtt_broker_port = selected_mower_info.get("mqtt_port", 443) 

    if not mqtt_broker_url:
        logger.error("MQTT Broker URL nicht in Produktinformationen gefunden. Skript wird beendet.")
        return

    if not cloud_client._ensure_token_valid():
        logger.error("Konnte Access Token nicht validieren/erneuern. Skript wird beendet.")
        return

    landroid_mqtt = WorxLandroidMQTTClient(
        broker_url=mqtt_broker_url,
        broker_port=mqtt_broker_port,
        mqtt_api_prefix=WORX_MQTT_API_PREFIX,
        user_id=cloud_client.user_id,
        access_token=cloud_client.access_token,
        product_info=selected_mower_info
    )

    mqtt_thread = threading.Thread(target=landroid_mqtt.connect_and_loop, daemon=True)
    mqtt_thread.start()
    logger.debug(f"MQTT thread started. Is alive: {mqtt_thread.is_alive()}")

    try:
        while mqtt_thread.is_alive():
            time.sleep(1) 
    except KeyboardInterrupt:
        logger.info("Strg+C erkannt. Beende Skript...")
    finally:
        logger.info("Im finally-Block von main().") 
        landroid_mqtt.stop()
        if mqtt_thread.is_alive(): 
            mqtt_thread.join(timeout=5) 
        logger.info("Worx Landroid Direktkommunikations-Skript beendet.")


if __name__ == "__main__":
    import socket 
    main()
