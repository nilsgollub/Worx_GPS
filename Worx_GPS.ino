#include <ArduinoMqttClient.h>
#include <WiFiNINA.h>
#include <TinyGPS++.h>
#include <ArduinoJson.h>

#include "credentials.h"
// MQTT-Einstellungen
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

// GPS-Einstellungen
TinyGPSPlus gps;
#define SerialGPS Serial1

// Speicherintervall für GPS-Daten (in Millisekunden)
const unsigned long gpsInterval = 2000;
unsigned long lastDataTime = 0; 

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

// Verbindungsstatus
bool isWifiConnected = false;
bool isMqttConnected = false;

// Dynamischer Speicher für GPS-Daten
DynamicJsonDocument gpsDoc(4096); 
JsonArray gpsDataArray = gpsDoc.createNestedArray();

// Grundstücksgrenzen (als Arrays für einfachere Überprüfung)
const float latBounds[] = {46.811819, 46.812107};
const float lonBounds[] = {7.132838, 7.133173};

// Variablen für die Erkennung von Stehenbleiben
const float stationaryThreshold = 0.00005; 
const unsigned long stationaryTime = 5000; 
float lastLatitude = 0.0;
float lastLongitude = 0.0;
unsigned long lastMovementTime = 0;
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

            int wifiConnectTimeout = 10000; 
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
// Funktion zum Generieren zufälliger GPS-Daten innerhalb der Grundstücksgrenzen
void generateFakeGPSData(float &latitude, float &longitude) {
  latitude = random(latBounds[0] * 1000000, latBounds[1] * 1000000) / 1000000.0;
  longitude = random(lonBounds[0] * 1000000, lonBounds[1] * 1000000) / 1000000.0;
}

// Funktion zum Abrufen von GPS-Daten (entweder echt oder simuliert)
void getGPSData(float &latitude, float &longitude, int &satellites, bool &isValid) {
  if (isFakeGPS) {
    generateFakeGPSData(latitude, longitude);
    satellites = random(1, 12); // Zufällige Anzahl Satelliten (1-12)
    isValid = true;
  } else {
    while (SerialGPS.available() > 0) {
      if (gps.encode(SerialGPS.read())) {
        if (gps.location.isValid() && gps.location.age() < 2000) {
          latitude = gps.location.lat();
          longitude = gps.location.lng();
          satellites = gps.satellites.value();
          isValid = true;
          return; // Gültige Daten gefunden, Funktion beenden
        } else {
          isValid = false;
        }
      }
    }
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
  gpsDataArray.clear();
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

  // GPS-Daten abrufen (entweder echt oder simuliert)
  if (millis() - lastDataTime >= gpsInterval) {
    float latitude = 0.0;
    float longitude = 0.0;
    int satellites = 0;
    bool isValid = false;
    getGPSData(latitude, longitude, satellites, isValid);
    unsigned long timestamp = millis();

    if (isRecording) {
      // GPS-Daten als JSON-Objekt formatieren (ohne Verschachtelung)
      JsonObject obj = gpsDoc.createNestedObject();
      obj["lat"] = latitude;
      obj["lon"] = longitude;
      obj["timestamp"] = timestamp;

      // JSON-Objekt zum gpsDataArray-Array hinzufügen
      gpsDataArray.add(obj);

      // Überprüfen, ob der Speicher fast voll ist
      if (gpsDoc.memoryUsage() > 0.8 * gpsDoc.capacity()) {
        handleError("Speicher fast voll!", topicStatus, "error_memory_full");
        isRecording = false; // Stoppe die Aufzeichnung, wenn der Speicher voll ist
      }
    }

    // Statusmeldung als JSON-Objekt mit Zeitstempel senden
    DynamicJsonDocument statusDoc(256);
    statusDoc["lat"] = latitude;
    statusDoc["lon"] = longitude;
    statusDoc["timestamp"] = timestamp;
    statusDoc["satellites"] = satellites;
    statusDoc["isValid"] = isValid;

    String statusMessage;
    serializeJson(statusDoc, statusMessage);
    sendMqttMessage(topicStatus, statusMessage); // Sende Status an topicStatus

    lastDataTime = millis();
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
          clearGPSData(); // Leere den Speicher am Anfang der Aufzeichnung
          Serial.println("Aufzeichnung gestartet.");
        } else if (payload == "stop") {
          isRecording = false;
          Serial.println("Aufzeichnung gestoppt.");
          // Sende alle gesammelten Daten auf einmal
          if (gpsDataArray.size() > 0) {
            String output;
            serializeJson(gpsDataArray, output);
            sendMqttMessage(topicGPS, output); // Sende GPS-Daten an topicGPS
            clearGPSData();
          }
        } else if (payload == "problem") {
          handleProblemCommand();
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
      // Sende alle gesammelten Daten auf einmal
      if (gpsDataArray.size() > 0) {
        String output;
        serializeJson(gpsDataArray, output);
        sendMqttMessage(topicGPS, output); // Sende GPS-Daten an topicGPS
        clearGPSData();
      }
    } else if (command == "problem") {
      handleProblemCommand();
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

  // GPS-Status anzeigen (nur wenn nicht im Fake-GPS-Modus)
  if (!isFakeGPS) {
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
  }
  delay(1000); // Kleine Verzögerung, um die Ausgabe lesbarer zu machen
}
// Funktion für die Problembehandlung
void handleProblemCommand() {
    float latitude = 0.0;
    float longitude = 0.0;
    int satellites = 0; // Variablen für Satelliten und Gültigkeit hinzufügen
    bool isValid = false;
    getGPSData(latitude, longitude, satellites, isValid); // Alle Parameter übergeben

    if (problemPositionCount < maxProblemPositions) {
        problemLatitudes[problemPositionCount] = latitude;
        problemLongitudes[problemPositionCount] = longitude;
        problemPositionCount++;
    } else {
        handleError("Maximale Anzahl Problempositionen erreicht!", topicStatus, "error_max_problems");
    }

    String problemData = "["; 
    for (int i = 0; i < problemPositionCount; i++) {
        // GPS-Daten als JSON-Objekt formatieren (ohne Verschachtelung)
        DynamicJsonDocument doc(128); 
        doc["lat"] = problemLatitudes[i];
        doc["lon"] = problemLongitudes[i];

        // JSON-Objekt zum problemData-Array hinzufügen
        serializeJson(doc, problemData);
        problemData += ",";
    }
    
    // Entferne das letzte Komma und füge die schließende Klammer hinzu
    problemData.remove(problemData.length() - 1); 
    problemData += "]";

    sendMqttMessage(topicStatus, problemData);
    if (isVerbose) {
        Serial.println("Problemmeldung gesendet.");
    }
}
