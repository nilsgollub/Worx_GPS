import pytest
from unittest.mock import patch, MagicMock, call
import paho.mqtt.client as paho_mqtt_client
from paho.mqtt.enums import CallbackAPIVersion
import logging

# Mock config before importing MqttHandler
MQTT_CONFIG_MOCK_REAL = {
    "host": "real.mqtt.com", "port": 1883, "user": "real_user", "password": "real_password",
    "host_lokal": "local.mqtt.com", "port_lokal": 1884, "user_local": "local_user", "password_local": "local_password",
    "topic_control": "worx/control", "topic_gps": "worx/gps", "topic_status": "worx/status"
}
MQTT_CONFIG_MOCK_TEST = {
    "host": "real.mqtt.com", "port": 1883, "user": "real_user", "password": "real_password",
    "host_lokal": "local.mqtt.com", "port_lokal": 1884, "user_local": "local_user", "password_local": "local_password",
    "topic_control": "worx/control_test", "topic_gps": "worx/gps_test", "topic_status": "worx/status_test"
}


# Mock paho client globally for tests
@patch('mqtt_handler.paho_mqtt_client.Client')
def test_mqtt_handler_init_real_mode(MockPahoClient):
    """Test initialization in real mode."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)

        MockPahoClient.assert_called_once_with(CallbackAPIVersion.VERSION2)
        assert handler.test_mode is False
        assert handler.broker == "real.mqtt.com"
        assert handler.port == 1883
        assert handler.user == "real_user"
        assert handler.password == "real_password"
        assert handler.topic_control == "worx/control"
        assert handler.mqtt_client == mock_client_instance
        # Check if callbacks were assigned
        assert handler.mqtt_client.on_connect is not None
        assert handler.mqtt_client.on_disconnect is not None
        assert handler.mqtt_client.on_message is not None


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_mqtt_handler_init_test_mode(MockPahoClient):
    """Test initialization in test mode."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_TEST):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=True)

        MockPahoClient.assert_called_once_with(CallbackAPIVersion.VERSION2)
        assert handler.test_mode is True
        assert handler.broker == "local.mqtt.com"
        assert handler.port == 1884
        assert handler.user == "local_user"
        assert handler.password == "local_password"
        assert handler.topic_gps == "worx/gps_test"
        assert handler.mqtt_client == mock_client_instance


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_on_connect_success(MockPahoClient, caplog):
    """Test the _on_connect callback on success."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        # Simulate the callback being called by paho-mqtt
        handler._on_connect(mock_client_instance, None, None, 0, None)  # reason_code 0 = success
        assert f"Erfolgreich mit MQTT Broker verbunden: {handler.broker}:{handler.port}" in caplog.text


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_on_connect_failure(MockPahoClient, caplog):
    """Test the _on_connect callback on failure."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        handler._on_connect(mock_client_instance, None, None, 5, None)  # reason_code 5 = Auth error
        assert "Verbindung zum MQTT Broker fehlgeschlagen mit Reason Code: 5" in caplog.text


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_on_disconnect_graceful(MockPahoClient, caplog):
    """Test the _on_disconnect callback on graceful disconnect."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        # Simulate the callback
        handler._on_disconnect(mock_client_instance, None, None, 0, None)  # reason_code 0 = graceful
        assert "Verbindung zum MQTT Broker bewusst getrennt." in caplog.text


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_on_disconnect_unexpected(MockPahoClient, caplog):
    """Test the _on_disconnect callback on unexpected disconnect."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        handler._on_disconnect(mock_client_instance, None, None, 8, None)  # reason_code 8 = unspecified error
        assert "Verbindung zum MQTT Broker unerwartet getrennt. Reason Code: 8" in caplog.text


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_set_message_callback(MockPahoClient):
    """Test setting and triggering a custom message callback."""
    mock_client_instance = MockPahoClient.return_value
    custom_callback_mock = MagicMock()

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        handler.set_message_callback(custom_callback_mock)

        # Simulate paho-mqtt calling the internal on_message
        mock_msg = MagicMock()
        mock_msg.topic = "some/topic"
        mock_msg.payload = b"hello"
        handler.mqtt_client.on_message(mock_client_instance, None, mock_msg)

        # Assert that our custom callback was called with only the msg argument
        custom_callback_mock.assert_called_once_with(mock_msg)


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_connect(MockPahoClient):
    """Test the connect method."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        handler.connect()

        # Check if username/password were set
        mock_client_instance.username_pw_set.assert_called_once_with(handler.user, handler.password)
        # Check if connect was called
        mock_client_instance.connect.assert_called_once_with(handler.broker, handler.port, 60)
        # Check if loop was started
        mock_client_instance.loop_start.assert_called_once()


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_connect_no_auth(MockPahoClient):
    """Test connect method when user/password are not set in config."""
    mock_client_instance = MockPahoClient.return_value
    # Mock config without user/pass
    config_no_auth = MQTT_CONFIG_MOCK_REAL.copy()
    config_no_auth["user"] = None
    config_no_auth["password"] = None

    with patch('mqtt_handler.MQTT_CONFIG', config_no_auth):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        handler.connect()

        mock_client_instance.username_pw_set.assert_not_called()
        mock_client_instance.connect.assert_called_once_with(handler.broker, handler.port, 60)
        mock_client_instance.loop_start.assert_called_once()


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_disconnect(MockPahoClient):
    """Test the disconnect method."""
    mock_client_instance = MockPahoClient.return_value
    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        # Assume connect was called before
        handler.disconnect()

        mock_client_instance.loop_stop.assert_called_once()
        mock_client_instance.disconnect.assert_called_once()


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_publish_message_success(MockPahoClient):
    """Test publishing a message successfully."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = True  # Simulate connected state
    mock_msg_info = MagicMock()
    mock_msg_info.rc = paho_mqtt_client.MQTT_ERR_SUCCESS
    mock_client_instance.publish.return_value = mock_msg_info

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        topic = "test/publish"
        payload = "hello world"
        result = handler.publish_message(topic, payload, retain=True)

        mock_client_instance.publish.assert_called_once_with(topic, payload.encode('utf-8'), retain=True)
        assert result == mock_msg_info


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_publish_message_bytes_payload(MockPahoClient):
    """Test publishing a message with bytes payload."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = True
    mock_msg_info = MagicMock()
    mock_msg_info.rc = paho_mqtt_client.MQTT_ERR_SUCCESS
    mock_client_instance.publish.return_value = mock_msg_info

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        topic = "test/publish_bytes"
        payload = b'\x01\x02\x03'
        handler.publish_message(topic, payload)

        mock_client_instance.publish.assert_called_once_with(topic, payload, retain=False)  # retain default is False


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_publish_message_not_connected(MockPahoClient, caplog):
    """Test publishing when not connected."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = False  # Simulate disconnected state

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        result = handler.publish_message("test/fail", "payload")

        mock_client_instance.publish.assert_not_called()
        assert "Kann Nachricht nicht senden: MQTT Client nicht verbunden" in caplog.text
        assert result is None


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_publish_message_error_rc(MockPahoClient, caplog):
    """Test publishing when publish returns an error code."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = True
    mock_msg_info = MagicMock()
    mock_msg_info.rc = paho_mqtt_client.MQTT_ERR_QUEUE_SIZE  # Example error
    mock_client_instance.publish.return_value = mock_msg_info

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        handler.publish_message("test/error", "payload")

        mock_client_instance.publish.assert_called_once()
        assert f"Problem beim Übergeben der Nachricht auf Topic 'test/error'. RC: {paho_mqtt_client.MQTT_ERR_QUEUE_SIZE}" in caplog.text


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_subscribe_success(MockPahoClient):
    """Test subscribing to a topic successfully."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = True
    mock_client_instance.subscribe.return_value = (paho_mqtt_client.MQTT_ERR_SUCCESS, 123)  # result, mid

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        topic = "test/subscribe"
        qos = 1
        result, mid = handler.subscribe(topic, qos)

        mock_client_instance.subscribe.assert_called_once_with(topic, qos)
        assert result == paho_mqtt_client.MQTT_ERR_SUCCESS
        assert mid == 123


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_subscribe_not_connected(MockPahoClient, caplog):
    """Test subscribing when not connected."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = False

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        result, mid = handler.subscribe("test/fail_sub", 0)

        mock_client_instance.subscribe.assert_not_called()
        assert "Kann Topic nicht abonnieren: MQTT Client nicht verbunden" in caplog.text
        assert result is None
        assert mid is None


@patch('mqtt_handler.paho_mqtt_client.Client')
def test_subscribe_error_rc(MockPahoClient, caplog):
    """Test subscribing when subscribe returns an error code."""
    mock_client_instance = MockPahoClient.return_value
    mock_client_instance.is_connected.return_value = True
    mock_client_instance.subscribe.return_value = (paho_mqtt_client.MQTT_ERR_NO_CONN, 0)  # Example error

    with patch('mqtt_handler.MQTT_CONFIG', MQTT_CONFIG_MOCK_REAL):
        from mqtt_handler import MqttHandler
        handler = MqttHandler(test_mode=False)
        result, mid = handler.subscribe("test/error_sub", 0)

        mock_client_instance.subscribe.assert_called_once()
        assert f"Problem beim Anfragen des Abonnements für Topic 'test/error_sub'. RC: {paho_mqtt_client.MQTT_ERR_NO_CONN}" in caplog.text
        assert result == paho_mqtt_client.MQTT_ERR_NO_CONN
        assert mid == 0
