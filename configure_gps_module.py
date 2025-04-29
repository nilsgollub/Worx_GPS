# configure_gps.py
import serial
import time
import logging
from config import REC_CONFIG  # Importiere Port/Baudrate aus der Hauptkonfiguration

# Versuche pyubx2 und pynmea2 zu importieren
try:
    from pyubx2 import UBXMessage, SET

    PYUBX2_AVAILABLE = True
except ImportError:
    PYUBX2_AVAILABLE = False

try:
    import pynmea2

    PYNMEA2_AVAILABLE = True
except ImportError:
    PYNMEA2_AVAILABLE = False

# Logging konfigurieren (einfaches Logging zur Konsole)
# Erhöhe das Level auf INFO für weniger detaillierte Ausgabe, DEBUG für alles
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- Konfigurationsparameter ---
SERIAL_PORT = REC_CONFIG["serial_port"]
BAUDRATE = REC_CONFIG["baudrate"]
WRITE_TIMEOUT = 60  # Sekunden Timeout für Schreibvorgänge
READ_TIMEOUT = 1  # Sekunden Timeout für Lesevorgänge
PAUSE_AFTER_SEND = 2.5  # Pause nach dem Senden eines Befehls
PAUSE_AFTER_RESET = 4.0  # Längere Pause nach einem Reset
VERIFICATION_DURATION = 10  # Sekunden, um auf GGA-Daten nach der Konfig zu warten


# --- Hilfsfunktion zum Senden ---
def send_ubx_command(ser, msg):
    """Sendet eine UBX-Nachricht und wartet."""
    if not PYUBX2_AVAILABLE:
        logger.error("pyubx2 nicht verfügbar. Kann Befehl nicht senden.")
        return False
    if not ser or not ser.is_open:
        logger.error("Serielle Verbindung nicht offen. Kann Befehl nicht senden.")
        return False

    try:
        logger.debug(f"Sende UBX Befehl: {msg}")
        ser.reset_output_buffer()  # Sendepuffer leeren
        start_write = time.monotonic()
        ser.write(msg.serialize())
        # Warte nach dem Senden
        logger.debug(f"Warte {PAUSE_AFTER_SEND}s nach dem Senden...")
        time.sleep(PAUSE_AFTER_SEND)
        duration = time.monotonic() - start_write
        logger.info(f"Befehl {msg.identity} gesendet (dauerte {duration:.2f}s).")
        # Optional: Hier könnte man auf ACK/NAK warten
        return True
    except serial.SerialTimeoutException:
        duration_timeout = time.monotonic() - start_write
        logger.error(f"Timeout ({ser.write_timeout}s) beim Senden von {msg.identity} nach {duration_timeout:.2f}s.")
        return False
    except serial.SerialException as e:
        logger.error(f"Serieller Fehler beim Senden von {msg.identity}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Senden von {msg.identity}: {e}", exc_info=True)
        return False


# --- Hauptkonfigurationsfunktion ---
def configure_gps_module(ser):
    """Führt die Konfigurationssequenz auf dem GPS-Modul aus."""
    if not PYUBX2_AVAILABLE:
        logger.critical("pyubx2 ist nicht installiert. Konfiguration nicht möglich.")
        return False

    config_ok = True
    save_needed = False

    # --- 1. Kaltstart (CFG-RST) ---
    logger.info("--- Schritt 1: Kaltstart (CFG-RST) ---")
    try:
        nav_bbr_mask = 0xFFFF  # Cold start
        reset_mode = 0x02  # Controlled Software reset (GNSS only)
        payload_rst = nav_bbr_mask.to_bytes(2, 'little') + reset_mode.to_bytes(1, 'little') + b'\x00'
        msg_rst = UBXMessage('CFG', 'CFG-RST', SET, payload=payload_rst)
        if send_ubx_command(ser, msg_rst):
            logger.info("CFG-RST: Kaltstart-Befehl gesendet. Warte auf Neustart...")
            time.sleep(PAUSE_AFTER_RESET)
        else:
            logger.error("Fehler beim Senden von CFG-RST. Breche Konfiguration ab.")
            return False  # Abbruch bei Reset-Fehler sinnvoll
    except Exception as e:
        logger.error(f"Fehler beim Erstellen von CFG-RST: {e}", exc_info=True)
        return False

    # --- 2. NMEA Nachrichten konfigurieren (CFG-MSG) ---
    logger.info("--- Schritt 2: NMEA Nachrichten (CFG-MSG) ---")
    # --- Korrektur: GGA, GSA, RMC, VTG, GSV aktivieren (Rate 1), GLL deaktivieren (Rate 0) ---
    nmea_msgs_to_configure = {
        0xF0: {  # NMEA Standard Class
            0x00: 1,  # GGA: Rate 1
            0x02: 1,  # GSA: Rate 1
            0x04: 1,  # RMC: Rate 1
            0x05: 1,  # VTG: Rate 1
            0x03: 1,  # GSV: Rate 1
            0x01: 0  # GLL: Rate 0 (Bleibt oft deaktiviert)
        }
    }
    # --- Ende Korrektur ---
    try:
        for msgClass, ids_rates in nmea_msgs_to_configure.items():
            for msgID, rate in ids_rates.items():
                rates = [0] * 6
                rates[1] = rate  # Index 1 ist UART1
                payload_msg = bytes([msgClass, msgID]) + bytes(rates)
                msg_cfg = UBXMessage('CFG', 'CFG-MSG', SET, payload=payload_msg)
                if send_ubx_command(ser, msg_cfg):
                    # Log angepasst für Klarheit
                    action = f"aktiviert (Rate {rate})" if rate > 0 else "deaktiviert"
                    logger.info(f"CFG-MSG: NMEA {msgClass:02X}-{msgID:02X} {action}.")
                    save_needed = True
                else:
                    logger.error(f"Fehler beim Setzen von CFG-MSG {msgClass:02X}-{msgID:02X}.")
                    config_ok = False
    except Exception as e:
        logger.error(f"Fehler beim Erstellen von CFG-MSG: {e}", exc_info=True)
        config_ok = False

    # --- 3. Port-Konfiguration (CFG-PRT) ---
    if config_ok:  # Nur wenn bisher alles ok war
        logger.info("--- Schritt 3: Port Konfiguration (CFG-PRT) ---")
        try:
            portID = 1  # UART1
            mode = 0x08D0  # 8N1 (8 Datenbits, No Parity, 1 Stopbit)
            baudRate = 9600  # Sicherstellen, dass es 9600 ist
            inProtoMask = 0x02  # 0x01=UBX, 0x02=NMEA, 0x04=RTCM -> Nur NMEA In
            outProtoMask = 0x02  # Nur NMEA Out
            payload_prt = portID.to_bytes(1, 'little') + b'\x00' + b'\x00\x00' + \
                          mode.to_bytes(4, 'little') + baudRate.to_bytes(4, 'little') + \
                          inProtoMask.to_bytes(2, 'little') + outProtoMask.to_bytes(2, 'little') + \
                          b'\x00\x00' + b'\x00\x00'  # flags + reserved
            msg_prt = UBXMessage('CFG', 'CFG-PRT', SET, payload=payload_prt)
            if send_ubx_command(ser, msg_prt):
                logger.info(f"CFG-PRT: UART1 auf {baudRate} Baud, 8N1, NMEA In/Out gesetzt.")
                save_needed = True
            else:
                logger.error("Fehler beim Setzen von CFG-PRT.")
                config_ok = False
        except Exception as e:
            logger.error(f"Fehler beim Erstellen von CFG-PRT: {e}", exc_info=True)
            config_ok = False

    # --- 4. Speichern (CFG-CFG) ---
    if save_needed and config_ok:
        logger.info("--- Schritt 4: Konfiguration speichern (CFG-CFG) ---")
        try:
            clear_mask = 0x0000
            save_mask = 0x0007  # Save IO Port, Message, INF Message config
            load_mask = 0x0000
            dev_mask = 0x04  # Save to BBR only (Battery Backed RAM)
            payload_save = clear_mask.to_bytes(4, 'little') + save_mask.to_bytes(4, 'little') + \
                           load_mask.to_bytes(4, 'little') + dev_mask.to_bytes(1, 'little') + b'\x00' * 3
            msg_save = UBXMessage('CFG', 'CFG-CFG', SET, payload=payload_save)
            if send_ubx_command(ser, msg_save):
                logger.info("CFG-CFG: Speicherbefehl erfolgreich gesendet.")
                # Wichtig: Das Modul braucht etwas Zeit zum Speichern. Die Pause in send_ubx_command hilft.
            else:
                logger.error("Fehler beim Senden des Speicherbefehls (CFG-CFG).")
                config_ok = False
        except Exception as e:
            logger.error(f"Fehler beim Erstellen von CFG-CFG: {e}", exc_info=True)
            config_ok = False
    elif not config_ok:
        logger.warning("Konfiguration wird nicht gespeichert, da Fehler aufgetreten sind.")
    else:
        logger.info("Keine Änderungen zum Speichern (oder Fehler).")

    logger.info("--- U-Blox Konfigurationssequenz beendet ---")
    return config_ok


# --- Funktion zur Überprüfung der NMEA-Ausgabe ---
def verify_nmea_output(ser):
    """
    Versucht nach der Konfiguration für eine bestimmte Zeit NMEA-Daten zu lesen
    und prüft, ob gültige GGA-Sätze empfangen werden.
    """
    if not PYNMEA2_AVAILABLE:
        logger.warning("pynmea2 nicht verfügbar. NMEA-Verifizierung übersprungen.")
        return True  # Überspringen gilt als "kein Fehler"

    logger.info(f"--- Schritt 5: Überprüfe NMEA GGA Ausgabe für {VERIFICATION_DURATION} Sekunden ---")
    start_time = time.monotonic()
    gga_verified = False
    lines_read = 0

    # Eingangspuffer leeren, bevor wir mit dem Lesen beginnen
    try:
        ser.reset_input_buffer()
        logger.debug("Seriellen Eingangspuffer vor Verifizierung geleert.")
    except Exception as e:
        logger.warning(f"Fehler beim Leeren des Eingangspuffers vor Verifizierung: {e}")

    while time.monotonic() - start_time < VERIFICATION_DURATION:
        try:
            if ser.in_waiting > 0:  # Nur lesen, wenn Daten verfügbar sind
                line_bytes = ser.readline()
                if not line_bytes:
                    # Sollte bei in_waiting > 0 nicht passieren, aber sicher ist sicher
                    time.sleep(0.05)
                    continue

                lines_read += 1
                try:
                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    # --- Zeile immer mit INFO loggen ---
                    logger.info(f"Empfangen: {line}")
                    # --- Ende ---

                    # Prüfe auf GGA (kann $GPGGA, $GNGGA, etc. sein)
                    if line.startswith('$') and line[3:6] == 'GGA':
                        # logger.info(f"GGA Satz gefunden: {line}") # Redundant, da oben schon geloggt
                        try:
                            # Versuche zu parsen, um Gültigkeit zu prüfen
                            pynmea2.parse(line)
                            logger.info("-> GGA Satz erfolgreich geparst!")  # Hervorhebung
                            gga_verified = True
                            break  # Erfolgreich verifiziert, Schleife beenden
                        except pynmea2.ParseError as pe:
                            logger.warning(f"-> GGA Satz gefunden, aber Parsing fehlgeschlagen: {pe}")
                            # Nicht abbrechen, vielleicht ist der nächste Satz gültig
                    # elif line.startswith('$'): # Optional: Andere NMEA auch loggen, wenn gewünscht
                    #     logger.info(f"Andere NMEA Nachricht: {line.split(',')[0]}")
                    # else: # Optional: Nicht-NMEA Zeilen loggen
                    #     if line:
                    #         logger.info(f"Keine NMEA Nachricht: {line[:50]}...")

                except UnicodeDecodeError:
                    logger.warning(f"Konnte empfangene Bytes nicht dekodieren: {line_bytes[:50]}...")
            else:
                # Keine Daten warten, kurz schlafen
                time.sleep(0.1)

        except serial.SerialException as e:
            logger.error(f"Serieller Fehler während der Verifizierung: {e}")
            return False  # Verifizierung fehlgeschlagen
        except Exception as e:
            logger.error(f"Unerwarteter Fehler während der Verifizierung: {e}", exc_info=True)
            return False  # Verifizierung fehlgeschlagen

    # --- Ergebnis der Verifizierung ---
    if gga_verified:
        logger.info(">>> NMEA GGA Ausgabe erfolgreich verifiziert! <<<")
        return True
    else:
        logger.error(f">>> FEHLER: Kein gültiger GGA Satz innerhalb von {VERIFICATION_DURATION}s empfangen. <<<")
        logger.error("         Mögliche Ursachen: Konfiguration fehlgeschlagen, falsche Baudrate, Verkabelungsproblem.")
        return False


# --- Hauptausführung ---
if __name__ == "__main__":
    logger.info(f"Starte U-Blox Konfigurationsskript für Port {SERIAL_PORT} @ {BAUDRATE} Baud")

    # Prüfe Abhängigkeiten
    if not PYUBX2_AVAILABLE:
        logger.critical("pyubx2 ist nicht installiert. Bitte installieren: pip install pyubx2")
        exit(1)
    # PYNMEA2 wird nur für die Verifizierung benötigt, also nur warnen
    if not PYNMEA2_AVAILABLE:
        logger.warning("pynmea2 ist nicht installiert. NMEA-Verifizierung wird übersprungen.")

    ser = None  # Initialisieren für finally Block
    overall_success = False  # Flag für Gesamterfolg

    try:
        # Serielle Verbindung öffnen
        logger.info("Öffne serielle Verbindung...")
        # Verwende die global definierten Timeouts
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=READ_TIMEOUT, write_timeout=WRITE_TIMEOUT)
        logger.info(f"Serielle Verbindung zu {ser.name} geöffnet.")

        # Konfiguration durchführen
        config_success = configure_gps_module(ser)

        # Verifizierung nur starten, wenn Konfiguration ok war
        verification_success = False
        if config_success:
            verification_success = verify_nmea_output(ser)
        else:
            logger.warning("Konfiguration war nicht erfolgreich, überspringe NMEA-Verifizierung.")

        # Gesamterfolg hängt von beiden Schritten ab (wenn Verifizierung durchgeführt wurde)
        overall_success = config_success and (
                verification_success or not PYNMEA2_AVAILABLE)  # Erfolg, wenn Konfig ok UND (Verifizierung ok ODER Verifizierung übersprungen)

        if overall_success:
            logger.info(">>> Gesamte Operation (Konfiguration + Verifizierung) erfolgreich abgeschlossen. <<<")
        else:
            logger.error(">>> Gesamte Operation (Konfiguration und/oder Verifizierung) NICHT erfolgreich. <<<")

    except serial.SerialException as e:
        logger.critical(f"Kritischer serieller Fehler: {e}", exc_info=True)
        logger.critical(
            "Stelle sicher, dass der Port korrekt ist, existiert und keine andere Anwendung ihn blockiert (z.B. Worx_GPS_Rec.py).")
    except Exception as e:
        logger.critical(f"Unerwarteter kritischer Fehler: {e}", exc_info=True)
    finally:
        # Serielle Verbindung sicher schließen
        if ser and ser.is_open:
            logger.info("Schließe serielle Verbindung.")
            ser.close()
        logger.info("Konfigurationsskript beendet.")
        # Exit-Code setzen basierend auf Erfolg
        exit(0 if overall_success else 1)
