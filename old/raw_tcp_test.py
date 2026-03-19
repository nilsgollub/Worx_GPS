# raw_tcp_test.py
import socket
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Nimm die IP-Adresse, die dein minimales Paho-Skript zuletzt geloggt hat
# z.B. 54.72.93.222 (aus deinem letzten Log)
TARGET_IP = "54.72.93.222" # ERSETZE DIES MIT DER AKTUELLEN IP!
TARGET_PORT = 443 # Wir versuchen immer noch Port 443, auch wenn wir kein TLS sprechen

logger.info(f"RAW_TCP_TEST: Versuche, eine TCP-Verbindung zu {TARGET_IP}:{TARGET_PORT} herzustellen...")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10) # Timeout von 10 Sekunden

    logger.debug(f"RAW_TCP_TEST: Socket erstellt. Versuche connect()...")
    sock.connect((TARGET_IP, TARGET_PORT)) # Dieser Aufruf ist blockierend

    logger.info(f"RAW_TCP_TEST: TCP-Verbindung zu {TARGET_IP}:{TARGET_PORT} erfolgreich hergestellt!")
    # Da wir kein TLS sprechen, wird der Server die Verbindung wahrscheinlich schnell schließen
    # oder unsinnige Daten senden, wenn wir versuchen zu lesen/schreiben.
    # Für diesen Test reicht es, wenn connect() nicht fehlschlägt.

except socket.timeout:
    logger.error(f"RAW_TCP_TEST: Timeout beim Verbindungsversuch zu {TARGET_IP}:{TARGET_PORT}.")
except ConnectionRefusedError:
    logger.error(f"RAW_TCP_TEST: Verbindung zu {TARGET_IP}:{TARGET_PORT} wurde abgelehnt (Connection refused).")
except OSError as e:
    logger.error(f"RAW_TCP_TEST: Ein OS-Fehler ist aufgetreten (z.B. keine Route zum Host, Firewall blockiert): {e}")
except Exception as e:
    logger.error(f"RAW_TCP_TEST: Ein unerwarteter Fehler ist aufgetreten: {e}", exc_info=True)
finally:
    if 'sock' in locals() and sock:
        logger.debug("RAW_TCP_TEST: Schließe Socket.")
        sock.close()
    logger.info("RAW_TCP_TEST: Beendet.")

