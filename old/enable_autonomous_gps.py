# enable_autonomous_gps.py
import serial
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Konfiguration (Passe den Port an deine .env an)
SERIAL_PORT = "/dev/ttyACM0" # Oder /dev/ttyUSB0
BAUDRATE = 9600

def send_ubx_command(ser, payload):
    """Baut ein UBX-Paket zusammen und sendet es."""
    # Header: 0xB5 0x62
    header = b'\xb5\x62'
    # Checksumme berechnen (CK_A, CK_B)
    ck_a = 0
    ck_b = 0
    for byte in payload:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    
    packet = header + payload + bytes([ck_a, ck_b])
    ser.write(packet)
    logger.info(f"Gesendet: {packet.hex().upper()}")

def enable_assistnow_autonomous():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
        logger.info(f"Verbunden mit {SERIAL_PORT}")
        
        # UBX-CFG-NAVX5 Nachricht zur Aktivierung von AssistNow Autonomous
        # Class: 0x06, ID: 0x23, Length: 40 bytes
        # Wir müssen das bit 'aio' (AssistNow Autonomous) in den min/max/flags setzen.
        
        # Da wir den aktuellen Zustand nicht kennen, senden wir einen Standard-Block, 
        # der AssistNow Autonomous (AENA) aktiviert.
        
        # UBX-CFG-NAVX5 Payload (40 Bytes)
        # Wir setzen Bit 0 in den 'aopCfg' Flags (Offset 36-39)
        # Entnommen aus u-blox 7 Receiver Description Protocol Spec.
        
        # Vereinfachter Weg: Wir nutzen UBX-CFG-AOP (AssistNow Autonomous Configuration)
        # Class: 0x06, ID: 0x33, Length: 4 bytes
        # Payload: [0x01, 0x00, 0x00, 0x00] -> Enable (Bit 0 = 1)
        
        cfg_aop_payload = b'\x06\x33\x04\x00\x01\x00\x00\x00'
        
        logger.info("Aktiviere AssistNow Autonomous...")
        send_ubx_command(ser, cfg_aop_payload)
        
        # Ggf. auch die Daten-Speicherung im Flash-Speicher aktivieren (falls vorhanden)
        # UBX-CFG-CFG (Save current configuration to non-volatile memory)
        cfg_save_payload = b'\x06\x09\x0d\x00\x00\x00\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x01'
        logger.info("Speichere Konfiguration im NV-Memory...")
        send_ubx_command(ser, cfg_save_payload)
        
        time.sleep(1)
        ser.close()
        logger.info("Fertig. Das Modul lernt nun selbstständig Flugbahnen vorherzusagen.")
        
    except Exception as e:
        logger.error(f"Fehler: {e}")

if __name__ == "__main__":
    enable_assistnow_autonomous()
