"""WorxCloudService — Thread-sicherer Wrapper um pyworxcloud für die Flask WebUI.

Stellt eine persistente Verbindung zur Worx Cloud her und bietet synchrone
Methoden für Befehle und Statusabfragen, die aus Flask-Routen aufgerufen werden können.
Ersetzt HomeAssistantService + ha_polling_loop für den Mäher-Status und Autopilot.
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

from dotenv import load_dotenv

# Lade .env (falls vorhanden), aber überschreibe keine bereits gesetzten System-Umgebungsvariablen (wie in HA)
load_dotenv(override=False)

logger = logging.getLogger(__name__)

# Status-Code Mapping (dat.ls) → Deutscher Text + Kategorie
STATUS_MAP = {
    0: ("Leerlauf", "idle"),
    1: ("Zuhause", "home"),
    2: ("Start-Sequenz", "starting"),
    3: ("Verlässt Ladestation", "starting"),
    4: ("Folgt Draht", "mowing"),
    5: ("Sucht Ladestation", "returning"),
    6: ("Sucht Draht", "mowing"),
    7: ("Mäht", "mowing"),
    8: ("Angehoben", "error"),
    9: ("Festgefahren", "error"),
    10: ("Klingenschutz aktiv", "error"),
    11: ("Debug", "idle"),
    12: ("Fernsteuerung", "mowing"),
    30: ("Zurück zur Ladestation", "returning"),
    31: ("Erstellt Zonen-Karte", "mowing"),
    32: ("Kantenschnitt", "mowing"),
    33: ("Suche Start-Zone", "mowing"),
    34: ("Pause", "paused"),
    100: ("Interner Wakeup", "idle"),
    101: ("Erstinitialisierung", "idle"),
    102: ("Firmware-Upgrade", "idle"),
    103: ("Draht-Initialisierung", "idle"),
}

# Autopilot-Kategorien
MOWING_CATEGORIES = {"mowing", "starting"}
IDLE_CATEGORIES = {"idle", "home", "returning", "paused"}
ERROR_CATEGORIES = {"error"}


class WorxCloudService:
    """Wrapper um pyworxcloud.WorxCloud für synchronen Zugriff aus Flask."""

    def __init__(self):
        self._email = os.getenv("WORX_EMAIL", "")
        self._password = os.getenv("WORX_PASSWORD", "")
        self._cloud_type = os.getenv("WORX_CLOUD_TYPE", "worx")

        self._cloud = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._running = False
        self._lock = threading.Lock()

        # Cached device data
        self._device_name: Optional[str] = None
        self._serial: Optional[str] = None
        self._last_status: dict = {}
        self._last_update: Optional[str] = None

        # Autopilot
        self._autopilot_enabled = True
        self._last_autopilot_category: Optional[str] = None
        self._mqtt_publish_callback: Optional[Callable] = None

        # Status-Update Callback (für StatusManager / SocketIO)
        self._on_status_update: Optional[Callable] = None

        # HA MQTT Auto-Discovery
        self._ha_discovery = None

        if not self._email or not self._password:
            logger.warning("[WorxCloud] WORX_EMAIL oder WORX_PASSWORD nicht gesetzt. Service inaktiv.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Startet den Hintergrund-Event-Loop und verbindet sich mit der Cloud."""
        if not self._email or not self._password:
            logger.warning("[WorxCloud] Kein Login konfiguriert, Service wird nicht gestartet.")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="WorxCloudLoop")
        self._thread.start()

        # Warte auf Verbindung (max 30s)
        for i in range(120): # Erhöht auf 60s
            if self._connected:
                return True
            if i % 10 == 0:
                logger.debug(f"[WorxCloud] Warte auf Verbindung ({i/2}s)...")
            time.sleep(0.5)

        logger.error("[WorxCloud] Timeout beim Verbinden mit der Worx Cloud. Überprüfen Sie ihre Log-Meldungen.")
        return False

    def stop(self):
        """Stoppt die Cloud-Verbindung."""
        self._running = False
        if self._ha_discovery:
            self._ha_discovery.publish_availability(False)
        if self._loop and self._connected:
            future = asyncio.run_coroutine_threadsafe(self._cloud.disconnect(), self._loop)
            try:
                future.result(timeout=10)
            except Exception as e:
                logger.error(f"[WorxCloud] Fehler beim Trennen: {e}")
        self._connected = False
        logger.info("[WorxCloud] Service gestoppt.")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def set_status_update_callback(self, callback: Callable):
        """Callback wird bei jedem Cloud-Status-Update aufgerufen mit dem Status-Dict."""
        self._on_status_update = callback

    def set_mqtt_publish_callback(self, callback: Callable):
        """Callback für Autopilot: callback(command_str) → publiziert auf lokalen MQTT."""
        self._mqtt_publish_callback = callback

    def set_autopilot(self, enabled: bool):
        """Aktiviert/Deaktiviert den Autopilot."""
        self._autopilot_enabled = enabled
        logger.info(f"[WorxCloud] Autopilot {'aktiviert' if enabled else 'deaktiviert'}.")

    def set_ha_discovery(self, ha_discovery):
        """Setzt den HA Discovery Service für Auto-Discovery."""
        self._ha_discovery = ha_discovery
        logger.info("[WorxCloud] HA Discovery Service gesetzt.")

    # ------------------------------------------------------------------
    # Async Event Loop (Hintergrund-Thread)
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Läuft in einem Daemon-Thread und hält den asyncio Event-Loop am Leben."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            logger.error(f"[WorxCloud] Event-Loop Fehler: {e}", exc_info=True)
        finally:
            self._connected = False
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()
            logger.info("[WorxCloud] Event-Loop beendet.")

    async def _connect_and_listen(self):
        """Authentifiziert, verbindet und hält die MQTT-Verbindung offen. Mit Auto-Reconnect."""
        from pyworxcloud import WorxCloud
        from pyworxcloud.events import LandroidEvent

        mask_email = f"{self._email[:3]}***@{self._email.split('@')[-1]}" if '@' in self._email else "***"
        logger.info(f"[WorxCloud] Verbinde als '{mask_email}' (Type: {self._cloud_type})...")

        if not self._email or not self._password:
            logger.error("[WorxCloud] Email oder Passwort fehlen im Hintergrund-Thread!")
            return

        while self._running:
            try:
                self._cloud = WorxCloud(self._email, self._password, self._cloud_type)

                logger.debug("[WorxCloud] Führe Authentifizierung durch...")
                await self._cloud.authenticate()
                logger.info("[WorxCloud] Authentifizierung erfolgreich.")

                logger.debug("[WorxCloud] Suche Mäher im Account...")
                connected = await self._cloud.connect()
                if not connected:
                    logger.error("[WorxCloud] Keine Mäher gefunden oder Verbindung zur API/MQTT fehlgeschlagen. Reconnect in 10s...")
                    await asyncio.sleep(10)
                    continue
                
                if self._cloud.devices:
                    # pyworxcloud.devices ist ein Dictionary {serial: DeviceHandler}
                    first_device = list(self._cloud.devices.values())[0]
                    self._device_name = getattr(first_device, "name", "Unbekannt")
                    self._serial = getattr(first_device, "sn", "N/A")
                    logger.info(f"[WorxCloud] Mäher verbunden: {self._device_name} ({self._serial})")
                else:
                    logger.warning("[WorxCloud] Authentifizierung erfolgreich, aber keine Mäher im Account gefunden.")
                    self._device_name = "Kein Mäher"
                    self._serial = "N/A"

                # Erstes Gerät als Standard verwenden
                for name, device in self._cloud.devices.items():
                    self._device_name = name
                    self._serial = device.serial_number
                    logger.info(f"[WorxCloud] Aktives Gerät: '{name}' (SN: {self._serial})")
                    break

                # Initiales Status-Update
                if self._device_name in self._cloud.devices:
                    self._process_device_update(self._device_name, self._cloud.devices[self._device_name])

                # Event-Callback registrieren
                self._cloud.set_callback(LandroidEvent.DATA_RECEIVED, self._on_data_received)

                self._connected = True
                logger.info("[WorxCloud] Echtzeit-Events aktiv. Warte auf Updates...")

                # HA Discovery: Device-Info aktualisieren und Discovery publizieren
                if self._ha_discovery:
                    fw = str(getattr(list(self._cloud.devices.values())[0], 'firmware', 'N/A')) if self._cloud.devices else 'N/A'
                    self._ha_discovery.update_device_info(
                        self._device_name or 'Mower',
                        self._serial or 'unknown',
                        fw
                    )
                    self._ha_discovery.publish_discovery_configs()
                    self._ha_discovery.publish_availability(True)

                # Event-Loop am Leben halten
                while self._connected and self._running:
                    await asyncio.sleep(1)

            except Exception as e:
                self._connected = False
                logger.error(f"[WorxCloud] Verbindungsabbruch oder Fehler: {e}. Reconnect in 10s...", exc_info=True)
                if self._running:
                    await asyncio.sleep(10)

    def _on_data_received(self, name: str, device):
        """Callback von pyworxcloud bei jedem MQTT-Update vom Mäher."""
        logger.debug(f"[WorxCloud] DATA_RECEIVED für '{name}'")
        self._process_device_update(name, device)

    # ------------------------------------------------------------------
    # Status-Verarbeitung
    # ------------------------------------------------------------------

    def _process_device_update(self, name: str, device):
        """Extrahiert alle relevanten Daten aus dem DeviceHandler und cached sie."""
        try:
            status_id = device.status.get("id", -1) if isinstance(device.status, dict) else -1
            error_id = device.error.get("id", 0) if isinstance(device.error, dict) else 0
            status_text, category = STATUS_MAP.get(status_id, (f"Unbekannt ({status_id})", "unknown"))

            # Batterie
            battery = {}
            if device.battery:
                battery = {
                    "percent": device.battery.get("percent", 0),
                    "temperature": device.battery.get("temperature", 0),
                    "voltage": device.battery.get("voltage", 0),
                    "charging": device.battery.get("charging", False),
                    "cycles": device.battery.get("cycles", {}),
                }

            # Orientierung (IMU)
            orientation = {}
            if device.orientation:
                orientation = {
                    "pitch": device.orientation.get("pitch", 0),
                    "roll": device.orientation.get("roll", 0),
                    "yaw": device.orientation.get("yaw", 0),
                }

            # Statistiken
            statistics = {}
            if device.statistics:
                statistics = {
                    "worktime_total": device.statistics.get("worktime_total", 0),
                    "worktime_blades_on": device.statistics.get("worktime_blades_on", 0),
                    "distance": device.statistics.get("distance", 0),
                }

            # Zeitplan
            schedule = {}
            if device.schedules:
                schedule = {
                    "active": device.schedules.get("active", False),
                    "pause_mode_enabled": device.schedules.get("pause_mode_enabled", False),
                    "time_extension": device.schedules.get("time_extension", 0),
                }

            rssi = getattr(device, "rssi", None)
            locked = getattr(device, "locked", None)

            # Regensensor
            rainsensor = {}
            if device.rainsensor:
                rainsensor = {
                    "triggered": device.rainsensor.get("triggered", False),
                    "remaining": device.rainsensor.get("remaining", 0),
                    "delay": device.rainsensor.get("delay", 0),
                }

            now = datetime.now().strftime("%H:%M:%S")

            status = {
                "name": name,
                "serial": self._serial,
                "online": device.online,
                "status_id": status_id,
                "status_text": status_text,
                "status_category": category,
                "error_id": error_id,
                "error_text": device.error.get("description", "") if isinstance(device.error, dict) else "",
                "battery": battery,
                "orientation": orientation,
                "statistics": statistics,
                "schedule": schedule,
                "rssi": rssi,
                "locked": locked,
                "rainsensor": rainsensor,
                "firmware": str(getattr(device, "firmware", "N/A")),
                "last_update": now,
            }

            with self._lock:
                self._last_status = status
                self._last_update = now

            # Callback für StatusManager/Frontend
            if self._on_status_update:
                try:
                    self._on_status_update(status)
                except Exception as e:
                    logger.error(f"[WorxCloud] Fehler im Status-Callback: {e}")

            # Autopilot
            if self._autopilot_enabled:
                self._run_autopilot(status_id, category)

            # HA Discovery: State publizieren
            if self._ha_discovery:
                try:
                    self._ha_discovery.publish_state(status)
                except Exception as e:
                    logger.error(f"[WorxCloud] Fehler beim HA Discovery State Update: {e}")

            logger.debug(f"[WorxCloud] Status: {status_text} (ID:{status_id}, Kat:{category})")

        except Exception as e:
            logger.error(f"[WorxCloud] Fehler beim Verarbeiten des Device-Updates: {e}", exc_info=True)

    def _run_autopilot(self, status_id: int, category: str):
        """Autopilot-Logik: Sendet START_REC/STOP_REC/PROBLEM basierend auf Cloud-Status."""
        if not self._mqtt_publish_callback:
            return

        if category == self._last_autopilot_category:
            return  # Keine Änderung

        old_cat = self._last_autopilot_category
        self._last_autopilot_category = category

        if category in MOWING_CATEGORIES:
            logger.info(f"[WorxCloud-Autopilot] Mäher aktiv (ID:{status_id}) → START_REC")
            self._mqtt_publish_callback("START_REC")

        elif category in IDLE_CATEGORIES:
            logger.info(f"[WorxCloud-Autopilot] Mäher idle/home (ID:{status_id}) → STOP_REC")
            self._mqtt_publish_callback("STOP_REC")

        elif category in ERROR_CATEGORIES:
            logger.info(f"[WorxCloud-Autopilot] Mäher FEHLER (ID:{status_id}) → PROBLEM")
            self._mqtt_publish_callback("PROBLEM")

        else:
            logger.debug(f"[WorxCloud-Autopilot] Unbekannte Kategorie '{category}', keine Aktion.")

    # ------------------------------------------------------------------
    # Synchrone Getter (für Flask-Routen)
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Gibt den letzten gecachten Status zurück."""
        with self._lock:
            return self._last_status.copy()

    def get_device_name(self) -> Optional[str]:
        return self._device_name

    def get_serial(self) -> Optional[str]:
        return self._serial

    # ------------------------------------------------------------------
    # Synchrone Befehle (für Flask-Routen)
    # ------------------------------------------------------------------

    def _run_async(self, coro) -> Any:
        """Führt eine Coroutine im Hintergrund-Loop aus und wartet auf das Ergebnis."""
        if not self._loop or not self._connected:
            raise ConnectionError("Nicht mit der Worx Cloud verbunden.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    def command_start(self) -> dict:
        """Mähen starten."""
        try:
            self._run_async(self._cloud.start(self._serial))
            return {"success": True, "command": "start"}
        except Exception as e:
            logger.error(f"[WorxCloud] Start fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_stop(self) -> dict:
        """Zurück zur Box (Messer an)."""
        try:
            self._run_async(self._cloud.home(self._serial))
            return {"success": True, "command": "home"}
        except Exception as e:
            logger.error(f"[WorxCloud] Home fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_pause(self) -> dict:
        """Mähen pausieren."""
        try:
            self._run_async(self._cloud.pause(self._serial))
            return {"success": True, "command": "pause"}
        except Exception as e:
            logger.error(f"[WorxCloud] Pause fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_safehome(self) -> dict:
        """Zurück zur Box (Messer aus)."""
        try:
            self._run_async(self._cloud.safehome(self._serial))
            return {"success": True, "command": "safehome"}
        except Exception as e:
            logger.error(f"[WorxCloud] SafeHome fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_edgecut(self) -> dict:
        """Kantenschnitt starten."""
        try:
            self._run_async(self._cloud.edgecut(self._serial))
            return {"success": True, "command": "edgecut"}
        except Exception as e:
            logger.error(f"[WorxCloud] Edgecut fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_restart(self) -> dict:
        """Baseboard neustarten."""
        try:
            self._run_async(self._cloud.restart(self._serial))
            return {"success": True, "command": "restart"}
        except Exception as e:
            logger.error(f"[WorxCloud] Restart fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_ots(self, boundary: bool = False, runtime: int = 60) -> dict:
        """Einmal-Mähplan (One-Time-Schedule)."""
        try:
            self._run_async(self._cloud.ots(self._serial, boundary, runtime))
            return {"success": True, "command": "ots", "boundary": boundary, "runtime": runtime}
        except Exception as e:
            logger.error(f"[WorxCloud] OTS fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_set_lock(self, state: bool) -> dict:
        """Mäher sperren/entsperren."""
        try:
            self._run_async(self._cloud.set_lock(self._serial, state))
            return {"success": True, "command": "lock", "state": state}
        except Exception as e:
            logger.error(f"[WorxCloud] Lock fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_set_torque(self, torque: int) -> dict:
        """Rad-Drehmoment setzen (-50 bis +50%)."""
        try:
            self._run_async(self._cloud.set_torque(self._serial, torque))
            return {"success": True, "command": "torque", "value": torque}
        except Exception as e:
            logger.error(f"[WorxCloud] Torque fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_set_raindelay(self, minutes: int) -> dict:
        """Regenverzögerung setzen (in Minuten)."""
        try:
            self._run_async(self._cloud.raindelay(self._serial, minutes))
            return {"success": True, "command": "raindelay", "value": minutes}
        except Exception as e:
            logger.error(f"[WorxCloud] Raindelay fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_toggle_schedule(self, enable: bool) -> dict:
        """Zeitplan ein/aus."""
        try:
            self._run_async(self._cloud.toggle_schedule(self._serial, enable))
            return {"success": True, "command": "toggle_schedule", "enabled": enable}
        except Exception as e:
            logger.error(f"[WorxCloud] Toggle Schedule fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_set_zone(self, zone: int) -> dict:
        """Zone auswählen."""
        try:
            self._run_async(self._cloud.setzone(self._serial, zone))
            return {"success": True, "command": "setzone", "zone": zone}
        except Exception as e:
            logger.error(f"[WorxCloud] SetZone fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_set_time_extension(self, percent: int) -> dict:
        """Zeitplan-Verlängerung setzen (-100 bis +100%, Schritte von 10)."""
        try:
            self._run_async(self._cloud.set_time_extension(self._serial, percent))
            return {"success": True, "command": "time_extension", "value": percent}
        except Exception as e:
            logger.error(f"[WorxCloud] Time Extension fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def get_schedule(self) -> dict:
        """Zeitplan abrufen."""
        try:
            schedule = self._cloud.get_schedule(self._serial)
            return {"success": True, "schedule": schedule}
        except Exception as e:
            logger.error(f"[WorxCloud] Get Schedule fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def command_send_raw(self, json_data: str) -> dict:
        """Raw JSON an den Mäher senden."""
        try:
            self._run_async(self._cloud.send(self._serial, json_data))
            return {"success": True, "command": "raw", "data": json_data}
        except Exception as e:
            logger.error(f"[WorxCloud] Raw Send fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}
