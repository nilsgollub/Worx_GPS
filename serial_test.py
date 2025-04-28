    # In gps_handler.py

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
                # --- NEU: write_timeout hinzufügen ---
                self.ser_gps = serial.Serial(
                    self.serial_port,
                    self.baudrate,
                    timeout=1,  # Read timeout
                    write_timeout=60  # Write timeout (z.B. 60 Sekunden)
                )
                # --- Wichtiger Log direkt nach Erfolg ---
                logger.info(f"Serielle Verbindung zu {self.ser_gps.name} erfolgreich hergestellt.")

                # Status auf "No Fix" setzen, bis der erste GGA kommt
                self.last_gga_info = {'qual': 0, 'sats': 0, 'timestamp': time.time()}

                # --- NEU: U-BLOX Konfiguration nach erfolgreicher Verbindung ---
                if PYUBX2_AVAILABLE:
                    self._configure_ublox()
                else:
                    logger.warning("pyubx2 nicht verfügbar, U-BLOX Konfiguration übersprungen.")
                # --- ENDE NEU ---

            except serial.SerialException as ser_e:
                # --- Detaillierteres Logging ---
                logger.error(f"Serieller Fehler beim Herstellen der Verbindung zu {self.serial_port}: {ser_e}",
                             exc_info=True)
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
            except Exception as e:
                # --- Detaillierteres Logging ---
                logger.error(f"Unerwarteter Fehler beim Herstellen der seriellen Verbindung zu {self.serial_port}: {e}",
                             exc_info=True)
                self.ser_gps = None
                self.last_gga_info = {'qual': -1, 'sats': 0, 'timestamp': time.time()}
        else:
            logger.info("Fake-Modus aktiv, keine serielle Verbindung erforderlich.")
            self.ser_gps = None
            self.last_gga_info = {'qual': 1, 'sats': 8, 'timestamp': time.time()}

    def send_assist_now_data(self, data):
        """Sendet die heruntergeladenen AssistNow Daten an das GPS-Modul."""
        logger.debug("send_assist_now_data aufgerufen.")  # <-- NEU

        # --- NEU: Explizite Prüfung und Logging ---
        if self.ser_gps is None:
            logger.warning("send_assist_now_data: self.ser_gps ist None. Breche ab.")
            return False
        if not self.ser_gps.is_open:
            logger.warning(f"send_assist_now_data: Serielle Verbindung {self.ser_gps.name} ist nicht offen. Breche ab.")
            return False
        # --- Ende NEU ---

        logger.debug(f"Versuche, {len(data)} Bytes auf {self.ser_gps.name} zu schreiben...")  # <-- NEU
        try:
            start_write = time.monotonic()  # <-- NEU
            bytes_written = self.ser_gps.write(data)
            duration_write = time.monotonic() - start_write  # <-- NEU
            logger.debug(
                f"self.ser_gps.write abgeschlossen nach {duration_write:.2f}s. Bytes geschrieben: {bytes_written}")  # <-- NEU

            logger.debug("Führe self.ser_gps.flush() aus...")  # <-- NEU
            start_flush = time.monotonic()  # <-- NEU
            self.ser_gps.flush()
            duration_flush = time.monotonic() - start_flush  # <-- NEU
            logger.debug(f"self.ser_gps.flush() abgeschlossen nach {duration_flush:.2f}s.")  # <-- NEU

            logger.info(f"AssistNow Offline-Daten ({bytes_written} Bytes) erfolgreich gesendet.")
            return True
        except serial.SerialTimeoutException:
            # --- NEU: Logge die Dauer bis zum Timeout ---
            duration_timeout = time.monotonic() - start_write
            # Sicherstellen, dass write_timeout existiert, bevor darauf zugegriffen wird
            write_timeout_val = getattr(self.ser_gps, 'write_timeout', 'N/A')
            logger.error(
                f"Timeout ({write_timeout_val}s) beim Senden der AssistNow Offline-Daten nach {duration_timeout:.2f}s.")
            self._reconnect_serial()
            return False
        except serial.SerialException as e:
            logger.error(f"Serieller Fehler beim Senden der AssistNow Offline-Daten: {e}",
                         exc_info=True)  # <-- exc_info hinzugefügt
            self._reconnect_serial()
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Senden der AssistNow Offline-Daten: {e}", exc_info=True)
            return False
