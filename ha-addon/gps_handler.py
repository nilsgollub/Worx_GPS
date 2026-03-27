# gps_handler.py
import logging
import random
import time
import serial
import pynmea2
import platform
from datetime import datetime
from config import GEO_CONFIG, REC_CONFIG, GPS_CONFIG
import math



# Hole den Logger, anstatt basicConfig hier aufzurufen
logger = logging.getLogger(__name__)


class GpsHandler:
    def __init__(self):
        self.lat_bounds = GEO_CONFIG["lat_bounds"]
        self.lon_bounds = GEO_CONFIG["lon_bounds"]
        self.map_center = GEO_CONFIG["map_center"]
        self.serial_port = REC_CONFIG["serial_port"]
        self.baudrate = REC_CONFIG["baudrate"]
        self.ser_gps = None
        self.mode = "real"

        self._connect_serial()
        if self.mode == "real":
            self._configure_ublox_pedestrian()
            self._configure_gnss_mode()  # SBAS oder GLONASS je nach Konfiguration
            self._configure_ublox_autonomous()

        # AssistNow Autonomous (AOP) läuft on-chip, kein Server nötig
        self.assist_now_enabled = False
        
        self.is_fake_gps = False
        self.route_simulator = None
        self.last_valid_fix_time = 0
        self.last_known_position = None
        self.last_gga_info = {'qual': -1 if self.mode == "real" else 0, 'sats': 0, 'timestamp': time.time()}
        logger.info("GpsHandler initialisiert.")

    def _connect_serial(self):
        """Versucht, die serielle Verbindung herzustellen oder wiederherzustellen."""
        if self.ser_gps and self.ser_gps.is_open:
            try:
                self.ser_gps.close()
                logger.info("Bestehende serielle Verbindung geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen der bestehenden seriellen Verbindung: {e}")
            self.ser_gps = None

        if self.mode == "real":
            try:
                logger.info(
                    f"Versuche, serielle Verbindung zu {self.serial_port} mit Baudrate {self.baudrate} herzustellen...")
                # --- write_timeout bleibt sinnvoll für AssistNow ---
                self.ser_gps = serial.Serial(
                    self.serial_port,
                    self.baudrate,
                    timeout=1,  # Read timeout
                    write_timeout=60  # Write timeout
                )
                logger.info(f"Serielle Verbindung zu {self.ser_gps.name} erfolgreich hergestellt.")

                # --- Status auf -1 (Connecting) setzen, bis der erste GGA kommt ---
                # Wird jetzt in __init__ gesetzt und hier ggf. zurückgesetzt
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}



            except serial.SerialException as ser_e:
                logger.error(f"Serieller Fehler beim Herstellen der Verbindung zu {self.serial_port}: {ser_e}",
                             exc_info=True)
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung zu {self.serial_port}: {e}",
                             exc_info=True)
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
        else:
            logger.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
            self.ser_gps = None
            self.last_gga_info = {'qual': 1, 'sats': 8, 'timestamp': time.time()}  # Fake GPS hat sofort Fix

    def _configure_ublox_pedestrian(self):
        """Konfiguriert das Modul für den Pedestrian-Modus (optimiert für langsame Bewegungen)."""
        if self.ser_gps is None or not self.ser_gps.is_open:
            return

        logger.info("Konfiguriere u-blox Modul (Pedestrian-Modus & Elevation 10°)...")
        # UBX-CFG-NAV5 (Navigation Engine Settings)
        # Class: 0x06, ID: 0x24, Length: 36
        # Mask: 0x0011 (DynModel & MinElev bit 0 & 4)
        # DynModel: 3 (Pedestrian)
        # MinElev: 10
        payload = (
            b'\x06\x24\x24\x00'  # Header + Length (36)
            b'\x11\x00'          # Mask (bit 0 & 4)
            b'\x03'              # DynModel (3 = Pedestrian)
            b'\x00'              # FixMode (Auto)
            b'\x00\x00\x00\x00'  # FixedAlt
            b'\x00\x00\x00\x00'  # FixedAltVar
            b'\x0a'              # MinElev (10 Grad)
            b'\x00'              # DrLimit
            b'\x00\x00'          # pDop
            b'\x00\x00'          # tDop
            b'\x00\x00'          # pAcc
            b'\x00\x00'          # tAcc
            b'\x00'              # staticHoldThresh
            b'\x00'              # dgpsTimeOut
            b'\x00' * 12         # Reserved
        )
        self._send_ubx_command(payload)

    def _configure_ublox_sbas(self):
        """Aktiviert SBAS (EGNOS in Europa) für verbesserte Genauigkeit (~1-2m).
        HINWEIS: Auf dem NEO-7M deaktiviert SBAS effektiv GLONASS!"""
        if self.ser_gps is None or not self.ser_gps.is_open:
            return

        logger.info("Aktiviere SBAS/EGNOS (GPS+SBAS Modus)...")
        # UBX-CFG-SBAS: Class 0x06, ID 0x16, Length 8
        # mode: 0x01 (Enabled)
        # usage: 0x07 (Range + DiffCorr + Integrity)
        # maxSBAS: 3 (max 3 SBAS-Satelliten gleichzeitig)
        # scanmode2: 0x00
        # scanmode1: 0x00006200 (PRN 120, 121, 123, 126 = EGNOS Europa)
        payload = (
            b'\x06\x16\x08\x00'  # Header + Length (8)
            b'\x01'              # mode: Enabled
            b'\x07'              # usage: Range + DiffCorr + Integrity
            b'\x03'              # maxSBAS: 3
            b'\x00'              # scanmode2
            b'\x00\x62\x00\x00' # scanmode1: EGNOS PRNs (120,121,123,126)
        )
        self._send_ubx_command(payload)

    def _configure_ublox_glonass(self):
        """Deaktiviert SBAS und aktiviert GPS+GLONASS.
        Auf dem NEO-7M bringt GLONASS ~6 zusätzliche Satelliten → bessere Geometrie.
        Vorteil bei gutem Himmel: mehr Satelliten > SBAS-Korrektur."""
        if self.ser_gps is None or not self.ser_gps.is_open:
            return

        logger.info("Deaktiviere SBAS, nutze GPS+GLONASS Modus...")
        # 1. SBAS deaktivieren
        payload_sbas_off = (
            b'\x06\x16\x08\x00'  # Header + Length (8)
            b'\x00'              # mode: Disabled
            b'\x00'              # usage: None
            b'\x00'              # maxSBAS: 0
            b'\x00'              # scanmode2
            b'\x00\x00\x00\x00' # scanmode1: None
        )
        self._send_ubx_command(payload_sbas_off)

        # 2. GLONASS aktivieren via UBX-CFG-GNSS
        # NEO-7M: GPS (gnssId=0) + GLONASS (gnssId=6)
        # Class 0x06, ID 0x3E
        # numTrkChHw=32, numTrkChUse=32, numConfigBlocks=2
        payload_gnss = (
            b'\x06\x3E\x0C\x00'  # Header + Length (12 = 4 header + 2*4 blocks)
            b'\x00'              # msgVer: 0
            b'\x20'              # numTrkChHw: 32
            b'\x20'              # numTrkChUse: 32
            b'\x02'              # numConfigBlocks: 2
            # Block 1: GPS
            b'\x00'              # gnssId: 0 (GPS)
            b'\x08'              # resTrkCh: 8
            b'\x10'              # maxTrkCh: 16
            b'\x01'              # flags: enabled
            # Block 2: GLONASS  
            b'\x06'              # gnssId: 6 (GLONASS)
            b'\x08'              # resTrkCh: 8
            b'\x0E'              # maxTrkCh: 14
            b'\x01'              # flags: enabled
        )
        self._send_ubx_command(payload_gnss)

    def _configure_gnss_mode(self):
        """Konfiguriert SBAS oder GLONASS basierend auf der GPS_CONFIG Einstellung."""
        gnss_mode = GPS_CONFIG.get('gnss_mode', 'sbas')
        logger.info(f"GNSS-Modus: '{gnss_mode}'")
        
        if gnss_mode == 'glonass':
            self._configure_ublox_glonass()
        else:
            self._configure_ublox_sbas()

    def _configure_ublox_autonomous(self):
        """Aktiviert AssistNow Autonomous (AOP) auf dem u-blox Modul."""
        if self.ser_gps is None or not self.ser_gps.is_open:
            return

        logger.info("Aktiviere AssistNow Autonomous (AOP)...")
        # UBX-CFG-AOP: Class 0x06, ID 0x33, Length 4
        # Payload: [0x01, 0x00, 0x00, 0x00] -> Enable (Bit 0 = 1)
        cfg_aop_payload = b'\x06\x33\x04\x00\x01\x00\x00\x00'
        self._send_ubx_command(cfg_aop_payload)
        
        # Konfiguration dauerhaft speichern (UBX-CFG-CFG)
        cfg_save_payload = b'\x06\x09\x0d\x00\x00\x00\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x01'
        self._send_ubx_command(cfg_save_payload)

    def _send_ubx_command(self, payload):
        """Baut ein UBX-Paket zusammen und sendet es."""
        if self.ser_gps is None or not self.ser_gps.is_open:
            return

        header = b'\xb5\x62'
        ck_a = 0
        ck_b = 0
        for byte in payload:
            ck_a = (ck_a + byte) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        
        packet = header + payload + bytes([ck_a, ck_b])
        try:
            self.ser_gps.write(packet)
            self.ser_gps.flush()
            logger.debug(f"UBX Command gesendet: {packet.hex().upper()}")
        except Exception as e:
            logger.error(f"Fehler beim Senden des UBX Commands: {e}")

    def _reconnect_serial(self):
        """Wrapper für _connect_serial für den Einsatz bei Fehlern."""
        logger.info("Versuche, serielle Verbindung wiederherzustellen...")
        # _connect_serial ruft KEINE Konfiguration mehr auf
        self._connect_serial()

    def close_serial(self):
        """Schließt die serielle Verbindung sicher."""
        if self.ser_gps and self.ser_gps.is_open:
            try:
                self.ser_gps.close()
                logger.info("Serielle GPS-Verbindung geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen der seriellen Verbindung: {e}")
        self.ser_gps = None

    # --- Methode _send_ubx_config entfernt ---

    # --- Methode _configure_ublox entfernt ---

    # --- RouteSimulator Klasse bleibt ---
    class RouteSimulator:
        def __init__(self, start_lat, start_lon, speed=0.00001, direction=0):
            self.current_lat = start_lat
            self.current_lon = start_lon
            self.speed = speed
            self.direction = direction

        def move(self):
            self.current_lat += self.speed * math.cos(math.radians(self.direction))
            self.current_lon += self.speed * math.sin(math.radians(self.direction))
            return self.current_lat, self.current_lon

        def change_direction(self, angle_change):
            self.direction = (self.direction + angle_change) % 360

    # --- is_inside_boundaries bleibt ---
    def is_inside_boundaries(self, lat, lon):
        return (self.lat_bounds[0] <= lat <= self.lat_bounds[1] and
                self.lon_bounds[0] <= lon <= self.lon_bounds[1])

    def download_assist_now_data(self):
        """Nicht mehr benötigt — AOP läuft on-chip."""
        return None

    def send_assist_now_data(self, data):
        """Nicht mehr benötigt — AOP läuft on-chip."""
        return False

    # --- get_gps_data bleibt im Wesentlichen gleich ---
    def get_gps_data(self):
        """
        Liest und parst NMEA-Nachrichten. Versucht, innerhalb eines Timeouts einen GGA-Satz zu finden.
        Gibt Positionsdaten nur bei gültigem Fix zurück.
        Aktualisiert IMMER self.last_gga_info und self.last_known_position (bei gültigem Fix).
        """
        # --- Fake-Modi ---
        if self.mode == "fake_random":
            fake_pos = self.generate_fake_data()
            self.last_gga_info = {'qual': 1, 'sats': fake_pos.get('satellites', 8),
                                  'timestamp': fake_pos.get('timestamp', time.time())}
            self.last_known_position = fake_pos
            logger.debug(f"Fake Random Data: {fake_pos}")
            return fake_pos
        elif self.mode == "fake_route":
            fake_pos = self.generate_fake_route_data()
            self.last_gga_info = {'qual': 1, 'sats': fake_pos.get('satellites', 8),
                                  'timestamp': fake_pos.get('timestamp', time.time())}
            self.last_known_position = fake_pos
            logger.debug(f"Fake Route Data: {fake_pos}")
            return fake_pos

        # --- Real-Modus ---
        elif self.mode == "real":
            connection_ok = True
            if self.ser_gps is None:
                logger.warning("GPS-Verbindung ist None in get_gps_data.")
                connection_ok = False
            elif not self.ser_gps.is_open:
                logger.warning(f"GPS-Verbindung {self.ser_gps.name} ist nicht offen in get_gps_data.")
                connection_ok = False

            if not connection_ok:
                logger.info("-> get_gps_data löst _reconnect_serial aus.")
                self._reconnect_serial()
                # Setze Status auf Connecting, falls nicht schon
                if self.last_gga_info.get('qual') != -1:
                    self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
                return None

            try:
                # logger.debug("Leere seriellen Eingangspuffer...") # Kann evtl. Probleme machen, erstmal raus
                # self.ser_gps.reset_input_buffer()
                pass  # Platzhalter
            except Exception as e:
                logger.error(f"Fehler beim Leeren des Eingangspuffers: {e}")

            start_time = time.monotonic()
            read_timeout = 0.9
            gga_msg = None

            while time.monotonic() - start_time < read_timeout:
                try:
                    line_bytes = self.ser_gps.readline()
                    if not line_bytes:
                        # logger.debug("Keine Daten von serieller Schnittstelle gelesen (readline Timeout).") # Zu viel Logspam
                        time.sleep(0.05)
                        continue

                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    # logger.debug(f"Serielle Zeile empfangen: '{line[:80]}...'") # Zu viel Logspam

                    if line.startswith('$'):
                        try:
                            # Basis-Prüfung: Hat die Zeile überhaupt nützliche Felder?
                            # Zeilen wie '$GPGL,,,,,*4', '$GPRMC,,V,,,,,,,,*3' oder '$PRM,61.0V,,,102,,*7' überspringen
                            parts = line.split(',')
                            if len(parts) > 2:
                                talker = parts[0].upper()
                                status_field = ""
                                if "RMC" in talker or "GLL" in talker:
                                    status_field = parts[2] # RMC/GLL haben Status an Pos 2
                                elif "GGA" in talker:
                                    status_field = parts[6] if len(parts) > 6 else "" # GGA hat Qual an Pos 6
                                
                                # Wenn 'V' (Void) oder '0' (No Fix) oder proprietäre Mähroboter-Daten ($PRM)
                                # Zähle gefüllte Felder abseits von Talker und Status
                                filled_data = [p for i, p in enumerate(parts) if i not in [0, 2, 6] and p.split('*')[0].strip()]
                                
                                if "V" in status_field or "0" in status_field or not filled_data or talker.startswith('$PRM'):
                                    # logger.debug(f"Überspringe unvollständige oder proprietäre NMEA-Zeile: '{line}'")
                                    continue
                            
                            msg = pynmea2.parse(line)
                            # Prüfe generisch auf GGA Datentyp (unterstützt GPGGA, GNGGA, GLGGA etc.)
                            if hasattr(msg, 'sentence_type') and msg.sentence_type == 'GGA':
                                gga_msg = msg
                                logger.debug(
                                    f"GGA gefunden ({msg.talker}): Qual={getattr(msg, 'gps_qual', 'N/A')}, Sats={getattr(msg, 'num_sats', 'N/A')}")
                                # break # Optional: Nur ersten GGA nehmen
                        except pynmea2.ParseError:
                            # Silently ignore parse errors for sentences that look like standard "no data" patterns
                            if "V" in line or ",0," in line or line.count(',,') > 3 or line.startswith('$PRM'):
                                # logger.debug(f"Ignoriere erwarteten Parse-Fehler für Such-Phase: '{line}'")
                                pass
                            else:
                                logger.warning(f"Fehler beim Parsen der NMEA-Zeile: '{line}'")
                        except AttributeError as e:
                            logger.error(f"Attributfehler beim Verarbeiten der NMEA-Nachricht: {e} - Zeile: '{line}'")
                    # else: # Zu viel Logspam
                    # if line:
                    # logger.debug(f"Ignoriere Zeile ohne '$': '{line[:50]}...'")

                except serial.SerialException as e:
                    logger.error(f"Serieller Fehler beim Lesen von GPS: {e}")
                    self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
                    self._reconnect_serial()
                    return None
                except UnicodeDecodeError as e:
                    logger.warning(f"Fehler beim Dekodieren der seriellen Daten: {e}")
                except Exception as e:
                    logger.error(f"Unerwarteter Fehler in get_gps_data Leseschleife: {e}", exc_info=True)
                    return None

            if gga_msg:
                current_time = time.time()
                qual = 0
                sats = 0
                try:
                    qual_str = getattr(gga_msg, 'gps_qual', '0')
                    qual = int(qual_str) if qual_str else 0
                except (ValueError, TypeError):
                    qual = 0
                try:
                    sats_str = getattr(gga_msg, 'num_sats', '0')
                    sats = int(sats_str) if sats_str else 0
                except (ValueError, TypeError):
                    sats = 0

                self.last_gga_info['qual'] = qual
                self.last_gga_info['sats'] = sats
                self.last_gga_info['timestamp'] = current_time

                if qual > 0:
                    self.last_valid_fix_time = current_time
                    try:
                        if hasattr(gga_msg, 'latitude') and hasattr(gga_msg, 'longitude') and \
                                gga_msg.latitude is not None and gga_msg.longitude is not None:
                            lat = float(gga_msg.latitude)
                            lon = float(gga_msg.longitude)
                            
                            # --- NEU: HDOP extrahieren ---
                            hdop = 10.0  # Hoher Standardwert für Sicherheit
                            try:
                                if hasattr(gga_msg, 'horizontal_dil') and gga_msg.horizontal_dil:
                                    hdop = float(gga_msg.horizontal_dil)
                            except (ValueError, TypeError):
                                pass

                            self.last_known_position = {
                                'lat': lat, 'lon': lon, 'timestamp': current_time,
                                'satellites': sats, 'hdop': hdop, 'mode': self.mode
                            }
                            logger.debug(
                                f"Gültige GGA-Daten verarbeitet: Qual={qual}, Sats={sats}, HDOP={hdop}, Pos=({lat:.6f}, {lon:.6f})")
                            return self.last_known_position
                        else:
                            logger.warning(f"GGA mit Qual={qual} hat keine gültigen Lat/Lon-Attribute: {gga_msg}")
                            return None
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Fehler beim Extrahieren von Lat/Lon aus GGA: {e} - GGA: {gga_msg}")
                        return None
                else:
                    logger.debug(f"Letzter gelesener GGA hatte keinen gültigen Fix (Qual={qual}).")
                    return None
            else:
                # logger.debug("Kein GGA-Satz im Lesezeitfenster gefunden.") # Zu viel Logspam
                time_since_last_info = time.time() - self.last_gga_info.get('timestamp', 0)
                # --- Logik für "No Signal" bleibt ---
                if time_since_last_info > 15:
                    if self.last_gga_info.get('qual') not in [-1, -2]:
                        logger.warning(
                            f"Seit {time_since_last_info:.1f}s keine GGA-Info mehr. Setze Status auf 'No Signal'.")
                        self.last_gga_info['qual'] = -2
                        self.last_gga_info['sats'] = 0
                return None

        logger.error("Unerwarteter Fall am Ende von get_gps_data erreicht.")
        return None

    # --- get_last_gga_status bleibt ---
    def get_last_gga_status(self):
        qual = self.last_gga_info.get('qual', -1)  # Standard -1 (Connecting)
        sats = self.last_gga_info.get('sats', 0)
        ts = self.last_gga_info.get('timestamp', 0)

        qual_map = {
            -2: "No Signal", -1: "Connecting", 0: "No Fix", 1: "GPS Fix (SPS)",
            2: "DGPS Fix", 3: "PPS Fix", 4: "RTK Fixed", 5: "RTK Float",
            6: "Estimated (DR)", 7: "Manual Input", 8: "Simulation"
        }
        fix_description = qual_map.get(qual, f"Unknown ({qual})")

        lat_str, lon_str = "", ""
        if self.last_known_position and 'lat' in self.last_known_position and 'lon' in self.last_known_position:
            if qual > 0 or (time.time() - self.last_known_position.get('timestamp', 0) < 15):
                try:
                    lat_str = f"{self.last_known_position['lat']:.8f}"
                    lon_str = f"{self.last_known_position['lon']:.8f}"
                except (TypeError, ValueError):
                    pass  # Fehler schon geloggt

        agps_status_str = ",AOP: On"

        # HDOP extrahieren
        hdop_val = 0.0
        if self.last_known_position:
            hdop_val = self.last_known_position.get('hdop', 0.0)

        status_message = f"status,{fix_description},{sats},{lat_str},{lon_str}{agps_status_str},{hdop_val:.2f}"
        # logger.debug(f"Generierter GPS Status String: {status_message} (Qual={qual}, Sats={sats}, TS={ts})") # Zu viel Logspam
        return status_message

    # --- generate_fake_data bleibt ---
    def generate_fake_data(self):
        lat_range, lon_range = GEO_CONFIG["fake_gps_range"]
        fake_pos = {
            'lat': random.uniform(*lat_range), 'lon': random.uniform(*lon_range),
            'timestamp': time.time(), 'satellites': random.randint(4, 12), 
            'hdop': round(random.uniform(0.8, 1.2), 2), 'mode': self.mode
        }
        logger.debug(f"Generiere Fake-Daten (random): {fake_pos}")
        return fake_pos

    # --- generate_fake_route_data bleibt ---
    def generate_fake_route_data(self):
        if self.route_simulator:
            if random.random() < 0.1:
                self.route_simulator.change_direction(random.randint(-30, 30))
            lat, lon = self.route_simulator.move()
            fake_pos = {
                'lat': lat, 'lon': lon, 'timestamp': time.time(),
                'satellites': random.randint(7, 12), 
                'hdop': round(random.uniform(0.8, 1.1), 2), 'mode': self.mode
            }
            logger.debug(f"Generiere Fake-Daten (route): {fake_pos}")
            return fake_pos
        else:
            logger.warning("Routenmodus aktiv, aber kein Routensimulator initialisiert.")
            return self.generate_fake_data()

    def check_assist_now(self, force_update=False):
        """AOP läuft on-chip, kein Server-Download nötig. Placeholder für Kompatibilität."""
        return True

    # --- change_gps_mode bleibt ---
    def change_gps_mode(self, new_mode):
        if new_mode == self.mode:
            logger.info(f"GPS-Modus ist bereits '{new_mode}'. Keine Änderung.")
            return True

        logger.info(f"Ändere GPS-Modus von '{self.mode}' zu: {new_mode}")
        previous_mode = self.mode
        self.mode = new_mode

        if new_mode == "fake_route":
            self.is_fake_gps = True
            start_lat, start_lon = self.map_center
            if not self.route_simulator or previous_mode == "real":
                if self.last_known_position and 'lat' in self.last_known_position:
                    start_lat = self.last_known_position['lat']
                    start_lon = self.last_known_position['lon']
                    logger.info(
                        f"Starte Routensimulator von letzter bekannter Position ({start_lat:.6f}, {start_lon:.6f}).")
                else:
                    logger.info(f"Starte Routensimulator von Kartenmitte ({start_lat:.6f}, {start_lon:.6f}).")
                self.route_simulator = GpsHandler.RouteSimulator(start_lat, start_lon, direction=random.randint(0, 360))
            self.close_serial()
            logger.info("Serielle Verbindung für Fake-Modus geschlossen (falls offen).")
            self.last_gga_info = {'qual': 8, 'sats': 8, 'timestamp': time.time()}

        elif new_mode == "fake_random":
            self.is_fake_gps = True
            self.route_simulator = None
            self.close_serial()
            logger.info("Serielle Verbindung für Fake-Modus geschlossen (falls offen).")
            self.last_gga_info = {'qual': 8, 'sats': 8, 'timestamp': time.time()}

        elif new_mode == "real":
            self.is_fake_gps = False
            self.route_simulator = None
            self._connect_serial()
            # WICHTIG: Erneut konfigurieren (Fussgänger-Modus, GNSS-Modus & AOP)
            self._configure_ublox_pedestrian()
            self._configure_gnss_mode()
            self._configure_ublox_autonomous()

        else:
            logger.warning(f"Ungültiger GPS-Modus angefordert: {new_mode}")
            self.mode = previous_mode
            return False

        logger.info(f"GPS-Modus erfolgreich auf '{self.mode}' geändert.")
        return True
