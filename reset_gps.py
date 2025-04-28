# reset_gps.py
import serial
import time
import logging
import os
from dotenv import load_dotenv

# --- NEU: Importiere pyubx2 ---
try:
    from pyubx2 import UBXMessage, SET, POLL, UBX_CONFIG_DATABASE, protocol

    PYUBX2_AVAILABLE = True
except ImportError:
    PYUBX2_AVAILABLE = False
    print("FEHLER: pyubx2 ist nicht installiert. Bitte installieren: pip install pyubx2")
    exit(1)
# --- ENDE NEU ---

# Lade Konfiguration aus .env Datei (optional, aber praktisch)
load_dotenv()

# --- Konfiguration ---
# Hole Port und Baudrate aus Umgebungsvariablen oder setze Standardwerte
SERIAL_PORT = os.getenv("GPS_SERIAL_PORT", "/dev/ttyACM0")  # Passe den Standardport ggf. an
BAUDRATE = int(os.getenv("GPS_BAUDRATE", "9600"))
WRITE_TIMEOUT = 10  # Timeout für Schreibvorgänge in Sekunden
READ_TIMEOUT = 1  # Timeout für Lesevorgänge (falls benötigt)
# --- Ende Konfiguration ---

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def send_ubx_command(ser, ubx_msg):
    """
    Sendet einen UBX-Befehl an das geöffnete serielle Gerät und wartet kurz.

    Args:
        ser (serial.Serial): Das geöffnete Serial-Objekt.
        ubx_msg (UBXMessage): Die zu sendende pyubx2 UBXMessage.

    Returns:
        bool: True bei Erfolg, False bei Fehler.
    """
    if not ser or not ser.is_open:
        logger.error("Serielle Verbindung ist nicht offen.")
        return False

    try:
        logger.debug(f"Sende UBX Befehl: {ubx_msg}")
        ser.reset_output_buffer()  # Ausgangspuffer leeren
        ser.write(ubx_msg.serialize())
        time.sleep(1.0)  # Kurze Pause nach dem Senden geben
        # Optional: Hier könnte man auf ein ACK warten, wenn nötig
        logger.info(f"Befehl {ubx_msg.identity} erfolgreich gesendet.")
        return True
    except serial.SerialTimeoutException:
        logger.error(f"Timeout ({ser.write_timeout}s) beim Senden des UBX Befehls {ubx_msg.identity}.")
        return False
    except serial.SerialException as e:
        logger.error(f"Serieller Fehler beim Senden des UBX Befehls {ubx_msg.identity}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Senden des UBX Befehls {ubx_msg.identity}: {e}", exc_info=True)
        return False


def reset_gps_to_defaults(port, baud):
    """
    Stellt eine Verbindung zum GPS-Modul her und sendet den Befehl
    zum Zurücksetzen auf die Werkseinstellungen.
    """
    if not PYUBX2_AVAILABLE:
        logger.critical("pyubx2 nicht verfügbar. Abbruch.")
        return

    logger.warning(f"Versuche, GPS-Modul an {port} auf Werkseinstellungen zurückzusetzen...")

    ser = None  # Initialisieren für finally Block
    try:
        # Serielle Verbindung öffnen
        logger.info(f"Öffne serielle Verbindung zu {port} mit Baudrate {baud}...")
        ser = serial.Serial(port, baud, timeout=READ_TIMEOUT, write_timeout=WRITE_TIMEOUT)
        logger.info(f"Serielle Verbindung zu {ser.name} erfolgreich geöffnet.")

        # CFG-CFG Befehl zum Laden der Standardkonfiguration erstellen
        # clearMask = 0x0000 (nichts löschen)
        # saveMask = 0x0000 (nichts speichern)
        # loadMask = 0x0001 (Default-Konfiguration laden)
        # deviceMask: Welche Geräte betroffen sind (0x07 = BBR, Flash, EEPROM - sicherheitshalber alle)
        clear_mask = 0x0000
        save_mask = 0x0000
        load_mask = 0x0001  # Wichtig: Lädt die Default-Konfiguration
        dev_mask = 0x07  # BBR, Flash, EEPROM

        # Payload korrekt zusammenbauen (13 Bytes für CFG-CFG SET)
        # clearMask(4) + saveMask(4) + loadMask(4) + deviceMask(1) + padding(3)
        payload_reset = clear_mask.to_bytes(4, 'little') + \
                        save_mask.to_bytes(4, 'little') + \
                        load_mask.to_bytes(4, 'little') + \
                        dev_mask.to_bytes(1, 'little') + b'\x00' * 3  # Padding für deviceMask

        msg_reset = UBXMessage('CFG', 'CFG-CFG', SET, payload=payload_reset)

        # Befehl senden
        if send_ubx_command(ser, msg_reset):
            logger.info("Befehl zum Laden der Werkseinstellungen erfolgreich gesendet.")
            logger.warning("Das GPS-Modul wurde angewiesen, die Werkseinstellungen zu laden.")
            logger.warning("Es wird dringend empfohlen, das Modul neu zu starten oder die Verbindung")
            logger.warning("neu aufzubauen, damit die Änderungen wirksam werden.")
            logger.warning(
                "Möglicherweise muss die Baudrate nach dem Reset angepasst werden, falls sie geändert wurde.")
        else:
            logger.error("Fehler beim Senden des Reset-Befehls.")

    except serial.SerialException as ser_e:
        logger.error(f"Serieller Fehler beim Zugriff auf {port}: {ser_e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {e}", exc_info=True)
    finally:
        # Serielle Verbindung immer schließen
        if ser and ser.is_open:
            ser.close()
            logger.info(f"Serielle Verbindung zu {ser.name} geschlossen.")


if __name__ == "__main__":
    logger.info("Starte GPS Reset Skript...")
    reset_gps_to_defaults(SERIAL_PORT, BAUDRATE)
    logger.info("GPS Reset Skript beendet.")
