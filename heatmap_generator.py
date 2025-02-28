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


class HeatmapGenerator:
    def __init__(self):
        self.map_center = GEO_CONFIG["map_center"]
        self.tile = HEATMAP_CONFIG["tile"]
        self.zoom_start = GEO_CONFIG["zoom_start"]
        self.crop_coordinates = GEO_CONFIG["crop_coordinates"]  # Koordinaten für das Zuschneiden
        self.crop_enabled = GEO_CONFIG["crop_enabled"]  # Option zum Aktivieren/Deaktivieren des Croppens

    def create_heatmap(self, data_list, filename_html, draw_path=False):
        """Erstellt eine Heatmap aus einer Liste von GPS-Daten und speichert sie als HTML."""
        # Erstelle eine neue Karte
        map_obj = folium.Map(location=self.map_center, zoom_start=self.zoom_start)
        attr = 'Google'  # Attribuierung hinzufügen
        tile_layer = folium.TileLayer(tiles=self.tile, attr=attr)  # TileLayer erstellen
        tile_layer.add_to(map_obj)  # TileLayer zur Karte hinzufügen
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
        self.save_html_as_png(filename_html, filename_html.replace(".html", ".png"))

    def save_html_as_png(self, html_file, png_file):
        """Konvertiert eine HTML-Datei in eine PNG-Datei mit Selenium."""
        temp_html_file = os.path.join(os.path.dirname(html_file), "temp.html")
        try:
            # HTML Datei erstellen.
            with open(html_file, "r", encoding="utf-8") as file:
                html_content = file.read()
            html_content = html_content.replace("tiles: '",
                                                "tiles: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',")

            with open(temp_html_file, "w", encoding="utf-8") as temp_file:
                temp_file.write(html_content)
            # Browser Einstellungen erstellen.
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless")  # Headless Modus
            chrome_options.add_argument("--window-size=1920x1080")  # Fenstergrösse
            # Treiber für Chrom holen.
            service = ChromeService(executable_path=ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            try:
                # HTML Datei im Browser öffnen.
                driver.get(f"file://{os.path.abspath(temp_html_file)}")
                # Screenshot machen.
                screenshot = driver.get_screenshot_as_png()

                # Screenshot in PIL Image umwandeln.
                img = Image.open(io.BytesIO(screenshot))
                # PNG zuschneiden
                if self.crop_enabled and self.crop_coordinates:
                    img = self.crop_image(img, self.crop_coordinates)
                img.save(png_file, "PNG")

                print(f"Successfully saved {png_file}")
            except Exception as e:
                print(f"Error converting HTML to PNG: {e}")
            finally:
                driver.quit()  # Browser schliessen

        except Exception as e:
            print(f"Error creating temporary HTML file: {e}")
        finally:
            if os.path.exists(temp_html_file):
                os.remove(temp_html_file)

    def crop_image(self, img, crop_coordinates):
        """Schneidet ein Bild basierend auf gegebenen Koordinaten zu."""
        left, upper, right, lower = crop_coordinates
        return img.crop((left, upper, right, lower))
