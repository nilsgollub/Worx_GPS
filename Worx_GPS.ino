#include <ArduinoMqttClient.h>
#include <WiFiNINA.h>
#include <TinyGPS++.h>
#include <SPI.h>
#include <SD.h>
#include "credentials.h" // WLAN-Anmeldeinformationen, MQTT-Einstellungen

// Global MQTT client declaration
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

// GPS-Einstellungen
TinyGPSPlus gps;
#define SerialGPS Serial1

// SD-Karten-Einstellungen
const int chipSelect = 4;
File dataFile;

// Speicherintervall für GPS-Daten (in Millisekunden)
const unsigned long gpsInterval = 2000;
unsigned long lastDataTime = 0; 

// Problemzonen (Anzahl und Koordinaten)
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

// Grundstücksgrenzen (als Arrays für einfachere Überprüfung)
const float latBounds[] = {46.811819, 46.812107};
const float lonBounds[] = {7.132838, 7.133173};

// Variablen für die Erkennung von Stehenbleiben
const float stationaryThreshold = 0.00005; 
const unsigned long stationaryTime = 5000; 
float lastLatitude = 0.0;
float lastLongitude = 0.0;
unsigned long lastMovementTime = 0;

// Variablen für die aktuelle Problemposition
float problemLatitude = 0.0;
float problemLongitude = 0.0;
bool problemDataAvailable = false;  // Flag, ob Problemdaten vorhanden sind

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
  randomSeed(millis()); // Zufallszahlengenerator neu setzen
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
  // SD-Karte initialisieren
  Serial.print("Initialisiere SD-Karte...");
  if (!SD.begin(chipSelect)) {
    Serial.println("Fehler bei der Initialisierung der SD-Karte!");
    while (true); // Endlosschleife bei Fehler
  }
  Serial.println("SD-Karte initialisiert.");

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
      // GPS-Daten als CSV speichern
      dataFile = SD.open("gps_data.csv", FILE_WRITE);
      if (dataFile) {
        Serial.print("Speichere GPS-Daten: "); // Debugging-Ausgabe
        Serial.print(latitude, 6);
        Serial.print(", ");
        Serial.print(longitude, 6);
        Serial.print(", ");
        Serial.println(timestamp);

        dataFile.print(latitude, 6); // 6 Nachkommastellen für Genauigkeit
        dataFile.print(",");
        dataFile.print(longitude, 6);
        dataFile.print(",");
        dataFile.println(timestamp);
        dataFile.flush(); // Puffer leeren nach jedem Schreibvorgang
        dataFile.close();
      } else {
        handleError("Fehler beim Öffnen der Datei auf der SD-Karte!", topicStatus, "error_sd_file");
      }
    }

    // Statusmeldung als CSV senden
    String statusMessage = String(latitude, 6) + "," + 
                          String(longitude, 6) + "," + 
                          String(millis()) + "," + 
                          String(satellites) + "," + 
                          String(isValid);
    sendMqttMessage(topicStatus, statusMessage);

    lastDataTime = millis();
  }

  // ... (Rest des Codes folgt in den nächsten Abschnitten)
}



void handleProblemCommand() {
  int satellites = 0;
  bool isValid = false;

  getGPSData(problemLatitude, problemLongitude, satellites, isValid);
  problemDataAvailable = true; // Markiere, dass Problemdaten vorhanden sind
}














