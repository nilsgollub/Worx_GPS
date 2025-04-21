# heatmap_generator.py
import folium
from folium import plugins
from PIL import Image
from config import HEATMAP_CONFIG, GEO_CONFIG
import os
import platform  # Importieren
import time
import logging
import numpy as np
import tempfile  # Für temporäre Dateien
import csv

# Selenium und WebDriver Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import WebDriverException

# webdriver-manager nur importieren, wenn er potenziell benötigt wird
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None  # Setze auf None, wenn nicht installiert

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    def __init__(self):
        self.map_center = GEO_CONFIG["map_center"]
        self.crop_enabled = GEO_CONFIG.get("crop_enabled", False)
        self.crop_center_percentage = GEO_CONFIG.get("crop_center_percentage")
        self.use_center_crop = False
        self.crop_pixel_left = GEO_CONFIG.get("crop_pixel_left")
        self.crop_pixel_top = GEO_CONFIG.get("crop_pixel_top")
        self.crop_pixel_right = GEO_CONFIG.get("crop_pixel_right")
        self.crop_pixel_bottom = GEO_CONFIG.get("crop_pixel_bottom")
        logger.info("HeatmapGenerator initialisiert.")
        if self.crop_enabled:
            if self.crop_center_percentage is not None and isinstance(self.crop_center_percentage, (
                    int, float)) and 0 <= self.crop_center_percentage <= 100:
                self.use_center_crop = True
                if self.crop_center_percentage < 100:
                    logger.info(f"PNG Cropping (Center Percentage) aktiviert: {self.crop_center_percentage}%")
                else:
                    logger.info("PNG Cropping (Center Percentage) ist 100%, kein Zuschnitt erfolgt.")
                    self.crop_enabled = False
            else:
                pixel_values = [self.crop_pixel_left, self.crop_pixel_top, self.crop_pixel_right,
                                self.crop_pixel_bottom]
                if all(p is not None and isinstance(p, int) and p >= 0 for p in pixel_values):
                    self.use_center_crop = False
                    logger.info(
                        f"PNG Cropping (Pixel Offsets) aktiviert mit (L,T,R,B): ({self.crop_pixel_left}, {self.crop_pixel_top}, {self.crop_pixel_right}, {self.crop_pixel_bottom})")
                else:
                    logger.warning(
                        "PNG Cropping ist aktiviert, aber weder 'crop_center_percentage' noch 'crop_pixel_*' Werte sind gültig. Cropping wird deaktiviert.")
                    self.crop_enabled = False

    def create_heatmap(self, data, html_file, draw_path):
        # ... (Diese Methode bleibt unverändert) ...
        initial_zoom = GEO_CONFIG.get("zoom_start", 15)
        google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        google_attr = 'Google Satellite'
        map_obj = folium.Map(
            location=self.map_center,
            zoom_start=initial_zoom,
            tiles=google_tiles_url,
            attr=google_attr
        )
        osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        folium.TileLayer(
            tiles="OpenStreetMap",
            attr=osm_attr,
            name='OpenStreetMap',
            overlay=False,
            control=True,
        ).add_to(map_obj)

        path_points = []
        all_points = []
        for point in data:
            try:
                latitude = float(point['lat'])
                longitude = float(point['lon'])
                all_points.append([latitude, longitude])
                if draw_path:
                    path_points.append([latitude, longitude])
            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"Fehler: Ungültige Werte im Datenpunkt: {point} - {e}")
                continue

        try:
            output_dir = os.path.dirname(html_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Ordners {output_dir}: {e}")
            return

        if all_points:
            config_key = None
            for key, config_val in HEATMAP_CONFIG.items():
                # Finde den passenden Config-Eintrag basierend auf dem Output-Dateinamen
                if isinstance(config_val, dict) and config_val.get("output") == html_file:
                    config_key = key
                    break
            radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 15)
            blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 10)
            heatmap_layer = plugins.HeatMap(all_points, radius=radius, blur=blur, name="Heatmap")
            heatmap_layer.add_to(map_obj)
        else:
            logger.warning(f"Keine gültigen Punkte zum Erstellen der Heatmap {html_file} gefunden.")

        if draw_path and len(path_points) > 1:
            path_layer = folium.PolyLine(path_points, color="blue", weight=1.0, opacity=1, name="Mhpfad")
            path_layer.add_to(map_obj)

        if all_points:
            points_array = np.array(all_points)
            min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
            min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()
            lat_span = max_lat - min_lat
            lon_span = max_lon - min_lon
            zoom_factor = 0.6
            lat_adjust = lat_span * zoom_factor / 2
            lon_adjust = lon_span * zoom_factor / 2
            epsilon = 1e-9
            if lat_adjust < 0: lat_adjust = 0
            if lon_adjust < 0: lon_adjust = 0
            if min_lat + lat_adjust >= max_lat - lat_adjust:
                lat_adjust = (max_lat - min_lat) / 4 if (max_lat - min_lat) > epsilon else 0
            if min_lon + lon_adjust >= max_lon - lon_adjust:
                lon_adjust = (max_lon - min_lon) / 4 if (max_lon - min_lon) > epsilon else 0
            tight_bounds = [
                [min_lat + lat_adjust, min_lon + lon_adjust],
                [max_lat - lat_adjust, max_lon - lon_adjust]
            ]
            try:
                map_obj.fit_bounds(tight_bounds)
                logger.debug(f"Kartenausschnitt angepasst an künstlich verkleinerte Grenzen: {tight_bounds}")
            except Exception as fit_err:
                logger.error(f"Fehler beim Anpassen des Kartenausschnitts (fit_bounds): {fit_err}")

        folium.LayerControl().add_to(map_obj)
        try:
            map_obj.save(html_file)
            logger.info(f"Interaktive Heatmap erstellt: {html_file}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der interaktiven Heatmap {html_file}: {e}")

    def generate_heatmap_from_csv(self, csv_file, html_file, draw_path=False):
        # ... (bleibt unverändert) ...
        data = self.read_csv(csv_file)
        self.create_heatmap(data, html_file, draw_path)

    def read_csv(self, csv_file):
        # ... (bleibt unverändert) ...
        data = []
        try:
            with open(csv_file, 'r', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
        except Exception as e:
            logger.error(f"Fehler beim lesen der CSV Datei {csv_file}: {e}")
        return data

    # --- save_html_as_png angepasst für Plattformunabhängigkeit ---
    def save_html_as_png(self, data, draw_path, png_file, config_key_hint=None):
        """
        Erstellt eine temporäre Satelliten-Karte, macht einen Screenshot und speichert ihn als PNG.
        Berücksichtigt das Betriebssystem für die ChromeDriver-Initialisierung.

        Args:
            data (list): Die Liste der Datenpunkte (Dictionaries mit 'lat', 'lon').
            draw_path (bool): Ob der Pfad gezeichnet werden soll.
            png_file (str): Der Zieldateiname für das PNG-Bild.
            config_key_hint (str, optional): Der Schlüssel aus HEATMAP_CONFIG, um Radius/Blur zu finden.
        """
        if not data:
            logger.warning(f"Keine Daten zum Erstellen von PNG {png_file} übergeben.")
            return

        try:
            output_dir = os.path.dirname(png_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Ordners für PNG {output_dir}: {e}")
            return

        temp_html_handle = None
        temp_html_path = None
        create_temp_file = self.crop_enabled
        temp_png_file = png_file + ".tmp" if create_temp_file else png_file
        final_png_file = png_file
        driver = None  # Initialisieren für finally-Block

        try:
            # --- Erstelle temporäre Karte NUR für Screenshot ---
            logger.debug(f"Erstelle temporäre Satellitenkarte für Screenshot von {png_file}...")
            google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
            google_attr = 'Google Satellite'
            screenshot_map = folium.Map(
                location=self.map_center,
                zoom_start=15,
                tiles=google_tiles_url,
                attr=google_attr
            )

            path_points = []
            all_points = []
            for point in data:
                try:
                    latitude = float(point['lat'])
                    longitude = float(point['lon'])
                    all_points.append([latitude, longitude])
                    if draw_path:
                        path_points.append([latitude, longitude])
                except (ValueError, KeyError, TypeError):
                    continue

            if all_points:
                radius = 15
                blur = 10
                found_config = False
                if config_key_hint and config_key_hint in HEATMAP_CONFIG:
                    radius = HEATMAP_CONFIG[config_key_hint].get("radius", radius)
                    blur = HEATMAP_CONFIG[config_key_hint].get("blur", blur)
                    found_config = True
                else:
                    for key, config_val in HEATMAP_CONFIG.items():
                        if isinstance(config_val, dict) and config_val.get("png_output") == png_file:
                            radius = config_val.get("radius", radius)
                            blur = config_val.get("blur", blur)
                            found_config = True
                            break
                if not found_config:
                    logger.warning(
                        f"Keine spezifische Radius/Blur-Konfiguration für {png_file} gefunden, verwende Defaults.")

                plugins.HeatMap(all_points, radius=radius, blur=blur).add_to(screenshot_map)

                if draw_path and len(path_points) > 1:
                    folium.PolyLine(path_points, color="blue", weight=1.0, opacity=1).add_to(screenshot_map)

                points_array = np.array(all_points)
                min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
                min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()
                lat_span = max_lat - min_lat
                lon_span = max_lon - min_lon
                zoom_factor = 0.6
                lat_adjust = lat_span * zoom_factor / 2
                lon_adjust = lon_span * zoom_factor / 2
                epsilon = 1e-9
                if lat_adjust < 0: lat_adjust = 0
                if lon_adjust < 0: lon_adjust = 0
                if min_lat + lat_adjust >= max_lat - lat_adjust:
                    lat_adjust = (max_lat - min_lat) / 4 if (max_lat - min_lat) > epsilon else 0
                if min_lon + lon_adjust >= max_lon - lon_adjust:
                    lon_adjust = (max_lon - min_lon) / 4 if (max_lon - min_lon) > epsilon else 0
                tight_bounds = [
                    [min_lat + lat_adjust, min_lon + lon_adjust],
                    [max_lat - lat_adjust, max_lon - lon_adjust]
                ]
                try:
                    screenshot_map.fit_bounds(tight_bounds)
                except Exception as fit_err:
                    logger.error(f"Fehler beim Anpassen des Kartenausschnitts (fit_bounds) für Screenshot: {fit_err}")

            temp_html_handle, temp_html_path = tempfile.mkstemp(suffix=".html", prefix="screenshot_")
            os.close(temp_html_handle)
            screenshot_map.save(temp_html_path)
            logger.debug(f"Temporäre Screenshot-HTML gespeichert: {temp_html_path}")
            # --- Ende temporäre Karte ---

            # --- Selenium Screenshot ---
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1200")  # Größere Auflösung für bessere Qualität

            service = None
            system_name = platform.system()

            try:
                if system_name == "Linux":
                    # Versuche systeminstallierten Treiber (typisch für Pi)
                    system_driver_paths = ['/usr/bin/chromedriver', '/usr/lib/chromium-browser/chromedriver']
                    found_driver_path = None
                    for path in system_driver_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            found_driver_path = path
                            logger.info(f"Verwende systeminstallierten ChromeDriver: {found_driver_path}")
                            break

                    if found_driver_path:
                        service = ChromeService(executable_path=found_driver_path)
                    else:
                        logger.warning("System-ChromeDriver nicht gefunden oder nicht ausführbar.")
                        # Fallback auf webdriver-manager, falls verfügbar
                        if ChromeDriverManager:
                            logger.info("Versuche Fallback auf webdriver-manager...")
                            service = ChromeService(executable_path=ChromeDriverManager().install())
                        else:
                            raise WebDriverException(
                                "System-ChromeDriver nicht gefunden und webdriver-manager nicht installiert.")

                elif system_name == "Windows":
                    if ChromeDriverManager:
                        logger.info("Windows erkannt. Verwende webdriver-manager.")
                        service = ChromeService(executable_path=ChromeDriverManager().install())
                    else:
                        raise ImportError("webdriver-manager ist nicht installiert, wird aber für Windows benötigt.")
                else:
                    # Andere Systeme: Versuche webdriver-manager
                    if ChromeDriverManager:
                        logger.info(f"System '{system_name}' erkannt. Versuche webdriver-manager.")
                        service = ChromeService(executable_path=ChromeDriverManager().install())
                    else:
                        raise ImportError(
                            f"webdriver-manager ist nicht installiert, wird aber für {system_name} benötigt.")

                # Initialisiere den WebDriver
                if service:
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    # Sollte nicht passieren, wenn die Logik oben korrekt ist
                    raise WebDriverException("ChromeDriver Service konnte nicht initialisiert werden.")

                # Lade die temporäre HTML und mache den Screenshot
                file_uri = f"file:///{os.path.abspath(temp_html_path)}"
                logger.debug(f"Lade HTML für Screenshot: {file_uri}")
                driver.get(file_uri)
                time.sleep(5)  # Wartezeit für Satellitenkacheln und Rendering
                driver.save_screenshot(temp_png_file)
                logger.info(f"Screenshot erfolgreich erstellt: {temp_png_file}")

            except (WebDriverException, ImportError, Exception) as driver_err:
                logger.error(f"Fehler bei der Initialisierung oder Verwendung von ChromeDriver: {driver_err}",
                             exc_info=True)
                # Cleanup und Abbruch
                if temp_html_path and os.path.exists(temp_html_path):
                    try:
                        os.remove(temp_html_path)
                    except OSError:
                        pass
                return  # Beende die Funktion hier, da Screenshot fehlgeschlagen ist
            finally:
                if driver:
                    driver.quit()
                    logger.debug("ChromeDriver beendet.")
            # --- Ende Selenium ---

            # --- PNG Cropping Logik (bleibt gleich) ---
            if self.crop_enabled:
                logger.info(f"Cropping für {final_png_file} wird durchgeführt.")
                try:
                    img = Image.open(temp_png_file)
                    width, height = img.size
                    crop_box = None

                    if self.use_center_crop:
                        percentage = self.crop_center_percentage / 100.0
                        min_dimension = min(width, height)
                        crop_side = int(min_dimension * percentage)
                        if crop_side > 0:
                            left = int((width - crop_side) / 2)
                            top = int((height - crop_side) / 2)
                            right = left + crop_side
                            bottom = top + crop_side
                            crop_box = (left, top, right, bottom)
                            logger.debug(
                                f"Berechnete Center-Crop-Box (L,T,R,B): {crop_box} für Bildgröße ({width}x{height})")
                        else:
                            logger.warning("Berechnete Crop-Seitenlänge ist 0 oder kleiner. Kein Zuschnitt.")
                    else:
                        left_px = self.crop_pixel_left
                        top_px = self.crop_pixel_top
                        right_px = width - self.crop_pixel_right
                        bottom_px = height - self.crop_pixel_bottom
                        # Stelle sicher, dass die Box gültig ist
                        if left_px < right_px and top_px < bottom_px:
                            crop_box = (left_px, top_px, right_px, bottom_px)
                            logger.debug(
                                f"Berechnete Pixel-Offset-Crop-Box (L,T,R,B): {crop_box} für Bildgröße ({width}x{height})")
                        else:
                            logger.error(
                                f"Ungültige Pixel-Offset-Werte führen zu keiner oder negativer Fläche: L={left_px}, T={top_px}, R={right_px}, B={bottom_px}")

                    if crop_box and crop_box[0] < crop_box[2] and crop_box[1] < crop_box[3]:
                        cropped_img = img.crop(crop_box)
                        cropped_img.save(final_png_file)
                        logger.info(f"Bild erfolgreich auf {final_png_file} zugeschnitten.")
                        # Lösche temporäres PNG nur bei Erfolg
                        if create_temp_file and os.path.exists(temp_png_file):
                            try:
                                os.remove(temp_png_file)
                            except OSError as rm_err:
                                logger.warning(f"Konnte temporäre PNG {temp_png_file} nicht löschen: {rm_err}")
                    else:
                        logger.error(
                            f"Ungültige oder keine Crop-Box berechnet: {crop_box}. Originalbild wird verwendet.")
                        # Benenne temporäres PNG um, wenn Cropping fehlschlägt oder nicht durchgeführt wird
                        if create_temp_file and os.path.exists(temp_png_file):
                            try:
                                if os.path.exists(final_png_file):  # Überschreibe Zieldatei, falls sie existiert
                                    os.remove(final_png_file)
                                os.rename(temp_png_file, final_png_file)
                                logger.info(f"Temporäres PNG zu {final_png_file} umbenannt (kein Crop).")
                            except OSError as ren_err:
                                logger.error(f"Konnte temp PNG nicht zu {final_png_file} umbenennen: {ren_err}")
                        elif not create_temp_file:
                            logger.info(f"Kein Cropping aktiviert, {final_png_file} wurde direkt erstellt.")


                except Exception as crop_err:
                    logger.error(f"Fehler beim Zuschneiden des Bildes {temp_png_file}: {crop_err}", exc_info=True)
                    # Versuche, das temporäre Bild umzubenennen, falls Cropping fehlschlägt
                    if create_temp_file and os.path.exists(temp_png_file):
                        try:
                            if os.path.exists(final_png_file):
                                os.remove(final_png_file)
                            os.rename(temp_png_file, final_png_file)
                            logger.info(f"Temporäres PNG zu {final_png_file} umbenannt (Crop fehlgeschlagen).")
                        except OSError as ren_err:
                            logger.error(f"Konnte temp PNG nicht zu {final_png_file} umbenennen: {ren_err}")
            # --- ENDE PNG Cropping ---

        except Exception as e:
            logger.error(f"Allgemeiner Fehler beim Erstellen der PNG Datei {final_png_file}: {e}", exc_info=True)
            # Cleanup bei allgemeinem Fehler
            if create_temp_file and os.path.exists(temp_png_file):
                try:
                    os.remove(temp_png_file)
                except OSError:
                    pass
        finally:
            # --- Temporäre HTML-Datei löschen ---
            if temp_html_path and os.path.exists(temp_html_path):
                try:
                    os.remove(temp_html_path)
                    logger.debug(f"Temporäre HTML-Datei {temp_html_path} gelöscht.")
                except OSError as e:
                    logger.warning(f"Konnte temporäre HTML-Datei {temp_html_path} nicht löschen: {e}")
            # ---


# --- Der __main__ Block für Tests ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    test_data = [
        {'lat': 46.8118, 'lon': 7.1328},
        {'lat': 46.8119, 'lon': 7.1329},
        {'lat': 46.8120, 'lon': 7.1330},
        {'lat': 46.81185, 'lon': 7.13285},
    ]
    if not os.path.exists("heatmaps"):
        os.makedirs("heatmaps")

    # Stelle sicher, dass die Werte in config.py für den Test passen
    # Diese Zeilen sollten entfernt oder auskommentiert werden,
    # da die Konfiguration jetzt aus der Datei gelesen wird.
    # GEO_CONFIG['crop_enabled'] = True
    # GEO_CONFIG['crop_center_percentage'] = 80

    generator = HeatmapGenerator()  # Liest Config beim Initialisieren

    # Test 1: Interaktive HTML
    print("Teste create_heatmap (erstellt interaktive HTML)...")
    test_html_file = "heatmaps/test_heatmap_interactive.html"
    generator.create_heatmap(test_data, test_html_file, draw_path=True)

    # Test 2: PNG Erstellung (mit Cropping, falls in config.py aktiviert)
    print("\nTeste save_html_as_png (erstellt PNG von temporärer Satellitenkarte)...")
    test_png_file = "heatmaps/test_heatmap_screenshot.png"
    # Finde den config_key basierend auf dem HTML-Namen (oder übergebe ihn explizit)
    # Hier nehmen wir an, es gibt keinen spezifischen Eintrag, also werden Defaults verwendet
    generator.save_html_as_png(test_data, True, test_png_file, config_key_hint=None)

    # Test 3: PNG Erstellung ohne Cropping (überschreibt temporär die Einstellung)
    print("\nTeste save_html_as_png ohne Cropping...")
    generator.crop_enabled = False  # Deaktiviere Cropping für diesen Test
    test_png_no_crop_file = "heatmaps/test_heatmap_screenshot_no_crop.png"
    generator.save_html_as_png(test_data, True, test_png_no_crop_file, config_key_hint=None)
    generator.crop_enabled = GEO_CONFIG.get("crop_enabled", False)  # Setze zurück auf Config-Wert

    print("\nTests abgeschlossen.")
