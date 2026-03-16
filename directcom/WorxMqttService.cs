using MQTTnet;
//using MQTTnet.Client;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json; // System.Text.Json für Serialisierung/Deserialisierung
using WorxMqttInterface.Json; // Namespace für unsere PositecJson-Klassen
using System.Collections.Concurrent;
using System.Web; // Für HttpUtility.UrlEncode

namespace WorxMqttInterface.Services
{
    public class WorxMqttService : IDisposable
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<WorxMqttService> _logger;
        private IMqttClient? _mqttClient;
        private OAuth? _oAuthToken;
        private DateTime _tokenExpiresAt;
        private List<ProductItem>? _products;
        private readonly ConcurrentDictionary<string, string> _latestMowerMessages = new(); // SN -> JSON Payload
        private Timer? _tokenRefreshTimer;

        // Konfigurationswerte (könnten aus appsettings.json kommen)
        private const string WorxApiPrefix = "WX"; // Für Worx Landroid
        private const string WorxLoginUrl = "https://id.worx.com/";
        private const string WorxApiUrl = "https://api.worxlandroid.com/api/v2/";
        private const string WorxClientId = "013132A8-DB34-4101-B993-3C8348EA0EBC"; // Client ID für Worx Landroid
        private string _appUuid;


        public WorxMqttService(ILogger<WorxMqttService> logger)
        {
            _logger = logger;
            _httpClient = new HttpClient();
            _appUuid = $"{Environment.MachineName.GetHashCode():X8}-{AppContext.BaseDirectory.GetHashCode():X8}-{Guid.NewGuid():N}";
            _logger.LogInformation("WorxMqttService initialized with App UUID: {AppUuid}", _appUuid);
        }

        public async Task<bool> LoginAsync(string email, string password)
        {
            var tokenUrl = $"{WorxLoginUrl}oauth/token";
            var payload = new Dictionary<string, string>
            {
                { "grant_type", "password" },
                { "client_id", WorxClientId },
                { "username", email },
                { "password", password },
                { "scope", "*" } // Oder spezifischer Scope falls bekannt
            };

            try
            {
                var response = await _httpClient.PostAsync(tokenUrl, new FormUrlEncodedContent(payload));
                var content = await response.Content.ReadAsStringAsync();

                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError("Login failed. Status: {StatusCode}, Response: {Response}", response.StatusCode, content);
                    return false;
                }

                _oAuthToken = JsonSerializer.Deserialize<OAuth>(content, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                if (_oAuthToken?.Access == null)
                {
                    _logger.LogError("Login failed: Access token not found in response.");
                    return false;
                }

                _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(_oAuthToken.Type ?? "Bearer", _oAuthToken.Access);
                _tokenExpiresAt = DateTime.UtcNow.AddSeconds(_oAuthToken.Expires - 60); // 60s Puffer
                _logger.LogInformation("Successfully logged in. Token expires at: {Expiration}", _tokenExpiresAt);

                // Token Refresh Timer starten
                ScheduleTokenRefresh();
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Exception during login.");
                return false;
            }
        }

        private void ScheduleTokenRefresh()
        {
            if (_oAuthToken == null) return;

            var dueTime = _tokenExpiresAt - DateTime.UtcNow;
            if (dueTime <= TimeSpan.Zero) dueTime = TimeSpan.FromSeconds(1); // Sofort versuchen, wenn schon abgelaufen

            _tokenRefreshTimer?.Dispose();
            _tokenRefreshTimer = new Timer(async _ => await RefreshTokenAsync(), null, dueTime, Timeout.InfiniteTimeSpan);
            _logger.LogInformation("Token refresh scheduled in {DueTime}", dueTime);
        }

        private async Task<bool> RefreshTokenAsync()
        {
            _logger.LogInformation("Attempting to refresh token...");
            if (_oAuthToken?.Refresh == null)
            {
                _logger.LogError("Cannot refresh token: No refresh token available.");
                return false;
            }

            var tokenUrl = $"{WorxLoginUrl}oauth/token";
            var payload = new Dictionary<string, string>
            {
                { "grant_type", "refresh_token" },
                { "client_id", WorxClientId },
                { "refresh_token", _oAuthToken.Refresh }
            };

            try
            {
                var response = await _httpClient.PostAsync(tokenUrl, new FormUrlEncodedContent(payload));
                var content = await response.Content.ReadAsStringAsync();

                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError("Token refresh failed. Status: {StatusCode}, Response: {Response}", response.StatusCode, content);
                    // Hier könnte ein erneuter Login erforderlich sein
                    _oAuthToken = null; // Ungültiges Token entfernen
                    return false;
                }

                var newOAuthToken = JsonSerializer.Deserialize<OAuth>(content, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                if (newOAuthToken?.Access == null)
                {
                    _logger.LogError("Token refresh failed: New access token not found.");
                    return false;
                }
                _oAuthToken = newOAuthToken;
                _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(_oAuthToken.Type ?? "Bearer", _oAuthToken.Access);
                _tokenExpiresAt = DateTime.UtcNow.AddSeconds(_oAuthToken.Expires - 60);
                _logger.LogInformation("Token successfully refreshed. New expiration: {Expiration}", _tokenExpiresAt);
                ScheduleTokenRefresh(); // Nächsten Refresh planen
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Exception during token refresh.");
                return false;
            }
        }

        private async Task<bool> EnsureTokenValidAsync()
        {
            if (_oAuthToken == null) return false; // Nicht eingeloggt
            if (DateTime.UtcNow >= _tokenExpiresAt)
            {
                _logger.LogInformation("Token expired or about to expire. Refreshing...");
                return await RefreshTokenAsync();
            }
            return true;
        }

        public async Task<List<ProductItem>?> GetProductsAsync()
        {
            if (!await EnsureTokenValidAsync()) // Token zuerst prüfen
            {
                _logger.LogError("Cannot get products: Token invalid.");
                return null;
            }
            // Die ursprüngliche Rekursionsgefahr in der Bedingung wurde entfernt.
            // Wenn _products null ist, wird es einfach versucht zu laden.
            // if (_products == null && await GetProductsAsync() == null)

            var productsUrl = $"{WorxApiUrl}product-items";
            try
            {
                var response = await _httpClient.GetAsync(productsUrl);
                var content = await response.Content.ReadAsStringAsync();
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError("Failed to get products. Status: {StatusCode}, Response: {Response}", response.StatusCode, content);
                    return null;
                }
                _products = JsonSerializer.Deserialize<List<ProductItem>>(content, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                _logger.LogInformation("Successfully fetched {ProductCount} products.", _products?.Count ?? 0);
                return _products;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Exception during product retrieval.");
                return null;
            }
        }

        public async Task<bool> ConnectMqttAsync(string serialNumber)
        {
            if (_products == null) // Sicherstellen, dass Produkte geladen sind
            {
                _logger.LogInformation("Products not yet loaded. Fetching products before MQTT connect...");
                await GetProductsAsync();
                if (_products == null)
                {
                     _logger.LogError("Cannot connect MQTT: Failed to load products.");
                     return false;
                }
            }

            var mower = _products?.FirstOrDefault(p => p.SerialNo == serialNumber);
            if (mower == null || mower.Endpoint == null || mower.Topic?.CmdOut == null || _oAuthToken?.Access == null)
            {
                _logger.LogError("Cannot connect MQTT: Mower data incomplete or not logged in. Mower: {@Mower}, Token: {HasToken}", mower, _oAuthToken?.Access != null);
                return false;
            }

            if (!await EnsureTokenValidAsync())
            {
                 _logger.LogError("Cannot connect MQTT: Token invalid for MQTT connection.");
                return false;
            }

            var factory = new MqttFactory();
            _mqttClient = factory.CreateMqttClient();

            var tps = _oAuthToken.Access.Split('.');
            if (tps.Length != 3) {
                _logger.LogError("Invalid JWT format for MQTT credentials.");
                return false;
            }
            // Wichtig: Die einzelnen Teile des Tokens müssen URL-kodiert sein, bevor sie zusammengesetzt werden.
            var mqttUsername = $"da?jwt={HttpUtility.UrlEncode(tps[0])}.{HttpUtility.UrlEncode(tps[1])}&x-amz-customauthorizer-signature={HttpUtility.UrlEncode(tps[2])}";

            var clientId = $"{WorxApiPrefix}/USER/{mower.UserId}/AvaDeskApp/{_appUuid}"; // Angelehnt an AvaDeskApp

            var options = new MqttClientOptionsBuilder()
                .WithTcpServer(mower.Endpoint, mower.MqttPort > 0 ? mower.MqttPort : 443) // Port 443 ist Standard für TLS
                .WithClientId(clientId)
                .WithCredentials(mqttUsername, null) // Kein separates Passwort
                .WithTlsOptions(o => {
                    o.UseTls = true;
                    o.SslProtocol = System.Security.Authentication.SslProtocols.Tls12;
                    // Für Produktivumgebungen sollten Zertifikate validiert werden.
                    // Für lokale Tests oder wenn der Broker ein selbstsigniertes Zertifikat hat:
                    o.AllowUntrustedCertificates = true;
                    o.IgnoreCertificateChainErrors = true;
                    o.IgnoreCertificateRevocationErrors = true;
                 })
                .WithCleanSession(true)
                .Build();

            _mqttClient.ApplicationMessageReceivedAsync += e =>
            {
                var payload = Encoding.UTF8.GetString(e.ApplicationMessage.PayloadSegment);
                _logger.LogInformation("MQTT Message Received on topic {Topic}: {Payload}", e.ApplicationMessage.Topic, payload);
                if (mower.SerialNo != null) // Null-Check für SerialNo
                {
                    _latestMowerMessages[mower.SerialNo] = payload; // Speichere die letzte Nachricht
                }
                return Task.CompletedTask;
            };

            _mqttClient.DisconnectedAsync += async e =>
            {
                _logger.LogWarning(e.Exception, "Disconnected from MQTT broker. Reason: {Reason}. Trying to reconnect...", e.Reason);
                await Task.Delay(TimeSpan.FromSeconds(5)); // Warte kurz vor dem Neuverbindungsversuch
                try
                {
                    if (_mqttClient != null && !_mqttClient.IsConnected) // Nur wenn nicht schon wieder verbunden
                    {
                         await _mqttClient.ConnectAsync(options, CancellationToken.None); // Erneuter Verbindungsversuch
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Reconnect failed.");
                }
            };

            try
            {
                await _mqttClient.ConnectAsync(options, CancellationToken.None);
                _logger.LogInformation("Successfully connected to MQTT broker for mower {SerialNumber}.", serialNumber);
                await _mqttClient.SubscribeAsync(new MqttTopicFilterBuilder().WithTopic(mower.Topic.CmdOut).Build());
                _logger.LogInformation("Subscribed to topic: {Topic}", mower.Topic.CmdOut);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to connect or subscribe to MQTT broker for mower {SerialNumber}.", serialNumber);
                return false;
            }
        }

        public async Task<bool> SendCommandAsync(string serialNumber, string commandJson)
        {
            if (_mqttClient == null || !_mqttClient.IsConnected)
            {
                _logger.LogError("Cannot send command: MQTT client not connected.");
                return false;
            }

            var mower = _products?.FirstOrDefault(p => p.SerialNo == serialNumber);
            if (mower?.Topic?.CmdIn == null)
            {
                _logger.LogError("Cannot send command: Command_in topic not found for mower {SerialNumber}.", serialNumber);
                return false;
            }

            var message = new MqttApplicationMessageBuilder()
                .WithTopic(mower.Topic.CmdIn)
                .WithPayload(commandJson)
                .WithQualityOfServiceLevel(MQTTnet.Protocol.MqttQualityOfServiceLevel.AtLeastOnce)
                .Build();

            try
            {
                var result = await _mqttClient.PublishAsync(message, CancellationToken.None);
                if (result.IsSuccess)
                {
                    _logger.LogInformation("Successfully sent command to {Topic}: {Command}", mower.Topic.CmdIn, commandJson);
                    return true;
                }
                else
                {
                    _logger.LogError("Failed to send command. Reason: {ReasonCode} - {ReasonString}", result.ReasonCode, result.ReasonString);
                    return false;
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Exception while sending MQTT command.");
                return false;
            }
        }

        public string? GetLatestMowerData(string serialNumber)
        {
            _latestMowerMessages.TryGetValue(serialNumber, out var data);
            return data;
        }

        public void Dispose()
        {
            _logger.LogInformation("Disposing WorxMqttService.");
            _tokenRefreshTimer?.Dispose();
            _mqttClient?.Dispose();
            _httpClient?.Dispose();
            GC.SuppressFinalize(this); // Hinzugefügt für korrekte IDisposable Implementierung
        }
    }
}
