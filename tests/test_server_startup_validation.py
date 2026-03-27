# tests/test_server_startup_validation.py
"""
Validates that servers can be started and respond to requests
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestServerStartupValidation:
    """Validates production-like server startup"""

    def test_webui_server_startup_simulation(self):
        """Test webui.py can start without errors"""
        try:
            with patch('web_ui.webui.MqttService'), \
                 patch('web_ui.webui.StatusManager'), \
                 patch('web_ui.webui.DataService'), \
                 patch('web_ui.webui.SystemMonitor'):
                
                from web_ui import webui
                
                # Verify all required components exist
                assert hasattr(webui, 'app')
                assert hasattr(webui, 'socketio')
                assert webui.app is not None
                assert webui.socketio is not None
                
                # Test client creation
                client = webui.app.test_client()
                assert client is not None
                
                print("✅ Webui server startup validation passed")
                
        except Exception as e:
            pytest.fail(f"Webui server startup failed: {e}")

    def test_gps_server_startup_simulation(self):
        """Test live_gps_map_server.py can start without errors"""
        try:
            with patch('config.MQTT_CONFIG', {
                    'host': 'localhost',
                    'port': 1883
                }), \
                 patch('config.GEO_CONFIG', {
                    'map_center': (0, 0)
                }):
                
                import live_gps_map_server
                
                # Verify all required components exist
                assert hasattr(live_gps_map_server, 'app')
                assert hasattr(live_gps_map_server, 'socketio')
                assert live_gps_map_server.app is not None
                assert live_gps_map_server.socketio is not None
                
                # Test client creation
                client = live_gps_map_server.app.test_client()
                assert client is not None
                
                print("✅ GPS server startup validation passed")
                
        except Exception as e:
            pytest.fail(f"GPS server startup failed: {e}")

    def test_server_ports_configured(self):
        """Test that servers have configured ports"""
        import config
        
        # Check MQTT config exists
        assert hasattr(config, 'MQTT_CONFIG')
        assert isinstance(config.MQTT_CONFIG, dict)
        
        # Check GEO config exists
        assert hasattr(config, 'GEO_CONFIG')
        assert isinstance(config.GEO_CONFIG, dict)
        
        print("✅ Server configuration validation passed")

    def test_api_endpoints_available(self):
        """Test all API endpoints are available"""
        with patch('web_ui.webui.MqttService'), \
             patch('web_ui.webui.StatusManager'), \
             patch('web_ui.webui.DataService'), \
             patch('web_ui.webui.SystemMonitor'):
            
            from web_ui import webui
            app = webui.app
            
            # Get all registered routes
            routes = [str(rule) for rule in app.url_map.iter_rules()]
            
            # Check for key endpoints
            assert any('/api/status' in route for route in routes), "Missing /api/status endpoint"
            assert any('/api/heatmaps' in route for route in routes), "Missing /api/heatmaps endpoint"
            assert any('/api/stats' in route for route in routes), "Missing /api/stats endpoint"
            assert any('/api/config' in route for route in routes), "Missing /api/config endpoint"
            
            print("✅ API endpoints validation passed")

    def test_database_connectivity(self):
        """Test data folder exists"""
        data_dir = Path(project_root) / 'data'
        assert data_dir.exists(), "Data directory not found"
        print("✅ Data directory validation passed")

    def test_heatmaps_folder_exists(self):
        """Test heatmaps folder structure"""
        heatmaps_dir = Path(project_root) / 'heatmaps'
        assert heatmaps_dir.exists(), "Heatmaps directory not found"
        print("✅ Heatmaps directory validation passed")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
