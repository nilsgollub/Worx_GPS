# web_ui/ha_discovery.py
"""Home Assistant MQTT Auto-Discovery Service.

Publishes discovery configs so HA automatically creates entities for the mower.
Compatible with the landroid-card (https://github.com/Barma-lej/landroid-card).

Entities created:
  - lawn_mower.{slug}              (main entity with start/pause/dock)
  - sensor.{slug}_battery          (battery %)
  - sensor.{slug}_rssi             (WiFi signal)
  - sensor.{slug}_total_worktime   (hours)
  - sensor.{slug}_distance_driven  (meters)
  - sensor.{slug}_blades_total_on_time (hours)
  - sensor.{slug}_blades_current_on_time (hours)
  - sensor.{slug}_yaw / roll / pitch
  - sensor.{slug}_error
  - binary_sensor.{slug}_online
  - binary_sensor.{slug}_rain
"""

import json
import logging
import re
import time
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Discovery prefix (HA default)
DISC_PREFIX = "homeassistant"

# Base topic for our state data
STATE_BASE = "worx_gps_monitor"

# Map our status categories to HA lawn_mower activities
CATEGORY_TO_ACTIVITY = {
    "mowing": "mowing",
    "starting": "mowing",
    "returning": "docked",  # on the way home → treat as docked
    "home": "docked",
    "idle": "docked",
    "paused": "paused",
    "error": "error",
    "unknown": "error",
}


def _slugify(text: str) -> str:
    """Convert a name to a slug (lowercase, underscores)."""
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    return s.strip('_')


class HADiscoveryService:
    """Publishes HA MQTT Auto-Discovery configs and state updates."""

    def __init__(self, mqtt_publish_fn: Callable, mower_name: str = "Mower",
                 serial: str = "unknown", firmware: str = "N/A"):
        """
        Args:
            mqtt_publish_fn: Function(topic, payload, qos, retain) to publish MQTT messages.
            mower_name: Display name of the mower.
            serial: Serial number (used as unique identifier).
            firmware: Firmware version string.
        """
        self._publish = mqtt_publish_fn
        self._mower_name = mower_name
        self._serial = serial
        self._firmware = firmware
        self._slug = _slugify(mower_name) or "mower"
        self._node_id = f"worx_gps_{self._slug}"
        self._discovered = False

        # State topics
        self._state_topic = f"{STATE_BASE}/{self._slug}/state"
        self._attr_topic = f"{STATE_BASE}/{self._slug}/attributes"
        self._avail_topic = f"{STATE_BASE}/{self._slug}/availability"
        self._cmd_topic = f"{STATE_BASE}/{self._slug}/command"

        logger.info(f"[HADiscovery] Initialisiert für '{mower_name}' (SN: {serial})")

    def _device_block(self) -> dict:
        """Returns the shared device block for all entities."""
        return {
            "identifiers": [f"worx_gps_{self._serial}"],
            "name": self._mower_name,
            "manufacturer": "Worx",
            "model": "Landroid",
            "serial_number": self._serial,
            "sw_version": self._firmware,
            "via_device": "worx_gps_monitor",
        }

    def _publish_discovery(self, component: str, object_id: str, config: dict):
        """Publish a single discovery config message."""
        topic = f"{DISC_PREFIX}/{component}/{self._node_id}/{object_id}/config"
        # Always include device block
        config.setdefault("device", self._device_block())
        config.setdefault("availability_topic", self._avail_topic)
        config.setdefault("payload_available", "online")
        config.setdefault("payload_not_available", "offline")

        payload = json.dumps(config)
        self._publish(topic, payload, qos=1, retain=True)
        logger.debug(f"[HADiscovery] Published: {topic}")

    # ------------------------------------------------------------------
    # Discovery: Register all entities
    # ------------------------------------------------------------------

    def publish_discovery_configs(self):
        """Publish discovery configs for all entities. Call once after connect."""
        logger.info("[HADiscovery] Registriere Entities bei Home Assistant...")

        slug = self._slug

        # 1. lawn_mower (main entity for landroid-card)
        self._publish_discovery("lawn_mower", slug, {
            "name": None,  # Use device name
            "unique_id": f"worx_gps_{self._serial}_mower",
            "activity_state_topic": self._state_topic,
            "activity_value_template": "{{ value_json.activity }}",
            "json_attributes_topic": self._attr_topic,
            "start_mowing_command_topic": self._cmd_topic,
            "start_mowing_command_template": '{"command": "start_mowing"}',
            "pause_command_topic": self._cmd_topic,
            "pause_command_template": '{"command": "pause"}',
            "dock_command_topic": self._cmd_topic,
            "dock_command_template": '{"command": "dock"}',
            "icon": "mdi:robot-mower",
        })

        # 2. Battery sensor
        self._publish_discovery("sensor", f"{slug}_battery", {
            "name": "Battery",
            "unique_id": f"worx_gps_{self._serial}_battery",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.battery_percent }}",
            "unit_of_measurement": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "icon": "mdi:battery",
        })

        # 3. RSSI sensor
        self._publish_discovery("sensor", f"{slug}_rssi", {
            "name": "RSSI",
            "unique_id": f"worx_gps_{self._serial}_rssi",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.rssi }}",
            "unit_of_measurement": "dBm",
            "device_class": "signal_strength",
            "state_class": "measurement",
            "icon": "mdi:wifi",
            "entity_category": "diagnostic",
        })

        # 4. Total worktime (in hours for landroid-card compatibility)
        self._publish_discovery("sensor", f"{slug}_total_worktime", {
            "name": "Total worktime",
            "unique_id": f"worx_gps_{self._serial}_total_worktime",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.total_worktime }}",
            "unit_of_measurement": "h",
            "icon": "mdi:timer-outline",
            "state_class": "total_increasing",
        })

        # 5. Distance driven (meters)
        self._publish_discovery("sensor", f"{slug}_distance_driven", {
            "name": "Distance driven",
            "unique_id": f"worx_gps_{self._serial}_distance",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.distance }}",
            "unit_of_measurement": "m",
            "icon": "mdi:map-marker-distance",
            "state_class": "total_increasing",
        })

        # 6. Blades total on time
        self._publish_discovery("sensor", f"{slug}_blades_total_on_time", {
            "name": "Blades total on time",
            "unique_id": f"worx_gps_{self._serial}_blades_total",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.blades_total_on }}",
            "unit_of_measurement": "h",
            "icon": "mdi:fan",
            "state_class": "total_increasing",
        })

        # 7. Blades current on time
        self._publish_discovery("sensor", f"{slug}_blades_current_on_time", {
            "name": "Blades current on time",
            "unique_id": f"worx_gps_{self._serial}_blades_current",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.blades_current_on }}",
            "unit_of_measurement": "h",
            "icon": "mdi:fan",
        })

        # 8. Orientation: Yaw / Roll / Pitch
        for axis in ["yaw", "roll", "pitch"]:
            self._publish_discovery("sensor", f"{slug}_{axis}", {
                "name": axis.capitalize(),
                "unique_id": f"worx_gps_{self._serial}_{axis}",
                "state_topic": self._state_topic,
                "value_template": f"{{{{ value_json.{axis} }}}}",
                "unit_of_measurement": "°",
                "icon": "mdi:axis-arrow",
                "entity_category": "diagnostic",
            })

        # 9. Error sensor
        self._publish_discovery("sensor", f"{slug}_error", {
            "name": "Error",
            "unique_id": f"worx_gps_{self._serial}_error",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.error }}",
            "icon": "mdi:alert-circle-outline",
        })

        # 10. Battery temperature
        self._publish_discovery("sensor", f"{slug}_battery_temperature", {
            "name": "Battery temperature",
            "unique_id": f"worx_gps_{self._serial}_bat_temp",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.battery_temperature }}",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "entity_category": "diagnostic",
        })

        # 11. Online binary sensor
        self._publish_discovery("binary_sensor", f"{slug}_online", {
            "name": "Online",
            "unique_id": f"worx_gps_{self._serial}_online",
            "state_topic": self._state_topic,
            "value_template": "{{ 'ON' if value_json.online else 'OFF' }}",
            "device_class": "connectivity",
            "entity_category": "diagnostic",
        })

        # 12. Rain binary sensor
        self._publish_discovery("binary_sensor", f"{slug}_rain", {
            "name": "Rain",
            "unique_id": f"worx_gps_{self._serial}_rain",
            "state_topic": self._state_topic,
            "value_template": "{{ 'ON' if value_json.rain else 'OFF' }}",
            "device_class": "moisture",
            "icon": "mdi:weather-rainy",
        })

        # 13. Status text (for the landroid-card status display)
        self._publish_discovery("sensor", f"{slug}_status", {
            "name": "Status",
            "unique_id": f"worx_gps_{self._serial}_status",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.status_text }}",
            "icon": "mdi:information-outline",
        })

        self._discovered = True
        logger.info(f"[HADiscovery] {15} Entities registriert.")

    # ------------------------------------------------------------------
    # State publishing
    # ------------------------------------------------------------------

    def publish_state(self, status: dict):
        """Publish current state from a WorxCloudService status dict.
        
        Args:
            status: The status dict from WorxCloudService._process_device_update()
        """
        if not self._discovered:
            return

        category = status.get("status_category", "unknown")
        activity = CATEGORY_TO_ACTIVITY.get(category, "error")
        
        battery = status.get("battery", {})
        orientation = status.get("orientation", {})
        statistics = status.get("statistics", {})
        rainsensor = status.get("rainsensor", {})

        # Blade times: pyworxcloud returns minutes, landroid-card expects hours
        blades_total_min = statistics.get("worktime_blades_on", 0) or 0
        blades_current_min = 0  # Not always available from pyworxcloud
        worktime_total_min = statistics.get("worktime_total", 0) or 0

        # State payload (flat JSON for value_templates)
        state = {
            "activity": activity,
            "status_text": status.get("status_text", "Unknown"),
            "status_id": status.get("status_id", -1),
            "battery_percent": battery.get("percent", 0),
            "battery_temperature": battery.get("temperature", 0),
            "battery_voltage": battery.get("voltage", 0),
            "battery_charging": battery.get("charging", False),
            "rssi": status.get("rssi", 0) or 0,
            "online": status.get("online", False),
            "locked": status.get("locked", False),
            "total_worktime": round(worktime_total_min / 60, 1) if worktime_total_min else 0,
            "distance": statistics.get("distance", 0) or 0,
            "blades_total_on": round(blades_total_min / 60, 1) if blades_total_min else 0,
            "blades_current_on": round(blades_current_min / 60, 1),
            "yaw": orientation.get("yaw", 0),
            "roll": orientation.get("roll", 0),
            "pitch": orientation.get("pitch", 0),
            "error": status.get("error_text", "") or "None",
            "error_id": status.get("error_id", 0),
            "rain": rainsensor.get("triggered", False),
            "rain_delay": rainsensor.get("delay", 0),
            "rain_remaining": rainsensor.get("remaining", 0),
            "firmware": status.get("firmware", "N/A"),
        }

        self._publish(self._state_topic, json.dumps(state), qos=0, retain=True)

        # Attributes payload (additional details for json_attributes_topic)
        attributes = {
            "serial_number": status.get("serial", "N/A"),
            "firmware": status.get("firmware", "N/A"),
            "status_id": status.get("status_id", -1),
            "battery_cycles": battery.get("cycles", {}),
            "schedule_active": status.get("schedule", {}).get("active", False),
            "time_extension": status.get("schedule", {}).get("time_extension", 0),
            "rain_delay": rainsensor.get("delay", 0),
            "rain_remaining": rainsensor.get("remaining", 0),
            "last_update": status.get("last_update", ""),
        }
        self._publish(self._attr_topic, json.dumps(attributes), qos=0, retain=True)

    def publish_availability(self, online: bool = True):
        """Publish availability status."""
        payload = "online" if online else "offline"
        self._publish(self._avail_topic, payload, qos=1, retain=True)
        logger.debug(f"[HADiscovery] Availability: {payload}")

    def update_device_info(self, mower_name: str, serial: str, firmware: str = "N/A"):
        """Update device info if it changes after initial connection."""
        changed = (mower_name != self._mower_name or serial != self._serial 
                   or firmware != self._firmware)
        self._mower_name = mower_name
        self._serial = serial
        self._firmware = firmware
        self._slug = _slugify(mower_name) or "mower"
        self._node_id = f"worx_gps_{self._slug}"

        # Update topic paths
        self._state_topic = f"{STATE_BASE}/{self._slug}/state"
        self._attr_topic = f"{STATE_BASE}/{self._slug}/attributes"
        self._avail_topic = f"{STATE_BASE}/{self._slug}/availability"
        self._cmd_topic = f"{STATE_BASE}/{self._slug}/command"

        if changed:
            logger.info(f"[HADiscovery] Device-Info aktualisiert: {mower_name} (SN: {serial})")

    def get_command_topic(self) -> str:
        """Returns the command topic for subscribing."""
        return self._cmd_topic

    def remove_discovery(self):
        """Remove all discovery configs (send empty payloads)."""
        logger.info("[HADiscovery] Entferne Discovery-Configs...")
        slug = self._slug
        components = [
            ("lawn_mower", slug),
            ("sensor", f"{slug}_battery"),
            ("sensor", f"{slug}_rssi"),
            ("sensor", f"{slug}_total_worktime"),
            ("sensor", f"{slug}_distance_driven"),
            ("sensor", f"{slug}_blades_total_on_time"),
            ("sensor", f"{slug}_blades_current_on_time"),
            ("sensor", f"{slug}_yaw"),
            ("sensor", f"{slug}_roll"),
            ("sensor", f"{slug}_pitch"),
            ("sensor", f"{slug}_error"),
            ("sensor", f"{slug}_battery_temperature"),
            ("sensor", f"{slug}_status"),
            ("binary_sensor", f"{slug}_online"),
            ("binary_sensor", f"{slug}_rain"),
        ]
        for comp, obj_id in components:
            topic = f"{DISC_PREFIX}/{comp}/{self._node_id}/{obj_id}/config"
            self._publish(topic, "", qos=1, retain=True)
