# heatmap_generator.py
import folium
from folium import plugins
from PIL import Image
from config import HEATMAP_CONFIG, GEO_CONFIG
import os
# import io # Nicht mehr direkt benötigt in diesem Snippet
# import tempfile # Nicht mehr direkt benötigt in diesem Snippet
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
import csv
# import json # Nicht mehr direkt benötigt in diesem Snippet
import logging
import time
import numpy as np  # Importiere numpy für min/max Berechnungen

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class HeatmapGenerator:
    def __init__(self):
        self.map_center = GEO_CONFIG["map_center"]
        # self.zoom_start = GEO_CONFIG["zoom_start"] # Wird weniger relevant, wenn fit_bounds verwendet wird
        self.crop_coordinates = GEO_CONFIG["crop_coordinates"]
        self.crop_enabled = GEO_CONFIG["crop_enabled"]

    def create_heatmap(self, data, html_file, draw_path):
        # --- Änderung: Initialen Zoom entfernen oder als Fallback lassen ---
        # Starte mit einem Standard-Zoom, fit_bounds passt es später an, wenn Daten vorhanden sind.
        initial_zoom = GEO_CONFIG.get("zoom_start", 15)  # Hole aus Config oder nimm 15 als Default
        map_obj = folium.Map(location=self.map_center, zoom_start=initial_zoom,
                             tiles="OpenStreetMap")
        # --- Ende Änderung ---

        path_points = []
        all_points = []  # Liste von [lat, lon]

        for point in data:
            try:
                latitude = float(point['lat'])
                longitude = float(point['lon'])
                all_points.append([latitude, longitude])
                if draw_path:  # Nur hinzufügen, wenn Pfad gezeichnet werden soll
                    path_points.append([latitude, longitude])
            except (ValueError, KeyError, TypeError) as e:
                logging.error(f"Fehler: Ungltige Werte im Datenpunkt: {point} - {e}")
                continue

        # Stelle sicher, dass der Ordner existiert
        try:
            output_dir = os.path.dirname(html_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            logging.error(f"Fehler beim Erstellen des Ordners {output_dir}: {e}")
            return

        # Füge Heatmap hinzu, wenn Punkte vorhanden sind
        if all_points:
            config_key = None
            for key, config_val in HEATMAP_CONFIG.items():
                if isinstance(config_val, dict) and config_val.get("output") == html_file:
                    config_key = key
                    break
            radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 15)
            blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 10)
            plugins.HeatMap(all_points, radius=radius, blur=blur).add_to(map_obj)
        else:
            logging.warning(f"Keine gültigen Punkte zum Erstellen der Heatmap {html_file} gefunden.")

        # Zeichne Pfad, falls aktiviert und Punkte vorhanden
        if draw_path and len(path_points) > 1:
            folium.PolyLine(path_points, color="blue", weight=2.5, opacity=1).add_to(map_obj)

        # --- NEU: Kartenausschnitt an Daten anpassen ---
        if all_points:
            # Konvertiere Punkte zu numpy array für einfache min/max Berechnung
            points_array = np.array(all_points)
            # Berechne die Grenzen: [[min_lat, min_lon], [max_lat, max_lon]]
            bounds = [
                [points_array[:, 0].min(), points_array[:, 1].min()],  # Süd-West Ecke
                [points_array[:, 0].max(), points_array[:, 1].max()]  # Nord-Ost Ecke
            ]
            # Füge einen kleinen Puffer hinzu (optional, aber oft schöner)
            padding_lat = (bounds[1][0] - bounds[0][0]) * 0.05  # 5% Puffer
            padding_lon = (bounds[1][1] - bounds[0][1]) * 0.05  # 5% Puffer
            padded_bounds = [
                [bounds[0][0] - padding_lat, bounds[0][1] - padding_lon],
                [bounds[1][0] + padding_lat, bounds[1][1] + padding_lon]
            ]
            try:
                map_obj.fit_bounds(padded_bounds)
                logging.debug(f"Kartenausschnitt angepasst an Grenzen: {padded_bounds}")
            except Exception as fit_err:
                logging.error(f"Fehler beim Anpassen des Kartenausschnitts (fit_bounds): {fit_err}")
        # --- ENDE NEU ---

        # Speichere Karte
        try:
            map_obj.save(html_file)
            logging.info(f"Heatmap erstellt: {html_file}")
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Heatmap {html_file}: {e}")

    # --- Rest der Klasse bleibt gleich (read_csv, save_html_as_png, etc.) ---
    # ... (generate_heatmap_from_csv, read_csv, save_html_as_png) ...

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
            logging.error(f"Fehler beim lesen der CSV Datei {e}")
        return data

    def save_html_as_png(self, html_file, png_file):
        # Stelle sicher, dass der Ordner für PNG existiert
        try:
            output_dir = os.path.dirname(png_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            logging.error(f"Fehler beim Erstellen des Ordners für PNG {output_dir}: {e}")
            return  # Breche ab

        # Teste ob ein Browser verfügbar ist.
        try:
            service = ChromeService(executable_path=ChromeDriverManager().install())
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_window_size(1200, 1000)
            driver.get(f"file:///{os.path.abspath(html_file)}")
            time.sleep(2)  # Warten bis Karte gerendert ist (fit_bounds braucht evtl. kurz)
            driver.save_screenshot(png_file)
            driver.quit()
            logging.info(f"Successfully saved {png_file}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen der PNG Datei {png_file}: {e}")


# Beispielhafte Verwendung (nur für Testzwecke)
if __name__ == '__main__':
    # ... (Rest des if __name__ Blocks bleibt gleich) ...
    # Erstelle Beispieldaten
    test_data = [
        {'lat': 46.8118, 'lon': 7.1328},
        {'lat': 46.8119, 'lon': 7.1329},
        {'lat': 46.8120, 'lon': 7.1330},
        {'lat': 46.81185, 'lon': 7.13285},
    ]

    # Erstelle einen Ordner für die Ausgabe, falls nicht vorhanden
    if not os.path.exists("heatmaps"):
        os.makedirs("heatmaps")

    generator = HeatmapGenerator()

    # Teste create_heatmap
    print("Teste create_heatmap...")
    generator.create_heatmap(test_data, "heatmaps/test_heatmap.html", draw_path=True)

    # Teste save_html_as_png
    print("\nTeste save_html_as_png...")
    generator.save_html_as_png("heatmaps/test_heatmap.html", "heatmaps/test_heatmap.png")

    # Teste generate_heatmap_from_csv (erfordert eine CSV-Datei)
    # Erstelle eine Dummy-CSV-Datei
    print("\nErstelle Dummy-CSV für Test...")
    dummy_csv_file = "heatmaps/dummy_data.csv"
    with open(dummy_csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['lat', 'lon'])  # Header
        writer.writerow([46.8117, 7.1327])
        writer.writerow([46.81175, 7.13275])
        writer.writerow([46.8118, 7.1328])

    print("\nTeste generate_heatmap_from_csv...")
    generator.generate_heatmap_from_csv(dummy_csv_file, "heatmaps/test_heatmap_from_csv.html", draw_path=False)
    generator.save_html_as_png("heatmaps/test_heatmap_from_csv.html", "heatmaps/test_heatmap_from_csv.png")

    print("\nTests abgeschlossen.")
