#include <ArduinoMqttClient.h>
#include <WiFiNINA.h>
#include <ArduinoJson.h>
#include <TinyGPS++.h>
#include "credentials.h"

// WLAN-Zugangsdaten
const int numNetworks = sizeof(ssid) / sizeof(ssid[0]);

// MQTT-Einstellungen
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

// GPS-Variablen
TinyGPSPlus gps;
const int GPSBaud = 9600;
float latitude = 0.0;
float longitude = 0.0;
bool gpsFix = false;
bool fakeGpsMode = false;
bool serialOutput = true;
unsigned long lastGpsTime = 0;
const int gpsInterval = 2; // Sekunden
bool maehenAktiv = false;
bool problemDetected = false;

// Grundstücksgrenzen
const float minLatitude = 46.811819;
const float maxLatitude = 46.812107;
const float minLongitude = 7.132838;
const float maxLongitude = 7.133173;

// Speicher für GPS-Daten und Problemkoordinaten im RAM
const int maxGpsPoints = 10000; // Maximale Anzahl an GPS-Punkten
struct GpsPoint {
  float lat;
  float lon;
  unsigned long timestamp;
};
GpsPoint gpsData[maxGpsPoints];
int currentGpsIndex = 0;

float problemLatitude = 0.0;
float problemLongitude = 0.0;

// Neue Variablen für Stillstandserkennung
unsigned long lastMovementTime = 0;
const unsigned long movementTimeout = 10000; // Timeout in Millisekunden (10 Sekunden)
float lastLatitude = 0.0;
float lastLongitude = 0.0;
const float movementThreshold = 0.00001; // Bewegungsschwelle (anpassen!)
void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ; // Warten auf serielle Verbindung
  }
  if (serialOutput) {
    Serial.println("Starting Worx Mower GPS Tracker...");
  }

  // GPS initialisieren
  Serial1.begin(GPSBaud);

  // WLAN-Verbindung herstellen
  int currentNetwork = 0;
  if (serialOutput) {
    Serial.print("Connecting to WiFi");
  }
  while (WiFi.status() != WL_CONNECTED) {
    if (serialOutput) {
      Serial.print(".");
    }
    WiFi.begin(ssid[currentNetwork], pass[currentNetwork]);
    delay(5000); // Warte 5 Sekunden, bevor zum nächsten Netzwerk gewechselt wird
    currentNetwork = (currentNetwork + 1) % numNetworks;
  }
  if (serialOutput) {
    Serial.println("\nConnected to WiFi");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
  }

  // MQTT-Verbindung herstellen
  mqttClient.setUsernamePassword(username, password);
  if (serialOutput) {
    Serial.print("Connecting to MQTT broker ");
  }
  while (!mqttClient.connect(broker, port)) {
    if (serialOutput) {
      Serial.print(".");
    }
    delay(2500);
  }
  if (serialOutput) {
    Serial.println(" connected!");
  }

  // MQTT-Nachrichten-Handler registrieren und Topics abonnieren
  mqttClient.onMessage(onMqttMessage);
  mqttClient.subscribe(topicControl);
}
void loop() {
  mqttClient.poll();
  getGpsData();
  handleSerialInput();

  if (maehenAktiv) {
    checkMovement(); 
    if (gpsFix && isInsideBoundaries(latitude, longitude)) {
      recordGpsData();
    }
  } else if (fakeGpsMode) {
    simulateGpsData();
  }

  // Überprüfe und sende gespeicherte Problemdaten
  sendProblemData();
}

void getGpsData() {
  while (Serial1.available() > 0) {
    if (gps.encode(Serial1.read())) {
      if (gps.location.isValid()) {
        latitude = gps.location.lat();
        longitude = gps.location.lng();
        gpsFix = true;
        lastGpsTime = millis(); 
        if (serialOutput) {
          Serial.print("GPS: ");
          Serial.print(latitude, 6); 
          Serial.print(", ");
          Serial.println(longitude, 6);
        }
      } else {
        gpsFix = false;
      }
    }
  }
}
void checkMovement() {
  if (gpsFix) {
    float distance = TinyGPSPlus::distanceBetween(
      lastLatitude, lastLongitude,
      latitude, longitude
    );

    if (distance > movementThreshold) {
      lastMovementTime = millis();
      lastLatitude = latitude;
      lastLongitude = longitude;
    } else {
      if (millis() - lastMovementTime > movementTimeout) {
        static unsigned long lastProblemTime = 0;
        const unsigned long problemTimeout = 5000; // Timeout in Millisekunden

        if (millis() - lastProblemTime > problemTimeout) {
          if (!problemDetected) {
            problemDetected = true;
            if (serialOutput) {
              Serial.println("Problem detected (no movement)!");
            }
            // GPS-Position bei Problem speichern
            problemLatitude = latitude;
            problemLongitude = longitude;
          }
          lastProblemTime = millis();
        }
      }
    }
  }
}
void recordGpsData() {
  // GPS-Daten im RAM speichern
  if (currentGpsIndex < maxGpsPoints) {
    gpsData[currentGpsIndex].lat = latitude;
    gpsData[currentGpsIndex].lon = longitude;
    gpsData[currentGpsIndex].timestamp = lastGpsTime;
    currentGpsIndex++;
  } else {
    if (serialOutput) {
      Serial.println("GPS data buffer full!");
    }
  }
}

void sendGpsData() {
  // GPS-Daten aus dem RAM per MQTT senden
  if (mqttClient.connected()) {
    DynamicJsonDocument doc(2048); // Größeres JSON-Dokument für alle GPS-Punkte
    JsonArray data = doc.createNestedArray("data");
    for (int i = 0; i < currentGpsIndex; i++) {
      JsonObject point = data.createNestedObject();
      point["lat"] = gpsData[i].lat;
      point["lon"] = gpsData[i].lon;
      point["timestamp"] = gpsData[i].timestamp;
    }
    char jsonBuffer[2048];
    serializeJson(doc, jsonBuffer);
    mqttClient.beginMessage(topicGps);
    mqttClient.print(jsonBuffer);
    mqttClient.endMessage();

    // RAM-Puffer leeren
    currentGpsIndex = 0;
  } else {
    if (serialOutput) {
      Serial.println("MQTT not connected. Cannot send GPS data.");
    }
  }
}

void sendProblemData() {
  // Sende die aktuelle Problemposition (lat, lon) per MQTT, wenn eine Verbindung besteht und ein Problem erkannt wurde
  if (problemDetected && mqttClient.connected()) {
    DynamicJsonDocument doc(200);
    doc["lat"] = problemLatitude;
    doc["lon"] = problemLongitude;
    doc["timestamp"] = millis();
    doc["command"] = "problem";
    char jsonBuffer[256];
    serializeJson(doc, jsonBuffer);
    mqttClient.beginMessage(topicStatus);
    mqttClient.print(jsonBuffer);
    mqttClient.endMessage();

    // Problem als gesendet markieren
    problemDetected = false;
  }
}
void onMqttMessage(int messageSize) {
  // Verarbeite eingehende MQTT-Nachrichten
  if (mqttClient.messageTopic() == topicControl) {
    String payload = mqttClient.readString();
    if (serialOutput) {
      Serial.print("MQTT message received: ");
      Serial.println(payload);
    }
    if (payload == "start") {
      maehenAktiv = true;
      if (serialOutput) {
        Serial.println("Start recording GPS data");
      }
    } else if (payload == "stop") {
      maehenAktiv = false;
      if (serialOutput) {
        Serial.println("Stop recording and send GPS data");
      }
      sendGpsData();
    } else if (payload == "laden") {
      if (serialOutput) {
        Serial.println("Clear problem data");
      }
      problemLatitude = 0.0;
      problemLongitude = 0.0;
    } else if (payload == "fakegps_on") {
      fakeGpsMode = true;
    } else if (payload == "fakegps_off") {
      fakeGpsMode = false;
    } else if (payload == "serial_on") {
      serialOutput = true;
    } else if (payload == "serial_off") {
      serialOutput = false;
    } else {
      if (serialOutput) {
        Serial.println("Unknown command");
      }
    }
  }
}

void simulateGpsData() {
  // Simuliere GPS-Daten, wenn kein GPS-Empfang möglich ist
  static unsigned long lastSimulatedGpsTime = 0;
  if (millis() - lastSimulatedGpsTime > gpsInterval) {
    latitude += random(-0.00005, 0.00005); 
    longitude += random(-0.00005, 0.00005); 
    lastSimulatedGpsTime = millis();
    if (serialOutput) {
      Serial.print("Simulated GPS: ");
      Serial.print(latitude, 6);
      Serial.print(", ");
      Serial.println(longitude, 6);
    }
  }
}


void handleSerialInput() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command == "start") {
      maehenAktiv = true;
      if (serialOutput) {
        Serial.println("Start recording GPS data");
      }
    } else if (command == "stop") {
      maehenAktiv = false;
      if (serialOutput) {
        Serial.println("Stop recording and send GPS data");
      }
      sendGpsData();
    } else if (command == "laden") {
      if (serialOutput) {
        Serial.println("Clear problem data");
      }
      problemLatitude = 0.0;
      problemLongitude = 0.0;
    } else if (command == "fakegps_on") {
      fakeGpsMode = true;
    } else if (command == "fakegps_off") {
      fakeGpsMode = false;
    } else if (command == "serial_on") {
      serialOutput = true;
    } else if (command == "serial_off") {
      serialOutput = false;
    } else {
      if (serialOutput) {
        Serial.println("Unknown command");
      }
    }
  }
}

bool isInsideBoundaries(float lat, float lon) {
  return (lat >= minLatitude && lat <= maxLatitude && lon >= minLongitude && lon <= maxLongitude);
}
