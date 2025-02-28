# heatmap_generator.py
import folium
from folium import plugins
from PIL import Image
from config import HEATMAP_CONFIG, GEO_CONFIG
import os
import io
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
import csv
import json


class HeatmapGenerator:
    def __init__(self):
        self.map_center = GEO_CONFIG["map_center"]
        self.tile = HEATMAP_CONFIG["tile"]
        self.zoom_start = GEO_CONFIG["zoom_start"]
        self.crop_coordinates = GEO_CONFIG["crop_coordinates"]  # Koordinaten für das Zuschneiden
        self.crop_enabled = GEO_CONFIG["crop_enabled"]  # Option zum Aktivieren

    def create_heatmap(self, data, html_file, draw_path):
        # Erstelle eine Karte.
        map_obj = folium.Map(location=self.map_center, zoom_start=self.zoom_start,
                             tiles="OpenStreetMap")  # Korrektur: Korrekte Einstellung
        path_points = []
        all_points = []

        # Füge die Heatmap und die Punkte hinzu.
        for point in data:
            try:
                # Die Werte müssen als Float vorliegen.
                latitude = float(point['latitude'])
                longitude = float(point['longitude'])

                all_points.append([latitude, longitude])
                path_points.append([latitude, longitude])

            except (ValueError, KeyError) as e:
                print(f"Fehler: Ungültige Werte in Zeile: {point}")
                print(f"Fehler: {e}")
                continue
        plugins.HeatMap(all_points).add_to(map_obj)

        # Zeichne Pfad, falls aktiviert.
        if draw_path and len(path_points) > 1:
            folium.PolyLine(path_points, color="blue", weight=2.5, opacity=1).add_to(map_obj)

        # Speichere Karte.
        map_obj.save(html_file)
        print(f"Heatmap erstellt: {html_file}")

    def generate_heatmap_from_csv(self, csv_file, html_file, draw_path=False):
        data = self.read_csv(csv_file)
        self.create_heatmap(data, html_file, draw_path)

    def read_csv(self, csv_file):
        data = []
        try:
            with open(csv_file, 'r', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
        except Exception as e:
            print(f"Fehler beim lesen der CSV Datei {e}")
        return data

    def save_html_as_png(self, html_file, png_file):
        # Teste ob ein Browser verfügbar ist.
        try:
            service = ChromeService(executable_path=ChromeDriverManager().install())
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_window_size(1200, 1000)
            driver.get(f"file:///{os.path.abspath(html_file)}")
            driver.save_screenshot(png_file)
            driver.quit()
            print(f"Successfully saved {png_file}")
        except Exception as e:
            print(f"Fehler beim Erstellen der PNG Datei: {e}")
