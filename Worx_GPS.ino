#include <ArduinoMqttClient.h>
#include <WiFiNINA.h>
#include <Arduino_LSM9DS1.h>
#include <SPI.h>
#include <SD.h>
#include <ArduinoJson.h>
#include <TinyGPS++.h>

// WLAN-Zugangsdaten
const char* ssid[] = {"Skynet2", "Skynet", "NiniHotspot"};
const char* pass[] = {"JhiswenP3003!", "JhiswenP3003!", "JhiswenP3003!"};
const int numNetworks = sizeof(ssid) / sizeof(ssid[0]);

// MQTT-Einstellungen
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);
const char broker[] = "192.168.1.117";
int port = 1883;
const char topicControl[] = "worx/control";
const char topicGps[] = "worx/gps";
const char topicStatus[] = "worx/status";
const char* username = "nilsgollub";
const char* password = "JhiswenP3003!";

// GPS und IMU Variablen
TinyGPSPlus gps;
const int GPSBaud = 9600; // GPS Baudrate als Konstante
float latitude = 0.0;
float longitude = 0.0;
bool gpsFix = false;
bool fakeGpsMode = false; // Flag für Fake GPS Modus
bool serialOutput = true; // Flag für Serial Monitor Ausgabe
unsigned long lastGpsTime = 0;
const int gpsInterval = 2; 
float imuThreshold = 0.5; // Bewegungsschwelle für IMU (anpassen!)
bool maehenAktiv = false;
bool problemDetected = false;

// SD-Karte
const int chipSelect = 4;
File dataFile;

// Grundstücksgrenzen 
const float minLatitude = 46.811819;
const float maxLatitude = 46.812107;
const float minLongitude = 7.132838;
const float maxLongitude = 7.133173;

// IMU-Kalibrierungsdaten
float gyroBiasX = 0.0, gyroBiasY = 0.0, gyroBiasZ = 0.0;
float accelBiasX = 0.0, accelBiasY = 0.0, accelBiasZ = 0.0;

// Anzahl der Kalibrierungsmessungen
const int numCalibrationMeasurements = 100;

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ; // Warten, bis serielle Verbindung hergestellt ist. Nur für native USB-Ports erforderlich
  }

  if (serialOutput) {
    Serial.println("Starting Worx Mower GPS Tracker...");
  }

  // IMU initialisieren
  if (!IMU.begin()) {
    if (serialOutput) {
      Serial.println("Failed to initialize IMU!");
    }
    while (1);
  }

  // SD-Karte initialisieren
  if (!SD.begin(chipSelect)) {
    if (serialOutput) {
      Serial.println("Card failed, or not present");
    }
    while (1); // Don't do anything more
  }

  // GPS initialisieren
  Serial1.begin(GPSBaud);

  connectToWifi();
  mqttClient.setUsernamePassword(username, password);
  connectToMqtt();
}

void connectToWifi() {
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
}

void connectToMqtt() {
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

  mqttClient.onMessage(onMqttMessage);

  // Abonniere MQTT-Topics
  mqttClient.subscribe(topicControl);
}

void loop() {
  // MQTT-Client überprüfen und Nachrichten verarbeiten
  mqttClient.poll();

  getGpsData(); // GPS-Daten lesen und verarbeiten

  if (maehenAktiv) {
    checkImuForMovement();
    if (gpsFix) {  // Nur Daten aufzeichnen, wenn ein GPS-Fix vorhanden ist
      recordGpsData();
    }
  } else if (fakeGpsMode) {
    simulateGpsData();
  }
}

void getGpsData() {
  while (Serial1.available() > 0) {
    if (gps.encode(Serial1.read())) {
      if (gps.location.isValid()) {
        latitude = gps.location.lat();
        longitude = gps.location.lng();
        gpsFix = true;
        lastGpsTime = millis(); // Zeitstempel aktualisieren
        if (serialOutput) {
          Serial.print("GPS: ");
          Serial.print(latitude, 6); // 6 Nachkommastellen
          Serial.print(", ");
          Serial.println(longitude, 6);
        }
      } else {
        gpsFix = false;
      }
    }
  }
}

void checkImuForMovement() {
  if (IMU.accelerationAvailable() && IMU.gyroscopeAvailable()) {
    float ax, ay, az, gx, gy, gz;
    IMU.readAcceleration(ax, ay, az);
    IMU.readGyroscope(gx, gy, gz);

    // Subtrahiere den Bias von den IMU-Werten
    ax -= accelBiasX;
    ay -= accelBiasY;
    az -= accelBiasZ;
    gx -= gyroBiasX;
    gy -= gyroBiasY;
    gz -= gyroBiasZ;

    // Berechne die Gesamtbeschleunigung und Winkelgeschwindigkeit
    float accelMagnitude = sqrt(ax*ax + ay*ay + az*az);
    float gyroMagnitude = sqrt(gx*gx + gy*gy + gz*gz);

    // Überprüfe, ob die Bewegung unter den Schwellenwerten liegt
    if (accelMagnitude < imuThreshold && gyroMagnitude < imuThreshold) {
      static unsigned long lastProblemTime = 0; // Zeitstempel des letzten Problems
      const unsigned long problemTimeout = 5000; // Timeout in Millisekunden

      // Überprüfe, ob der Timeout abgelaufen ist
      if (millis() - lastProblemTime > problemTimeout) {
        if (!problemDetected && isInsideBoundaries(latitude, longitude)) {
          problemDetected = true;
          if (serialOutput) {
            Serial.println("Problem detected!");
          }
          sendProblemData(latitude, longitude);
          lastProblemTime = millis(); // Zeitstempel aktualisieren
        }
      }
    } else {
      problemDetected = false;
    }
  }
}

// ... (Fortsetzung im nächsten Kommentar)

void recordGpsData() {
  if (!SD.exists("gps_data.json")) {
    dataFile = SD.open("gps_data.json", FILE_WRITE);
    dataFile.println("["); // Starte JSON-Array
    dataFile.close();
  }

  dataFile = SD.open("gps_data.json", O_APPEND); // Korrigierte Verwendung von O_APPEND
  if (dataFile) {
    DynamicJsonDocument doc(200); // Dynamische Speicherzuweisung
    doc["lat"] = latitude;
    doc["lon"] = longitude;
    doc["timestamp"] = lastGpsTime; // Timestamp vom GPS-Modul

    // Füge Komma hinzu, wenn es nicht der erste Eintrag ist
    if (dataFile.size() > 2) {
      dataFile.print(",");
    }

    serializeJson(doc, dataFile);
    dataFile.close();
  } else {
    if (serialOutput) {
      Serial.println("Error opening gps_data.json");
    }
  }
}


void sendGpsData() {
  dataFile = SD.open("gps_data.json", FILE_READ);
  if (dataFile) {
    // Füge schließende Klammer für JSON-Array hinzu
    dataFile.seek(dataFile.size() - 1); // Gehe zum letzten Zeichen vor EOF
    if (dataFile.peek() == ',') { // Wenn das letzte Zeichen ein Komma ist
      dataFile.seek(dataFile.size() - 2); // Überschreibe das Komma
    }
    dataFile.println("]");
    dataFile.seek(0); // Zurück zum Anfang

    // Sende Daten per MQTT
    if (mqttClient.connected()) { // Überprüfen, ob MQTT verbunden ist
      mqttClient.beginMessage(topicGps);
      while (dataFile.available()) {
        mqttClient.write(dataFile.read());
      }
      mqttClient.endMessage();
    } else {
      if (serialOutput) {
        Serial.println("MQTT not connected. Cannot send GPS data.");
      }
    }

    dataFile.close();

    // Lösche Datei nach dem Senden
    SD.remove("gps_data.json");
  } else {
    if (serialOutput) {
      Serial.println("Error opening gps_data.json");
    }
  }
}

void sendProblemData(float lat, float lon) {
  DynamicJsonDocument doc(200); // Dynamische Speicherzuweisung
  doc["lat"] = lat;
  doc["lon"] = lon;
  doc["timestamp"] = millis();
  doc["command"] = "problem";

  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);

  if (mqttClient.connected()) { // Überprüfen, ob MQTT verbunden ist
    mqttClient.beginMessage(topicStatus);
    mqttClient.print(jsonBuffer);
    mqttClient.endMessage();
  } else {
    if (serialOutput) {
      Serial.println("MQTT not connected. Cannot send problem data.");
    }
  }
}

void onMqttMessage(int messageSize) {
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
      // IMU kalibrieren, wenn der Worx in der Ladestation ist
      calibrateIMU();
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



// 7. Hilfsfunktionen:

void simulateGpsData() {
  // Simuliere GPS-Daten, wenn kein GPS-Empfang möglich ist
  static unsigned long lastSimulatedGpsTime = 0;
  if (millis() - lastSimulatedGpsTime > gpsInterval) {
    latitude += random(-0.00005, 0.00005);  // Zufällige Änderung
    longitude += random(-0.00005, 0.00005); // Zufällige Änderung
    lastSimulatedGpsTime = millis();

    if (serialOutput) {
      Serial.print("Simulated GPS: ");
      Serial.print(latitude, 6);
      Serial.print(", ");
      Serial.println(longitude, 6);
    }
  }
}

void calibrateIMU() {
  // IMU-Kalibrierung durchführen, wenn der Worx in der Ladestation steht
  gyroBiasX = 0; gyroBiasY = 0; gyroBiasZ = 0;
  accelBiasX = 0; accelBiasY = 0; accelBiasZ = 0;

  for (int i = 0; i < numCalibrationMeasurements; i++) {
    float gx, gy, gz, ax, ay, az;
    IMU.readGyroscope(gx, gy, gz);
    IMU.readAcceleration(ax, ay, az);

    gyroBiasX += gx;
    gyroBiasY += gy;
    gyroBiasZ += gz;
    accelBiasX += ax;
    accelBiasY += ay;
    accelBiasZ += az;

    delay(10); // Kurze Pause zwischen den Messungen
  }

  gyroBiasX /= numCalibrationMeasurements;
  gyroBiasY /= numCalibrationMeasurements;
  gyroBiasZ /= numCalibrationMeasurements;
  accelBiasX /= numCalibrationMeasurements;
  accelBiasY /= numCalibrationMeasurements;
  accelBiasZ /= numCalibrationMeasurements;

  if (serialOutput) {
    Serial.println("IMU calibration complete");
  }
}

void handleSerialInput() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.startsWith("imuThreshold ")) {
      float newThreshold = command.substring(12).toFloat();
      if (newThreshold > 0) {
        imuThreshold = newThreshold;
        Serial.print("IMU threshold set to: ");
        Serial.println(imuThreshold);
      } else {
        Serial.println("Invalid threshold value. Must be greater than 0.");
      }
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
