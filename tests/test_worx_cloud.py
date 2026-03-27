"""Einfacher API-Test für die Worx Cloud Verbindung via pyworxcloud."""

import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def main():
    from pyworxcloud import WorxCloud

    email = os.getenv("WORX_EMAIL")
    password = os.getenv("WORX_PASSWORD")
    cloud_type = os.getenv("WORX_CLOUD_TYPE", "worx")

    print(f"[1] Verbinde mit Worx Cloud als '{email}' (Type: {cloud_type})...")

    cloud = WorxCloud(email, password, cloud_type)

    try:
        # Authentifizierung
        print("[2] Authentifizierung...")
        await cloud.authenticate()
        print("    ✓ Authentifizierung erfolgreich!")

        # Verbindung (MQTT)
        print("[3] Verbinde mit Cloud-MQTT...")
        connected = await cloud.connect()
        print(f"    ✓ Verbunden: {connected}")

        if not connected:
            print("    ✗ Keine Mäher gefunden oder Verbindung fehlgeschlagen.")
            return

        # Geräte auflisten
        print(f"\n[4] Gefundene Geräte: {len(cloud.devices)}")
        for name, device in cloud.devices.items():
            print(f"\n{'='*60}")
            print(f"  Name:          {name}")
            print(f"  Modell:        {device.model}")
            print(f"  Serial:        {device.serial_number}")
            print(f"  Online:        {device.online}")
            print(f"  Firmware:      {device.firmware}")
            print(f"  Protocol:      {device.protocol}")

            # Status
            print(f"\n  --- Status ---")
            print(f"  Status:        {device.status}")
            print(f"  Error:         {device.error}")
            print(f"  Locked:        {getattr(device, 'locked', 'N/A')}")

            # Batterie
            print(f"\n  --- Batterie ---")
            if device.battery:
                print(f"  Prozent:       {device.battery.get('percent', 'N/A')}%")
                print(f"  Temperatur:    {device.battery.get('temperature', 'N/A')}°C")
                print(f"  Spannung:      {device.battery.get('voltage', 'N/A')}V")
                print(f"  Laden:         {device.battery.get('charging', 'N/A')}")
                print(f"  Zyklen:        {device.battery.get('cycles', 'N/A')}")

            # Orientierung (IMU)
            print(f"\n  --- Orientierung (IMU) ---")
            if device.orientation:
                print(f"  Pitch:         {device.orientation.get('pitch', 'N/A')}")
                print(f"  Roll:          {device.orientation.get('roll', 'N/A')}")
                print(f"  Yaw:           {device.orientation.get('yaw', 'N/A')}")
            else:
                print(f"  (keine Daten)")

            # GPS (falls vorhanden)
            print(f"\n  --- GPS ---")
            gps = getattr(device, 'gps', None)
            if gps:
                print(f"  Latitude:      {gps.get('latitude', 'N/A')}")
                print(f"  Longitude:     {gps.get('longitude', 'N/A')}")
            else:
                print(f"  (kein GPS-Modul)")

            # Statistiken
            print(f"\n  --- Statistiken ---")
            if device.statistics:
                print(f"  Laufzeit:      {device.statistics.get('worktime_total', 0)} Min.")
                print(f"  Messer-Zeit:   {device.statistics.get('worktime_blades_on', 0)} Min.")
                print(f"  Strecke:       {device.statistics.get('distance', 0)} m")

            # Messer
            print(f"\n  --- Messer ---")
            if device.blades:
                print(f"  Blades:        {dict(device.blades)}")

            # Zonen
            print(f"\n  --- Zonen ---")
            if device.zone:
                print(f"  Zone:          {dict(device.zone)}")

            # Zeitplan
            print(f"\n  --- Zeitplan ---")
            if device.schedules:
                print(f"  Aktiv:         {device.schedules.get('active', 'N/A')}")
                print(f"  Pause-Modus:   {device.schedules.get('pause_mode_enabled', 'N/A')}")
                slots = device.schedules.get('slots', [])
                print(f"  Slots:         {len(slots)} Einträge")
                for i, slot in enumerate(slots[:5]):  # Nur erste 5
                    print(f"    [{i}] {slot}")

            # Capabilities
            print(f"\n  --- Capabilities ---")
            print(f"  {device.capabilities}")

            # RSSI
            rssi = getattr(device, 'rssi', None)
            if rssi:
                print(f"\n  WiFi RSSI:     {rssi} dBm")

            # Rain
            print(f"\n  --- Regensensor ---")
            if device.rainsensor:
                print(f"  Regensensor:   {dict(device.rainsensor)}")

            # Roh-Daten (gekürzt)
            print(f"\n  --- Raw dat/cfg ---")
            if device.raw_dat:
                print(f"  dat keys:      {list(device.raw_dat.keys())}")
            if device.raw_cfg:
                print(f"  cfg keys:      {list(device.raw_cfg.keys())}")

            # Vollständige Raw-Daten in Datei speichern
            raw_output = {
                "dat": device.raw_dat,
                "cfg": device.raw_cfg,
            }
            output_file = f"tests/worx_cloud_raw_{name.replace(' ', '_')}.json"
            with open(output_file, "w") as f:
                json.dump(raw_output, f, indent=2, default=str)
            print(f"\n  ✓ Raw-Daten gespeichert in: {output_file}")

            print(f"{'='*60}")

    except Exception as e:
        print(f"\n✗ FEHLER: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[5] Trenne Verbindung...")
        await cloud.disconnect()
        print("    ✓ Getrennt.")


if __name__ == "__main__":
    asyncio.run(main())
