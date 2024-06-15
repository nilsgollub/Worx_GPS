#include <Arduino.h>
#include "mbed.h"
#include "drivers/FlashIAP.h" // Add this header file

// Definieren Sie eine Struktur für Ihre Daten
struct TestData {
  char message[50];
  int number;
  float value;
};

void setup() {
  Serial.begin(9600);

  // Test 1: Schreiben und Lesen von Daten
  TestData dataToWrite = {"Testnachricht", 123, 3.14159};
  uint32_t address = 0x100000; // Startadresse im externen Flash

  // FlashIAP-Objekt erstellen, unter Verwendung des mbed-Namespace
  mbed::FlashIAP flash;

  // Sektor löschen (erforderlich vor dem Schreiben)
  if (flash.erase(address, flash.get_sector_size(address)) != 0) {
    Serial.println("Fehler beim Löschen des Sektors!");
    return;
  }

  // Daten schreiben
  if (flash.program(&dataToWrite, address, sizeof(TestData)) != 0) {
    Serial.println("Fehler beim Schreiben der Daten!");
    return;
  }

  // Daten lesen
  TestData dataRead;
  memcpy(&dataRead, (void*)address, sizeof(TestData));

  Serial.println("Test 1: Schreiben und Lesen:");
  Serial.println(dataRead.message);
  Serial.println(dataRead.number);
  Serial.println(dataRead.value);
}

void loop() {
  // Nichts zu tun
}

