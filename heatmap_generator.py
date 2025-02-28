# heatmap_generator.py
import folium
from folium import plugins
from PIL import Image
from config import HEATMAP_CONFIG, GEO_CONFIG
import os
import platform


class HeatmapGenerator:
    def __init__(self):
        self.map_center = GEO_CONFIG["map_center"]
        self.tile = HEATMAP_CONFIG["tile"]

    def create_heatmap(self, data_list, filename_html, draw_path=False):
        """Erstellt eine Heatmap aus einer Liste von GPS-Daten und speichert sie als HTML."""
        # Erstelle eine neue Karte
        map_obj = folium.Map(location=self.map_center, zoom_start=18, tiles=self.tile)
        all_points = []  # Punkte für Heatmap und Polylinie
        if draw_path:
            path_points = []  # Liste für die Pfadpunkte
            for data in data_list:
                for point in data:
                    path_points.append((point['lat'], point['lon']))
                    all_points.append((point['lat'], point['lon']))
            if path_points:
                folium.PolyLine(path_points, color="blue", weight=2.5, opacity=1).add_to(map_obj)
                # Pfeile hinzufügen
                plugins.AntPath(path_points, color="red", weight=4, opacity=1, dash_array=[10, 15]).add_to(map_obj)
        else:
            for data in data_list:
                for point in data:
                    all_points.append((point['lat'], point['lon']))
        # Heatmap hinzufügen
        if all_points:
            plugins.HeatMap(all_points, radius=25).add_to(map_obj)
        # Karte speichern
        map_obj.save(filename_html)
        # Karte als PNG speichern
        if platform.system() != "Linux":
            self.save_html_as_png(filename_html, filename_html.replace(".html", ".png"))
        else:
            print("PNG erstellen nur auf Windows/Mac möglich")

    def save_html_as_png(self, html_file, png_file):
        """Konvertiert eine HTML-Datei in eine PNG-Datei."""
        try:
            # Temporäre Datei
            temp_html_file = "temp.html"
            with open(temp_html_file, "w", encoding="utf-8") as temp_file:
                with open(html_file, "r", encoding="utf-8") as file:
                    for line in file:
                        if 'tileLayer' in line:
                            line = line.replace("tiles: '",
                                                "tiles: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',")
                        temp_file.write(line)
            # Open the HTML file using Pillow
            img = Image.open(temp_html_file)
            img.save(png_file)
            os.remove(temp_html_file)
            print(f"Successfully saved {png_file}")
        except Exception as e:
            print(f"Error converting HTML to PNG: {e}")
