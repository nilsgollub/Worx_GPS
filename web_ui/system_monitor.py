# web_ui/system_monitor.py
import logging
import time
import threading

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil nicht gefunden. Systeminformationen sind nicht verfügbar.")

logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self, update_callback, interval=5):
        """
        Initialisiert den SystemMonitor.
        Args:
            update_callback (function): Callback-Funktion, die mit den Systemstatistiken aufgerufen wird.
            interval (int): Intervall in Sekunden, in dem die Statistiken gesammelt werden.
        """
        self.update_callback = update_callback
        self.interval = interval
        self.thread = None
        self.stop_event = threading.Event()
        self.current_stats = {"cpu_load": 0.0, "ram_usage": 0.0, "cpu_temp": None}

    def _get_cpu_temperature(self):
        """Liest die CPU-Temperatur aus (vereinfachte Version)."""
        if not PSUTIL_AVAILABLE: return None
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if 'cpu_thermal' in temps: return temps['cpu_thermal'][0].current
                if 'coretemp' in temps: return temps['coretemp'][0].current # Für Intel CPUs
                # Fallback für andere Namen oder erste gefundene CPU-Temperatur
                for name, entries in temps.items():
                    if 'cpu' in name.lower() or 'core' in name.lower():
                        for entry in entries: return entry.current
            # Fallback für /sys/class/thermal
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception: # Absichtlich breit, da viele Systemkonfigurationen
            # logger.debug("Konnte CPU-Temperatur nicht lesen.", exc_info=True) # Kann sehr gesprächig sein
            return None

    def _collect_stats(self):
        if PSUTIL_AVAILABLE:
            self.current_stats['cpu_load'] = psutil.cpu_percent(interval=None) # Non-blocking
            self.current_stats['ram_usage'] = psutil.virtual_memory().percent
            self.current_stats['cpu_temp'] = self._get_cpu_temperature()
        else:
            self.current_stats = {"cpu_load": 0.0, "ram_usage": 0.0, "cpu_temp": None}

        if self.update_callback:
            self.update_callback(self.current_stats.copy()) # Kopie senden

    def _run(self):
        logger.info("SystemMonitor-Thread gestartet.")
        while not self.stop_event.is_set():
            self._collect_stats()
            self.stop_event.wait(self.interval)
        logger.info("SystemMonitor-Thread beendet.")

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run, daemon=True, name="SystemMonitorThread")
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=self.interval + 1)
        logger.info("SystemMonitor gestoppt.")