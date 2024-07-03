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
const unsigned long gpsInterval = 500;
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
bool isFakeGPS = false;

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

    if (isValid && (!checkBoundaries || isInsideBoundaries(latitude, longitude))) {
      // Nur gültige Daten innerhalb der Grundstücksgrenzen speichern und senden
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
          dataFile.print(latitude, 6);
          dataFile.print(",");
          dataFile.print(longitude, 6);
          dataFile.print(",");
          dataFile.println(timestamp);
          dataFile.flush();
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
    } else {
      Serial.println("Ungültige GPS-Daten verworfen.");  // Optionale Log-Ausgabe
    }

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
          // Leere die Datei am Anfang der Aufzeichnung, um alte Daten zu entfernen
          dataFile = SD.open("gps_data.csv", FILE_WRITE);
          dataFile.close();
          Serial.println("Aufzeichnung gestartet.");
        } else if (payload == "stop" && isRecording) {
          isRecording = false;
          Serial.println("Aufzeichnung gestoppt.");

          // Datei schließen und erneut öffnen (Lesen)
          dataFile.close(); // Sicherstellen, dass die Datei geschlossen ist
          dataFile = SD.open("gps_data.csv", FILE_READ);

          // Daten von der SD-Karte lesen und in einem String speichern
          if (dataFile) {
            dataFile.seek(0); // Setze den Dateizeiger auf den Anfang
            String csvData = "";
            while (dataFile.available()) {
              csvData += (char)dataFile.read();
            }
            dataFile.close(); // Datei schließen nach dem Lesen

            // Gesamte CSV-Datei in einer Nachricht senden
            Serial.print("Sende Daten: "); // Debugging-Ausgabe
            Serial.println(csvData);
            sendMqttMessage(topicGPS, csvData);
            Serial.println("GPS-Daten gesendet.");

            // Datei löschen nach dem Senden
            SD.remove("gps_data.csv");
            Serial.println("Datei gelöscht.");
          } else {
            handleError("Fehler beim Öffnen der Datei auf der SD-Karte!", topicStatus, "error_sd_file");
          }
        } else if (payload == "problem") {
          handleProblemCommand();
        } else if (payload == "restart") { // Neustart-Befehl
          Serial.println("Neustart-Befehl empfangen. Starte neu...");
          delay(1000); // Kurze Verzögerung, um die Nachricht auszugeben
          NVIC_SystemReset(); // Neustart des Arduino
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
      // Leere die Datei am Anfang der Aufzeichnung, um alte Daten zu entfernen
      dataFile = SD.open("gps_data.csv", FILE_WRITE);
      dataFile.close();
      if (isVerbose) {
        Serial.println("Aufzeichnung (seriell) gestartet.");
      }
    } else if (command == "stop") {
      isRecording = false;
      if (isVerbose) {
        Serial.println("Aufzeichnung (seriell) gestoppt.");
      }

      // Datei schließen und erneut öffnen (Lesen)
      dataFile.close(); // Sicherstellen, dass die Datei geschlossen ist
      dataFile = SD.open("gps_data.csv", FILE_READ);

      // Daten von der SD-Karte lesen und in einem String speichern
      if (dataFile) {
        dataFile.seek(0); // Setze den Dateizeiger auf den Anfang
        String csvData = "";
        while (dataFile.available()) {
          csvData += (char)dataFile.read();
        }
        dataFile.close(); // Datei schließen nach dem Lesen

        // Gesamte CSV-Datei in einer Nachricht senden
        Serial.print("Sende Daten: "); // Debugging-Ausgabe
        Serial.println(csvData);
        sendMqttMessage(topicGPS, csvData);
        Serial.println("GPS-Daten gesendet.");

        // Datei löschen nach dem Senden
        SD.remove("gps_data.csv");
        Serial.println("Datei gelöscht.");
      } else {
        handleError("Fehler beim Öffnen der Datei auf der SD-Karte!", topicStatus, "error_sd_file");
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

  // Problemdaten verarbeiten und senden, falls vorhanden und Aufzeichnung nicht aktiv
  if (problemDataAvailable && !isRecording) {
    // Problemzonen als CSV speichern (O_WRITE | O_CREAT | O_TRUNC verwenden)
    File problemDataFile = SD.open("problem_zones.csv", O_WRITE | O_CREAT | O_TRUNC);
    if (problemDataFile) {
      problemDataFile.print(problemLatitude, 6);
      problemDataFile.print(",");
      problemDataFile.println(problemLongitude, 6); // Nur Lat und Lon speichern
      problemDataFile.flush();
      problemDataFile.close();
      Serial.println("Problemzonen in Datei gespeichert."); // Debugging-Ausgabe
    } else {
      Serial.print("Fehler beim Öffnen der Problemzonen-Datei: ");
      Serial.println(problemDataFile.getWriteError());
      handleError("Fehler beim Öffnen der Problemzonen-Datei auf der SD-Karte!", topicStatus, "error_sd_file_problem");
    }

    // Problemmeldung als CSV senden (nur Lat und Lon)
    String problemData = "problem," + String(problemLatitude, 6) + "," + String(problemLongitude, 6);
    sendMqttMessage(topicStatus, problemData);
    if (isVerbose) {
      Serial.println("Problemmeldung gesendet.");
    }

    // Datei nach dem Senden löschen und Verzögerung hinzufügen
    delay(100); // Verzögerung nach dem Schließen
    if (SD.remove("problem_zones.csv")) {
      Serial.println("Problemzonen-Datei gelöscht.");
    } else {
      Serial.println("Fehler beim Löschen der Problemzonen-Datei!");
    }
    problemDataAvailable = false; // Problemdaten wurden verarbeitet
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

void handleProblemCommand() {
  int satellites = 0;
  bool isValid = false;

  getGPSData(problemLatitude, problemLongitude, satellites, isValid);
  problemDataAvailable = true; // Markiere, dass Problemdaten vorhanden sind
}














