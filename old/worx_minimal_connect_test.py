# worx_minimal_connect_test.py
import os
import ssl
import logging
import paho.mqtt.client as mqtt
import certifi # Stellt CA-Zertifikate bereit
import time
import socket # Für gethostbyname

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Konfiguration ---
BROKER_URL = "iot.eu-west-1.worxlandroid.com"
BROKER_PORT = 443
CLIENT_ID = "WorxMinimalTestClientPython" # Einfache, eindeutige Client-ID

# Dummy-Anmeldedaten - die Authentifizierung wird wahrscheinlich fehlschlagen,
# aber wir wollen sehen, ob der TCP/TLS-Handshake überhaupt beginnt.
MQTT_USER = "testuser"
MQTT_PASS = "testpassword"

# SSL Key Logging für Wireshark (optional, aber hilfreich, wenn Pakete fließen)
# Setze die Umgebungsvariable SSLKEYLOGFILE, z.B.:
# In PowerShell: $env:SSLKEYLOGFILE = "C:\temp\sslkeys_minimal.log"
keylog_filename = os.getenv("SSLKEYLOGFILE")

def on_connect(client, userdata, flags, reason_code, properties):
    # Diese Funktion wird nur aufgerufen, wenn ein CONNACK empfangen wird.
    logger.info(f"MINIMAL_TEST: on_connect aufgerufen mit Reason Code: {reason_code} ({mqtt.connack_string(reason_code if isinstance(reason_code, int) else -1 )})")
    if reason_code == 0:
        logger.info("MINIMAL_TEST: Erfolgreich mit Broker verbunden!")
        client.disconnect() # Für diesen Test direkt wieder trennen
    else:
        logger.error(f"MINIMAL_TEST: Verbindung fehlgeschlagen. Broker-Antwort-Code: {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    logger.info(f"MINIMAL_TEST: on_disconnect aufgerufen mit Reason Code: {reason_code} ({mqtt.connack_string(reason_code if isinstance(reason_code, int) else -1 )})")

def on_log(client, userdata, level, buf):
    # Gib alle Paho-Logs aus
    logger.info(f"MINIMAL_TEST_PAHO_LOG (Level {level}): {buf}")

# --- Hauptlogik ---
if __name__ == "__main__":
    logger.info("Starte minimalen Worx MQTT Verbindungstest...")

    try:
        broker_ip = socket.gethostbyname(BROKER_URL)
        logger.debug(f"MINIMAL_TEST: IP Adresse für {BROKER_URL} ist {broker_ip}")
    except socket.gaierror:
        logger.error(f"MINIMAL_TEST: Konnte IP für {BROKER_URL} nicht auflösen. Test wird abgebrochen.")
        exit()

    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_log = on_log

    logger.info(f"MINIMAL_TEST: Konfiguriere TLS für {BROKER_URL}:{BROKER_PORT}")
    try:
        client.tls_set(
            ca_certs=certifi.where(), # Verwende CA-Bundle von certifi
            tls_version=ssl.PROTOCOL_TLS_CLIENT # Moderne Standardeinstellung
        )
        logger.debug(f"MINIMAL_TEST: MQTT TLS konfiguriert mit certifi CA: {certifi.where()}")

        if keylog_filename and hasattr(client, '_ssl_context') and client._ssl_context:
            client._ssl_context.keylog_filename = keylog_filename
            logger.info(f"MINIMAL_TEST: SSL Key Logging aktiviert für: '{keylog_filename}'")
        elif keylog_filename:
            logger.warning("MINIMAL_TEST: SSLKEYLOGFILE gesetzt, aber _ssl_context nicht gefunden. Key Logging evtl. nicht aktiv.")
        
        # Temporär für diesen Test die Zertifikatsverifizierung deaktivieren,
        # um sicherzustellen, dass es nicht daran scheitert.
        client.tls_insecure_set(True)
        logger.warning("!!! MINIMAL_TEST: MQTT TLS-Verifizierung für Diagnosezwecke DEAKTIVIERT !!!")

    except Exception as e_tls:
        logger.error(f"MINIMAL_TEST: Fehler bei der TLS-Konfiguration: {e_tls}", exc_info=True)
        exit()
    
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    logger.debug("MINIMAL_TEST: Dummy MQTT Username/Passwort gesetzt.")

    logger.info(f"MINIMAL_TEST: Versuche Verbindung (blocking connect) zu {BROKER_URL} ({broker_ip}):{BROKER_PORT}")
    
    try:
        # Verwende den blockierenden connect-Aufruf
        rc = client.connect(BROKER_URL, BROKER_PORT, keepalive=60)
        logger.info(f"MINIMAL_TEST: client.connect() Aufruf beendet mit Rückgabewert: {rc} ({mqtt.error_string(rc if isinstance(rc, int) else -1 )})")

        # Wenn connect() 0 zurückgibt, sollte on_connect aufgerufen worden sein.
        # Wir starten den Loop, um Callbacks zu verarbeiten und PINGs zu ermöglichen, falls die Verbindung steht.
        if rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info("MINIMAL_TEST: connect() meldet Erfolg. Starte Loop für Callback-Verarbeitung und Keep-Alive.")
            client.loop_start()
            # Warte, um zu sehen, ob die Verbindung bestehen bleibt oder on_connect/on_disconnect aufgerufen wird.
            # 70 Sekunden, um einen Keep-Alive-Zyklus zu ermöglichen.
            time.sleep(70) 
            client.loop_stop()
        else:
            logger.error("MINIMAL_TEST: connect() meldet einen Fehler. Überprüfe den Rückgabewert und Paho-Logs.")

    except ssl.SSLCertVerificationError as e_ssl_verify:
        logger.error(f"MINIMAL_TEST: SSL Zertifikatsverifizierungsfehler: {e_ssl_verify}", exc_info=True)
    except ssl.SSLError as e_ssl:
        logger.error(f"MINIMAL_TEST: Allgemeiner SSL-Fehler: {e_ssl}", exc_info=True)
    except ConnectionRefusedError:
        logger.error(f"MINIMAL_TEST: Verbindung abgelehnt (ConnectionRefusedError).")
    except socket.timeout:
        logger.error(f"MINIMAL_TEST: Timeout beim Verbindungsversuch.")
    except OSError as e_os:
        logger.error(f"MINIMAL_TEST: OS-Fehler (z.B. keine Route, Netzwerk nicht erreichbar): {e_os}")
    except Exception as e:
        logger.error(f"MINIMAL_TEST: Ein unerwarteter Fehler ist beim Verbinden oder im Loop aufgetreten: {e}", exc_info=True)
    finally:
        logger.info("MINIMAL_TEST: Trenne Verbindung und beende Test.")
        client.disconnect() # Stellt sicher, dass disconnect aufgerufen wird
        logger.info("MINIMAL_TEST: Beendet.")
