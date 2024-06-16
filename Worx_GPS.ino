#include <ArduinoMqttClient.h>
#include <WiFiNINA.h>
#include <TinyGPS++.h>

// Einbinden der Anmeldeinformationen aus credentials.h
#include "credentials.h"

// MQTT-Einstellungen
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

// GPS-Einstellungen
TinyGPSPlus gps;
#define SerialGPS Serial1

// Speicherintervall für GPS-Daten (in Millisekunden)
const unsigned long gpsInterval = 2000;
unsigned long lastGPStime = 0;

// Speicher für Problemzonen (dynamische Größe)
const int maxProblemPositions = 10;
float problemLatitudes[maxProblemPositions];
float problemLongitudes[maxProblemPositions];
int problemPositionCount = 0;

// Flags und Variablen
bool isRecording = false;
bool isVerbose = true;
bool checkBoundaries = true;
bool isFakeGPS = true;
unsigned long lastFakeGPStime = 0;

// Verbindungsstatus
bool isWifiConnected = false;
bool isMqttConnected = false;

// Dynamischer Speicher für GPS-Daten
String gpsData = "";

// Grundstücksgrenzen (als Arrays für einfachere Überprüfung)
const float latBounds[] = {46.811819, 46.812107};
const float lonBounds[] = {7.132838, 7.133173};
// Funktion zum Verbinden mit WLAN (mit Timeout)
void connectToWiFi() {
    isWifiConnected = false;
    int connectionAttempts = 0;
    unsigned long lastConnectAttempt = 0;

    while (!isWifiConnected && connectionAttempts < numNetworks) {
        if (millis() - lastConnectAttempt > 5000) {
            Serial.print("Verbinde mit ");
            Serial.println(ssid[connectionAttempts]);
            WiFi.begin(ssid[connectionAttempts], pass[connectionAttempts]);

            int wifiConnectTimeout = 10000; // Timeout in Millisekunden
            unsigned long startTime = millis();

            while (WiFi.status() != WL_CONNECTED && (millis() - startTime) < wifiConnectTimeout) {
                delay(500);
            }

            if (WiFi.status() == WL_CONNECTED) {
                isWifiConnected = true;
                Serial.println("WLAN verbunden!");
                Serial.print("IP-Adresse: ");
                Serial.println(WiFi.localIP());
            } else {
                connectionAttempts++;
            }

            lastConnectAttempt = millis();
        }
    }

    if (!isWifiConnected) {
        Serial.println("Verbindung zu allen WLAN-Netzwerken fehlgeschlagen.");
    }
}

// Funktion zum Verbinden mit MQTT
void connectToMqtt() {
    isMqttConnected = false;

    if (isWifiConnected) {
        Serial.print("Verbinde mit MQTT Broker: ");
        Serial.println(broker);

        // Client-ID festlegen (vor dem Verbinden!)
        mqttClient.setId("RasenmaeherRoboter_12345");

        mqttClient.setUsernamePassword(user, password);

        while (!mqttClient.connect(broker, port)) {
            Serial.print(".");
            delay(500);
        }

        if (mqttClient.connected()) {
            isMqttConnected = true;
            Serial.println("MQTT verbunden!");

            // Abonnieren der Steuerungs-Topics
            mqttClient.subscribe(topicControl);
            Serial.print("Abonniert: ");
            Serial.println(topicControl);
        } else {
            Serial.println("MQTT-Verbindung fehlgeschlagen.");
        }
    }
}
// Funktion zum Verarbeiten von GPS-Daten (mit Grenzwertprüfung und Speicherung)
// Funktion zum Verarbeiten von GPS-Daten (mit Grenzwertprüfung, Speicherung und Zeitstempel)
void processGPS() {
    while (SerialGPS.available() > 0) {
        if (gps.encode(SerialGPS.read())) {
            if (gps.location.isValid() && gps.location.age() < 2000) {
                float latitude = gps.location.lat();
                float longitude = gps.location.lng();
                unsigned long timestamp = millis(); // Zeitstempel in Millisekunden

                if (checkBoundaries && !isInsideBoundaries(latitude, longitude)) {
                    if (isVerbose) {
                        Serial.println("GPS-Daten außerhalb der Grundstücksgrenzen verworfen.");
                    }
                    continue; // GPS-Daten verwerfen, wenn sie außerhalb der Grenzen liegen
                }

                if (isRecording) {
                    gpsData += String(latitude, 6) + "," + String(longitude, 6) + "," + String(timestamp) + ";";
                }

                // Statusmeldung mit aktuellen GPS-Daten und Zeitstempel senden
                sendMqttMessage(topicStatus, String("GPS: ") + String(latitude, 6) + ", " + String(longitude, 6) + ", " + String(timestamp));
            } else {
                handleError("Ungültige GPS-Daten!", topicStatus, "error_gps_invalid");
            }
        }
    }
}

// Funktion zum Generieren zufälliger GPS-Daten innerhalb der Grundstücksgrenzen (mit Zeitstempel)
void generateFakeGPS() {
    if (millis() - lastFakeGPStime >= gpsInterval) {
        float lat = random(latBounds[0] * 1000000, latBounds[1] * 1000000) / 1000000.0;
        float lon = random(lonBounds[0] * 1000000, lonBounds[1] * 1000000) / 1000000.0;
        unsigned long timestamp = millis(); // Zeitstempel in Millisekunden

        if (isRecording) {
            gpsData += String(lat, 6) + "," + String(lon, 6) + "," + String(timestamp) + ";";
        }

        // Problemposition mit Zeitstempel speichern (nur im Fake-GPS-Modus)
        if (problemPositionCount < maxProblemPositions) {
            problemLatitudes[problemPositionCount] = lat;
            problemLongitudes[problemPositionCount] = lon;
            // Hier fehlt die Speicherung des Zeitstempels für Problempositionen, da kein Array dafür vorgesehen ist.
            problemPositionCount++;
        } else {
            handleError("Maximale Anzahl Problempositionen erreicht!", topicStatus, "error_max_problems");
        }

        lastFakeGPStime = millis();
    }
}

// Funktion zum Versenden von MQTT-Nachrichten
void sendMqttMessage(const String& topic, const String& payload) {
    if (mqttClient.connected()) {
        mqttClient.beginMessage(topic);
        mqttClient.print(payload);
        mqttClient.endMessage();
        if (isVerbose) {
            Serial.print("MQTT-Nachricht gesendet an ");
            Serial.print(topic);
            Serial.print(": ");
            Serial.println(payload);
        }
    } else {
        if (isVerbose) {
            Serial.println("MQTT nicht verbunden. Nachricht nicht gesendet.");
        }
    }
}

// Funktion zum Leeren des GPS-Datenspeichers
void clearGPSData() {
    gpsData = "";
}

// Funktion zur Überprüfung, ob Koordinaten innerhalb der Grundstücksgrenzen liegen
bool isInsideBoundaries(float lat, float lon) {
    return (lat >= latBounds[0] && lat <= latBounds[1] && lon >= lonBounds[0] && lon <= lonBounds[1]);
}

// Funktion zur Fehlerbehandlung
void handleError(const String& message, const String& topic, const String& errorCode) {
    if (isVerbose) {
        Serial.println(message);
    }
    sendMqttMessage(topic, errorCode);
}

void setup() {
    Serial.begin(9600);
    SerialGPS.begin(9600);
    if (isVerbose) {
        Serial.println("Serielle Kommunikation und GPS initialisiert");
    }

    connectToWiFi();
    connectToMqtt();
}
void loop() {
    // WLAN- und MQTT-Verbindung prüfen und ggf. wiederherstellen
    if (!isWifiConnected) {
        connectToWiFi();
    }
    if (isWifiConnected && !isMqttConnected) {
        connectToMqtt();
    }

    // MQTT-Nachrichten verarbeiten
    if (isMqttConnected) {
        mqttClient.poll();
        if (mqttClient.available()) {
            String topic = mqttClient.messageTopic();
            String payload = mqttClient.readString();
            Serial.println("MQTT-Nachricht empfangen:");
            Serial.print("  Topic: ");
            Serial.println(topic);
            Serial.print("  Payload: ");
            Serial.println(payload);

            if (topic == topicControl) {
                if (payload == "start") {
                    isRecording = true;
                    clearGPSData();
                    Serial.println("Aufzeichnung gestartet.");
                } else if (payload == "stop") {
                    isRecording = false;
                    Serial.println("Aufzeichnung gestoppt.");
                    sendMqttMessage(topicGPS, gpsData);
                    clearGPSData();
                    for (int i = 0; i < problemPositionCount; i++) {
                        String problemData = String(problemLatitudes[i], 6) + "," + String(problemLongitudes[i], 6);
                        sendMqttMessage(topicStatus, problemData);
                    }
                    problemPositionCount = 0; // Problemzonen-Zähler zurücksetzen
                } else if (payload == "problem") {
                    handleProblemCommand(); // Funktion für Problembehandlung
                } else if (payload == "fakegps_on") {
                    isFakeGPS = true;
                    Serial.println("Fake GPS Modus aktiviert.");
                } else if (payload == "fakegps_off") {
                    isFakeGPS = false;
                    Serial.println("Fake GPS Modus deaktiviert.");
                } else {
                    if (isVerbose) {
                        Serial.println("Unbekannter Befehl empfangen.");
                    }
                }
            }
        }
    }

    // Serielle Befehle verarbeiten (ähnlich wie MQTT-Verarbeitung)
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();

        if (command == "start") {
            isRecording = true;
            clearGPSData();
            if (isVerbose) {
                Serial.println("Aufzeichnung (seriell) gestartet.");
            }
        } else if (command == "stop") {
            isRecording = false;
            if (isVerbose) {
                Serial.println("Aufzeichnung (seriell) gestoppt.");
            }
            sendMqttMessage(topicGPS, gpsData);
            clearGPSData();
            for (int i = 0; i < problemPositionCount; i++) {
                String problemData = String(problemLatitudes[i], 6) + "," + String(problemLongitudes[i], 6);
                sendMqttMessage(topicStatus, problemData);
            }
            problemPositionCount = 0; // Problemzonen-Zähler zurücksetzen
        } else if (command == "problem") {
            handleProblemCommand(); // Funktion für Problembehandlung
        } else if (command == "verbose") {
            isVerbose = !isVerbose; // verbose Modus umschalten
            Serial.print("Ausführliche Ausgabe ");
            Serial.println(isVerbose ? "aktiviert" : "deaktiviert");
        } else if (command == "fakegps_on") {
            isFakeGPS = true;
            Serial.println("Fake GPS Modus aktiviert.");
        } else if (command == "fakegps_off") {
            isFakeGPS = false;
            Serial.println("Fake GPS Modus deaktiviert.");
        } else {
            if (isVerbose) {
                Serial.println("Unbekannter Befehl empfangen.");
            }
        }

        // Seriellen Eingabepuffer leeren
        while (Serial.available() > 0) {
            Serial.read();
        }
    }

    // GPS-Daten verarbeiten (entweder echt oder fake)
    if (isRecording) {
        if (isFakeGPS) {
            generateFakeGPS();
        } else {
            processGPS();
        }
    }

    // GPS-Status anzeigen
    Serial.print("Satelliten: ");
    Serial.println(gps.satellites.value());
    if (gps.location.isValid()) {
        Serial.print("Latitude: ");
        Serial.println(gps.location.lat(), 6);
        Serial.print("Longitude: ");
        Serial.println(gps.location.lng(), 6);
    } else {
        Serial.println("Keine gültigen GPS-Daten");
    }
    delay(1000); // Kleine Verzögerung, um die Ausgabe lesbarer zu machen
}

// Funktion für die Problembehandlung (ausgelagert aus loop())
void handleProblemCommand() {
    if (isFakeGPS) {
        generateFakeGPS();
        String problemData = String(problemLatitudes[problemPositionCount - 1], 6) + "," + String(problemLongitudes[problemPositionCount - 1], 6);
        sendMqttMessage(topicStatus, problemData);
        if (isVerbose) {
            Serial.println("Problemmeldung (Fake GPS) gesendet.");
        }
    } else {
        if (gps.location.isValid()) {
            if (problemPositionCount < maxProblemPositions) {
                problemLatitudes[problemPositionCount] = gps.location.lat();
                problemLongitudes[problemPositionCount] = gps.location.lng();
                problemPositionCount++;
            } else {
                handleError("Maximale Anzahl Problempositionen erreicht!", topicStatus, "error_max_problems");
            }
            String problemData = String(problemLatitudes[problemPositionCount - 1], 6) + "," + String(problemLongitudes[problemPositionCount - 1], 6);
            sendMqttMessage(topicStatus, problemData);
            if (isVerbose) {
                Serial.println("Problemmeldung gesendet.");
            }
        } else {
            handleError("Keine gültigen GPS-Daten für Problemmeldung verfügbar.", topicStatus, "error_no_gps");
        }
    }
}
