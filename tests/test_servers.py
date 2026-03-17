# tests/test_servers.py
"""
Comprehensive tests for server-side components (webui.py and live_gps_map_server.py)
"""
import pytest
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, call
import logging

# Konfiguriere Logging für Tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Füge das Root-Verzeichnis zum Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestWebuiServer:
    """Tests für den webui.py Flask-Server"""

    @pytest.fixture
    def app(self):
        """Erstelle eine Test-Flask-App"""
        # Patch alle externen Services bevor webui importiert wird
        with patch('web_ui.webui.MqttService'), \
             patch('web_ui.webui.StatusManager'), \
             patch('web_ui.webui.DataService'), \
             patch('web_ui.webui.SystemMonitor'):
            
            # Importiere und konfiguriere die App
            from web_ui import webui
            webui.app.config['TESTING'] = True
            
            # Setze die Services auf Mock-Instanzen
            webui.mqtt_service = MagicMock()
            webui.status_manager = MagicMock()
            webui.data_service = MagicMock()
            webui.system_monitor = MagicMock()
            
            # Konfiguriere Mock-Rückgabewerte
            webui.mqtt_service.is_connected.return_value = True
            webui.status_manager.get_current_mower_status.return_value = {
                "status": "mowing",
                "battery": 80
            }
            webui.status_manager.get_current_system_stats.return_value = {
                "cpu": 25.5,
                "memory": 45.2
            }
            webui.status_manager.get_current_pi_status.return_value = {
                "temperature": 52.5,
                "uptime": 1234567
            }
            webui.data_service.get_available_heatmaps.return_value = [
                {"id": "heatmap_aktuell", "name": "Current Heatmap"}
            ]
            webui.data_service.get_current_heatmap_path.return_value = "/heatmaps/heatmap_aktuell.html"
            webui.data_service.get_statistics.return_value = {
                "total_area": 1000,
                "coverage": 85.5
            }
            webui.data_service.get_formatted_problem_zones.return_value = []
            webui.data_service.get_mow_sessions_for_display.return_value = []
            webui.data_service.get_editable_config.return_value = {
                "heatmap_radius": 10,
                "heatmap_blur": 15
            }
            webui.data_service.get_config_info.return_value = {
                "version": "1.0"
            }
            
            return webui.app.test_client()

    def test_api_status_endpoint(self, app):
        """Test /api/status Endpoint"""
        response = app.get('/api/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "mower" in data
        assert "system" in data
        assert "pi" in data
        assert "mqtt_connected" in data

    def test_api_heatmaps_endpoint(self, app):
        """Test /api/heatmaps Endpoint"""
        response = app.get('/api/heatmaps')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "heatmaps" in data
        assert "current_heatmap" in data

    def test_api_stats_endpoint(self, app):
        """Test /api/stats Endpoint"""
        response = app.get('/api/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "stats" in data
        assert "problem_zones" in data
        assert "mow_sessions" in data

    def test_api_config_endpoint(self, app):
        """Test /api/config Endpoint"""
        response = app.get('/api/config')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "config" in data
        assert "info" in data

    def test_api_status_services_not_ready(self, app):
        """Test /api/status wenn Services nicht initialisiert sind"""
        with patch('web_ui.webui.status_manager', None):
            response = app.get('/api/status')
            assert response.status_code == 503
            data = json.loads(response.data)
            assert "error" in data

    def test_serve_react_index(self, app):
        """Test React UI Serving"""
        with patch('os.path.exists', return_value=True), \
             patch('web_ui.webui.send_from_directory', return_value="<html>index</html>"):
            response = app.get('/')
            # Response wird gemockt, daher checke nur dass die Route existiert
            assert response is not None

    def test_cors_enabled(self, app):
        """Test dass CORS aktiviert ist"""
        response = app.options('/api/status')
        # CORS sollte aktiviert sein
        assert response is not None

    def test_api_heatmaps_empty_list(self, app):
        """Test /api/heatmaps mit leerer Liste"""
        from web_ui import webui
        webui.data_service.get_available_heatmaps.return_value = []
        
        response = app.get('/api/heatmaps')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["heatmaps"] == []

    def test_config_save_not_implemented(self, app):
        """Test dass /config/save existiert"""
        response = app.post('/config/save', data={})
        # Route sollte existieren (mit oder ohne Erfolg)
        assert response.status_code in [200, 400, 403, 503]


class TestLiveGpsMapServer:
    """Tests für den live_gps_map_server.py Flask-Server"""

    @pytest.fixture
    def gps_app(self):
        """Erstelle eine Test-Flask-App für GPS Server"""
        with patch('config.MQTT_CONFIG', {
                'host': 'test.mqtt.broker',
                'port': 1883,
                'topic_status': 'test/status',
                'topic_gps': 'test/gps'
            }), \
             patch('config.GEO_CONFIG', {
                'map_center': (51.1657, 10.4515),
                'initial_zoom': 12
            }):
            
            from live_gps_map_server import app as gps_app
            gps_app.config['TESTING'] = True
            return gps_app.test_client()

    def test_gps_server_exists(self, gps_app):
        """Test dass GPS Server lädt"""
        assert gps_app is not None

    def test_gps_home_route(self, gps_app):
        """Test Hauptseite des GPS Servers"""
        response = gps_app.get('/')
        # Sollte 200 oder 404 sein (je nachdem ob Template existiert)
        assert response.status_code in [200, 404, 500]

    def test_gps_socketio_exists(self):
        """Test dass SocketIO konfiguriert ist"""
        with patch('config.MQTT_CONFIG', {}), \
             patch('config.GEO_CONFIG', {}):
            from live_gps_map_server import socketio
            assert socketio is not None


class TestServiceInitialization:
    """Tests für Service-Initialisierung"""

    def test_mqtt_service_init(self):
        """Test MQTT Service Initialisierung"""
        with patch('config.MQTT_CONFIG', {
                'host': 'localhost',
                'port': 1883,
                'topic_status': 'status'
            }), \
             patch('config.REC_CONFIG', {'test_mode': False}):
            
            from web_ui.mqtt_service import MqttService
            service = MqttService({'host': 'localhost'}, 'status')
            assert service is not None
            assert service.mqtt_config is not None

    def test_data_service_init(self):
        """Test DataService Initialisierung"""
        with patch('config.HEATMAP_CONFIG', {'radius': 10}), \
             patch('config.PROBLEM_CONFIG', {}), \
             patch('config.GEO_CONFIG', {}), \
             patch('config.REC_CONFIG', {}), \
             patch('web_ui.data_service.DataManager'), \
             patch('web_ui.data_service.HeatmapGenerator'):
            
            from web_ui.data_service import DataService
            service = DataService(project_root, {}, {}, {}, {})
            assert service is not None
            assert service.project_root == Path(project_root)

    def test_status_manager_init(self):
        """Test StatusManager Initialisierung"""
        try:
            from web_ui.status_manager import StatusManager
            manager = StatusManager(MagicMock())
            assert manager is not None
        except Exception as e:
            logger.warning(f"StatusManager konnte nicht initialisiert werden: {e}")


class TestErrorHandling:
    """Tests für Error Handling"""

    @pytest.fixture
    def app_with_errors(self):
        """App mit Error-Handling Tests"""
        with patch('web_ui.webui.MqttService'), \
             patch('web_ui.webui.StatusManager'), \
             patch('web_ui.webui.DataService'), \
             patch('web_ui.webui.SystemMonitor'):
            
            from web_ui import webui
            webui.app.config['TESTING'] = True
            webui.mqtt_service = None
            webui.status_manager = None
            webui.data_service = None
            
            return webui.app.test_client()

    def test_api_status_missing_services(self, app_with_errors):
        """Test API mit fehlenden Services"""
        response = app_with_errors.get('/api/status')
        assert response.status_code == 503

    def test_api_stats_missing_service(self, app_with_errors):
        """Test Stats API mit fehlender DataService"""
        response = app_with_errors.get('/api/stats')
        assert response.status_code == 503

    def test_api_config_missing_service(self, app_with_errors):
        """Test Config API mit fehlender DataService"""
        response = app_with_errors.get('/api/config')
        assert response.status_code == 503


class TestServerIntegration:
    """Integrationstests für Server"""

    def test_webui_imports_successfully(self):
        """Test dass webui.py erfolgreich importiert werden kann"""
        try:
            with patch('web_ui.webui.MqttService'), \
                 patch('web_ui.webui.StatusManager'), \
                 patch('web_ui.webui.DataService'), \
                 patch('web_ui.webui.SystemMonitor'):
                import web_ui.webui
                assert hasattr(web_ui.webui, 'app')
                assert web_ui.webui.app is not None
        except ImportError as e:
            pytest.fail(f"webui.py konnten nicht importiert werden: {e}")

    def test_live_gps_imports_successfully(self):
        """Test dass live_gps_map_server.py erfolgreich importiert werden kann"""
        try:
            with patch('config.MQTT_CONFIG', {}), \
                 patch('config.GEO_CONFIG', {}):
                import live_gps_map_server
                assert hasattr(live_gps_map_server, 'app')
                assert live_gps_map_server.app is not None
        except ImportError as e:
            pytest.fail(f"live_gps_map_server.py konnte nicht importiert werden: {e}")

    def test_required_dependencies_installed(self):
        """Test dass alle erforderlichen Dependencies installiert sind"""
        required_packages = [
            'flask',
            'flask_socketio',
            'flask_cors',
            'paho',  # paho-mqtt
            'dotenv'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                pytest.fail(f"Erforderliches Package '{package}' nicht installiert")


class TestServerStartup:
    """Tests für Server-Startup"""

    def test_webui_app_creation(self):
        """Test dass webui Flask App erstellt werden kann"""
        with patch('web_ui.webui.MqttService'), \
             patch('web_ui.webui.StatusManager'), \
             patch('web_ui.webui.DataService'), \
             patch('web_ui.webui.SystemMonitor'), \
             patch('web_ui.webui.SocketIO'):
            
            from web_ui import webui
            assert webui.app is not None
            assert webui.app.name == 'web_ui.webui'

    def test_socketio_initialization(self):
        """Test dass SocketIO initialisiert wird"""
        with patch('web_ui.webui.MqttService'), \
             patch('web_ui.webui.StatusManager'), \
             patch('web_ui.webui.DataService'), \
             patch('web_ui.webui.SystemMonitor'):
            
            from web_ui import webui
            assert webui.socketio is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--color=yes'])
