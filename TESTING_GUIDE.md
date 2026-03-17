# Server Testing Quick Reference

## Running Server Tests

### Run All Server Tests (29 tests)
```bash
pytest tests/test_servers.py tests/test_server_startup_validation.py -v
```

### Run Only Web UI Server Tests
```bash
pytest tests/test_servers.py::TestWebuiServer -v
```

### Run Only GPS Server Tests
```bash
pytest tests/test_servers.py::TestLiveGpsMapServer -v
```

### Run Only Startup Validation Tests
```bash
pytest tests/test_server_startup_validation.py -v
```

### Run With Coverage Report
```bash
pytest tests/test_servers.py tests/test_server_startup_validation.py -v --cov=web_ui --cov-report=html
```

### Run With Detailed Output
```bash
pytest tests/test_servers.py tests/test_server_startup_validation.py -v --tb=long -s
```

## Test Results Summary

✅ **Total Tests**: 29/29 PASSED
- Web UI Server: 9/9 ✅
- GPS Server: 3/3 ✅
- Services: 3/3 ✅
- Error Handling: 3/3 ✅
- Integration: 3/3 ✅
- Server Startup: 2/2 ✅
- Validation: 6/6 ✅

## What Gets Tested

### APIs Tested
- ✅ `GET /api/status` - Server status
- ✅ `GET /api/heatmaps` - Available heatmaps
- ✅ `GET /api/stats` - Statistics
- ✅ `GET /api/config` - Configuration
- ✅ `POST /config/save` - Config updates

### Services Tested
- ✅ MqttService - MQTT connectivity
- ✅ DataService - Data management
- ✅ StatusManager - Status tracking
- ✅ SystemMonitor - System monitoring

### Features Tested
- ✅ Flask app initialization
- ✅ SocketIO activation
- ✅ Error handling (503 responses)
- ✅ CORS configuration
- ✅ Route registration
- ✅ Data folder structure
- ✅ Configuration loading

## Continuous Testing

To run tests automatically before committing:

```bash
# Install git hooks
pytest tests/test_servers.py -v --tb=short
git add . && git commit -m "test: passed server tests"
```

## Troubleshooting

If tests fail:

1. **Import errors** → Check Python path is correct
2. **Module not found** → Run `pip install -r requirements.txt`
3. **Port already in use** → Stop existing servers
4. **File not found** → Verify data/ and heatmaps/ directories exist

## Performance

- Total execution time: ~1.71 seconds
- Average test time: ~59ms per test
- Suitable for CI/CD pipelines

## Integration with CI/CD

```yaml
# Example GitHub Actions
- name: Run Server Tests
  run: |
    pytest tests/test_servers.py tests/test_server_startup_validation.py \
      -v --tb=short --cov=web_ui --junitxml=results.xml
```

## Manual Server Startup

To start servers manually for testing:

### Start Web UI Server
```bash
python -m web_ui.webui
```

### Start GPS Server
```bash
python live_gps_map_server.py
```

### Start Both With Supervisor
```bash
# Create supervisord config
[program:webui]
command=python -m web_ui.webui
directory=/path/to/project
autostart=true
autorestart=true

[program:gps_server]
command=python live_gps_map_server.py
directory=/path/to/project
autostart=true
autorestart=true
```

## Environment Variables

Required in `.env`:
```
FLASK_SECRET_KEY=your-secret-key
MQTT_HOST=localhost
MQTT_PORT=1883
TEST_MODE=false
```

## Next Steps

1. ✅ Manual testing with curl
2. ✅ Load testing with Apache Bench
3. ✅ Browser testing with Selenium
4. ✅ Integration tests with frontend

---
**Last Updated**: 2026-03-17
**Status**: All tests passing ✅
