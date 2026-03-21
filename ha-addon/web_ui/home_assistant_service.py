import requests
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class HomeAssistantService:
    def __init__(self):
        load_dotenv(override=True)
        self.url = os.getenv("HA_URL")
        self.token = os.getenv("HA_TOKEN")
        self.entity_id = os.getenv("HA_MOWER_ENTITY")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "content-type": "application/json",
        }
        
        if not self.url or not self.token:
            logger.warning("[HA-Service] HA_URL oder HA_TOKEN nicht gesetzt. HA-Integration inaktiv.")

    def get_mower_state(self):
        """Holt den aktuellen Status des Mähers aus Home Assistant."""
        if not self.url or not self.token or not self.entity_id:
            return None
            
        try:
            api_url = f"{self.url.rstrip('/')}/api/states/{self.entity_id}"
            response = requests.get(api_url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # Status-Text übersetzen oder direkt liefern
                return data.get('state', 'Unbekannt')
            else:
                logger.error(f"[HA-Service] Fehler beim Abrufen des Status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[HA-Service] Verbindungsfehler zu HA: {e}")
            return None

    def update_sensor(self, sensor_id, state, attributes=None):
        """Aktualisiert oder erstellt einen Sensor in Home Assistant (für Automatisierung)."""
        if not self.url or not self.token:
            return False
            
        try:
            api_url = f"{self.url.rstrip('/')}/api/states/sensor.{sensor_id}"
            payload = {
                "state": state,
                "attributes": attributes or {}
            }
            response = requests.post(api_url, headers=self.headers, json=payload, timeout=5)
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"[HA-Service] Fehler beim Senden an HA: {e}")
            return False

    def send_notification(self, message, title="Worx GPS"):
        """Sendet eine Benachrichtigung an Home Assistant."""
        if not self.url or not self.token:
            return False
            
        try:
            api_url = f"{self.url.rstrip('/')}/api/services/notify/persistent_notification"
            payload = {
                "title": title,
                "message": message
            }
            response = requests.post(api_url, headers=self.headers, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[HA-Service] Fehler beim Senden der Notification: {e}")
            return False

    def get_addon_info(self, addon_slug="local_worx_gps_monitor"):
        """Holt Informationen über ein Add-on vom Supervisor."""
        if not self.url or not self.token:
            return None
            
        try:
            api_url = f"{self.url.rstrip('/')}/api/hassio/addons/{addon_slug}/info"
            response = requests.get(api_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('data', {})
            return None
        except Exception as e:
            logger.error(f"[HA-Service] Fehler beim Abrufen der Add-on Info: {e}")
            return None

    def get_addon_logs(self, addon_slug="local_worx_gps_monitor"):
        """Holt die Logs eines Add-ons vom Supervisor."""
        if not self.url or not self.token:
            return "Kein HA_URL oder HA_TOKEN konfiguriert."
            
        try:
            api_url = f"{self.url.rstrip('/')}/api/hassio/addons/{addon_slug}/logs"
            response = requests.get(api_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.text
            return f"Fehler beim Abrufen der Logs: {response.status_code}"
        except Exception as e:
            logger.error(f"[HA-Service] Fehler beim Abrufen der Add-on Logs: {e}")
            return str(e)
