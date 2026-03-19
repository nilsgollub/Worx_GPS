"""
Testskript: Erzeugt realistische GPS+WiFi-Testdaten und generiert die WiFi-Heatmap.
Simuliert einen Mähvorgang im definierten Geofence-Bereich.
"""
import json
import time
import math
import random
import os
import sys

# Projekt-Root zum Suchpfad hinzufügen
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from config import GEO_CONFIG, HEATMAP_CONFIG
from heatmap_generator import HeatmapGenerator
from data_manager import DataManager

# Kartenmittelpunkt aus der Config
center_lat = GEO_CONFIG.get("map_center", (46.8118, 7.1328))[0]
center_lon = GEO_CONFIG.get("map_center", (46.8118, 7.1328))[1]

print(f"Kartenmittelpunkt: {center_lat}, {center_lon}")

# Generiere einen simulierten Mähvorgang (Zick-Zack-Muster)
test_data = []
base_time = time.time() - 3600  # Vor 1 Stunde

num_points = 200
lat = center_lat - 0.0003  # Startpunkt etwas südlich vom Zentrum
lon = center_lon - 0.0003  # Startpunkt etwas westlich vom Zentrum
direction = 1  # 1 = nach rechts, -1 = nach links

for i in range(num_points):
    # Zick-Zack Muster: horizontal laufen, dann nach oben springen
    if i % 20 == 0 and i > 0:
        lat += 0.00003  # Etwas nach Norden
        direction *= -1   # Richtung wechseln
    
    lon += direction * 0.000003  # Nach rechts/links bewegen
    
    # WiFi-Signal simulieren: stärker in der Mitte, schwächer am Rand
    dist_from_center = math.sqrt((lat - center_lat)**2 + (lon - center_lon)**2)
    base_wifi = -45 - (dist_from_center / 0.0003) * 20  # -45 dBm im Zentrum, schlechter am Rand
    wifi_signal = int(base_wifi + random.gauss(0, 3))  # Etwas Rauschen
    wifi_signal = max(-95, min(-25, wifi_signal))  # Clamp
    
    satellites = random.randint(6, 12)
    
    test_data.append({
        "lat": lat + random.gauss(0, 0.000002),  # GPS-Rauschen
        "lon": lon + random.gauss(0, 0.000002),
        "timestamp": base_time + i * 2,  # Alle 2 Sekunden ein Punkt
        "satellites": satellites,
        "wifi": wifi_signal
    })

print(f"Testdaten generiert: {len(test_data)} Punkte")
print(f"WiFi-Range: {min(p['wifi'] for p in test_data)} dBm bis {max(p['wifi'] for p in test_data)} dBm")

# Daten speichern
dm = DataManager(data_folder=os.path.join(project_root, "data"))
filename = dm.get_next_mow_filename()
dm.save_gps_data(test_data, filename)
print(f"Testdaten gespeichert als: {filename}")

# Heatmaps generieren
hg = HeatmapGenerator(heatmaps_base_dir=os.path.join(project_root, "heatmaps"))

# 1. WiFi-Heatmap
wifi_config_key = "wifi_heatmap"
if wifi_config_key in HEATMAP_CONFIG:
    config = HEATMAP_CONFIG[wifi_config_key]
    html_file = config["output"]
    print(f"\nGeneriere WiFi-Heatmap -> {html_file}")
    hg.create_heatmap(test_data, html_file, draw_path=True, is_multi_session=False)
    print(f"  ✓ WiFi-Heatmap erstellt!")
else:
    print(f"  ✗ '{wifi_config_key}' nicht in HEATMAP_CONFIG gefunden!")

# 2. Aktuelle Heatmap
aktuell_key = "heatmap_aktuell"
if aktuell_key in HEATMAP_CONFIG:
    config = HEATMAP_CONFIG[aktuell_key]
    html_file = config["output"]
    print(f"Generiere aktuelle Heatmap -> {html_file}")
    hg.create_heatmap(test_data, html_file, draw_path=True, is_multi_session=False)
    print(f"  ✓ Aktuelle Heatmap erstellt!")

# 3. Quality Path
quality_key = "quality_path_10"
if quality_key in HEATMAP_CONFIG:
    config = HEATMAP_CONFIG[quality_key]
    html_file = config["output"]
    print(f"Generiere Qualitätspfad -> {html_file}")
    hg.create_heatmap([test_data], html_file, draw_path=True, is_multi_session=True)
    print(f"  ✓ Qualitätspfad erstellt!")

# Prüfe generierte Dateien
heatmaps_dir = os.path.join(project_root, "heatmaps")
if os.path.exists(heatmaps_dir):
    files = os.listdir(heatmaps_dir)
    print(f"\nGenerierte Heatmap-Dateien ({len(files)}):")
    for f in sorted(files):
        size = os.path.getsize(os.path.join(heatmaps_dir, f))
        print(f"  • {f} ({size/1024:.1f} KB)")
else:
    print("\nHeatmaps-Verzeichnis nicht gefunden!")

print("\n✅ Test abgeschlossen!")
