# heatmap_generator.py
import folium
from folium import plugins
from PIL import Image
from config import HEATMAP_CONFIG, GEO_CONFIG
import os
import platform
import time
import logging
import numpy as np
import tempfile
import csv
from pathlib import Path  # pathlib verwenden

# Selenium und WebDriver Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import WebDriverException

# webdriver-manager nur importieren, wenn er potenziell benötigt wird
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    def __init__(self):
        self.map_center = GEO_CONFIG["map_center"]
        # Verwende pathlib für Pfade
        self.heatmaps_dir = Path("heatmaps")
        self.heatmaps_dir.mkdir(parents=True, exist_ok=True)  # Sicherstellen, dass der Ordner existiert

        # Cropping-Logik bleibt gleich...
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

    # --- Angepasste create_heatmap Methode ---
    def create_heatmap(self, data, html_file, draw_path, is_multi_session=False):
        """
        Erstellt eine interaktive Heatmap.

        Args:
            data (list): Entweder eine flache Liste von Punkten [{'lat': y, 'lon': x, ...}]
                         oder eine Liste von Listen von Punkten [[{...}, {...}], [{...}, {...}]]
                         für Multi-Session-Karten.
            html_file (str): Der Zieldateiname für die HTML-Datei.
            draw_path (bool): Ob der Pfad (PolyLine) gezeichnet werden soll.
            is_multi_session (bool): Gibt an, ob 'data' eine Liste von Sessions ist.
        """
        initial_zoom = GEO_CONFIG.get("zoom_start", 15)
        google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        google_attr = 'Google Satellite'

        map_obj = folium.Map(
            location=self.map_center,
            zoom_start=initial_zoom,
            tiles=google_tiles_url,
            attr=google_attr,
            control_scale=True  # Maßstab hinzufügen
        )
        osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        folium.TileLayer(
            tiles="OpenStreetMap",
            attr=osm_attr,
            name='OpenStreetMap',
            overlay=False,  # Basiskarte, nicht Overlay
            control=True,
        ).add_to(map_obj)

        # --- Logik für einzelne oder mehrere Sessions ---
        all_points_for_bounds = []  # Sammelt alle Punkte für die Kartengrenzen

        if is_multi_session and isinstance(data, list) and data and isinstance(data[0], list):
            logger.info(f"Erstelle Multi-Session Heatmap für {html_file} mit {len(data)} Sessions.")
            # Iteriere rückwärts, damit die neueste Session oben in der LayerControl steht
            for idx, session_data in enumerate(reversed(data)):
                session_index = len(data) - 1 - idx  # Index der ursprünglichen Liste
                # Name für die Ebene (z.B. "Mähvorgang -1", "-2", ...)
                # Der neueste ist -1, der älteste ist -N
                layer_name = f"Mähvorgang -{idx + 1}"
                feature_group = folium.FeatureGroup(name=layer_name,
                                                    show=(idx == 0))  # Nur neueste standardmäßig anzeigen

                session_points = []
                path_points = []
                for point in session_data:
                    try:
                        latitude = float(point['lat'])
                        longitude = float(point['lon'])
                        session_points.append([latitude, longitude])
                        if draw_path:
                            path_points.append([latitude, longitude])
                    except (ValueError, KeyError, TypeError):
                        continue  # Ignoriere ungültige Punkte in der Session

                if session_points:
                    all_points_for_bounds.extend(session_points)  # Für Gesamtgrenzen hinzufügen
                    # Finde Radius/Blur für diese spezifische Karte (heatmap_10)
                    config_key = None
                    for key, config_val in HEATMAP_CONFIG.items():
                        if isinstance(config_val, dict) and config_val.get("output") == html_file:
                            config_key = key
                            break
                    radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 15)
                    blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 10)

                    # Heatmap für diese Session zur FeatureGroup hinzufügen
                    plugins.HeatMap(session_points, radius=radius, blur=blur).add_to(feature_group)

                    # Pfad für diese Session zur FeatureGroup hinzufügen (falls gewünscht)
                    if draw_path and len(path_points) > 1:
                        folium.PolyLine(path_points, color="blue", weight=1.0, opacity=0.8).add_to(feature_group)

                    # FeatureGroup zur Karte hinzufügen
                    feature_group.add_to(map_obj)
                else:
                    logger.warning(f"Session {session_index} enthält keine gültigen Punkte.")

        elif isinstance(data, list):  # Normale, einzelne Session/Datenmenge
            logger.info(f"Erstelle Single-Session Heatmap für {html_file}.")
            single_session_points = []
            single_path_points = []
            for point in data:
                try:
                    latitude = float(point['lat'])
                    longitude = float(point['lon'])
                    single_session_points.append([latitude, longitude])
                    if draw_path:
                        single_path_points.append([latitude, longitude])
                except (ValueError, KeyError, TypeError):
                    logger.error(f"Fehler: Ungültige Werte im Datenpunkt: {point}")
                    continue

            if single_session_points:
                all_points_for_bounds = single_session_points  # Für Grenzen verwenden
                # Finde Radius/Blur für diese spezifische Karte
                config_key = None
                for key, config_val in HEATMAP_CONFIG.items():
                    if isinstance(config_val, dict) and config_val.get("output") == html_file:
                        config_key = key
                        break
                radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 15)
                blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 10)

                # Heatmap direkt zur Karte hinzufügen
                plugins.HeatMap(single_session_points, radius=radius, blur=blur, name="Heatmap").add_to(map_obj)

                # Pfad direkt zur Karte hinzufügen (falls gewünscht)
                if draw_path and len(single_path_points) > 1:
                    folium.PolyLine(single_path_points, color="blue", weight=1.0, opacity=1, name="Pfad").add_to(
                        map_obj)
            else:
                logger.warning(f"Keine gültigen Punkte zum Erstellen der Heatmap {html_file} gefunden.")
        else:
            logger.error(f"Ungültiger Datentyp für Heatmap-Erstellung: {type(data)}")
            return  # Abbruch bei ungültigen Daten

        # --- Kartengrenzen anpassen (fit_bounds) ---
        if all_points_for_bounds:
            try:
                points_array = np.array(all_points_for_bounds)
                min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
                min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()

                # Prüfe auf gültige Grenzen (mehr als ein Punkt)
                if min_lat < max_lat or min_lon < max_lon:
                    # Leichter Puffer um die Punkte
                    lat_margin = (max_lat - min_lat) * 0.05  # 5% Puffer
                    lon_margin = (max_lon - min_lon) * 0.05  # 5% Puffer
                    epsilon = 1e-9  # Für den Fall, dass alle Punkte fast identisch sind
                    if lat_margin < epsilon: lat_margin = 0.0001
                    if lon_margin < epsilon: lon_margin = 0.0001

                    bounds = [
                        [min_lat - lat_margin, min_lon - lon_margin],
                        [max_lat + lat_margin, max_lon + lon_margin]
                    ]
                    map_obj.fit_bounds(bounds)
                    logger.debug(f"Kartenausschnitt für {html_file} angepasst an Grenzen: {bounds}")
                else:
                    # Nur ein Punkt oder alle Punkte identisch, setze Standardzoom um den Punkt
                    map_obj.location = [min_lat, min_lon]  # Zentriere auf den Punkt
                    map_obj.zoom_start = max(initial_zoom, 18)  # Höherer Zoom für Einzelpunkte
                    logger.debug(
                        f"Nur ein Punkt oder identische Punkte, zentriere Karte auf {map_obj.location} mit Zoom {map_obj.zoom_start}")

            except Exception as fit_err:
                logger.error(f"Fehler beim Anpassen des Kartenausschnitts (fit_bounds) für {html_file}: {fit_err}")
        else:
            logger.warning(f"Keine Punkte für Bounds-Anpassung in {html_file} vorhanden.")

        # --- LayerControl hinzufügen ---
        # Muss nach dem Hinzufügen aller Layer/FeatureGroups erfolgen
        folium.LayerControl(collapsed=False).add_to(map_obj)  # collapsed=False zeigt die Ebenen standardmäßig

        # --- Speichern ---
        try:
            # Verwende pathlib für den Pfad
            html_path = self.heatmaps_dir / Path(html_file).name  # Nur Dateiname verwenden
            map_obj.save(str(html_path))
            logger.info(f"Interaktive Heatmap erstellt: {html_path}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der interaktiven Heatmap {html_path}: {e}")

    # --- generate_heatmap_from_csv bleibt unverändert ---
    def generate_heatmap_from_csv(self, csv_file, html_file, draw_path=False):
        data = self.read_csv(csv_file)
        # Annahme: CSV enthält immer nur eine Session, daher is_multi_session=False
        self.create_heatmap(data, html_file, draw_path, is_multi_session=False)

    # --- read_csv bleibt unverändert ---
    def read_csv(self, csv_file):
        data = []
        try:
            # Verwende pathlib
            csv_path = Path(csv_file)
            with open(csv_path, 'r', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
        except Exception as e:
            logger.error(f"Fehler beim lesen der CSV Datei {csv_path}: {e}")
        return data

    # --- save_html_as_png bleibt größtenteils unverändert ---
    # WICHTIG: Diese Methode erstellt weiterhin ein PNG der *KOMBINIERTEN* Daten,
    # wenn sie für 'heatmap_10' aufgerufen wird, da Selenium keine Layer auswählen kann.
    # Wenn ein PNG pro Session gewünscht wäre, müsste die Logik hier stark angepasst werden.
    def save_html_as_png(self, data, draw_path, png_file, config_key_hint=None, is_multi_session_data=False):
        """
        Erstellt eine temporäre Satelliten-Karte, macht einen Screenshot und speichert ihn als PNG.
        Berücksichtigt das Betriebssystem für die ChromeDriver-Initialisierung.
        Wenn is_multi_session_data=True, werden alle Punkte aus allen Sessions für das PNG verwendet.

        Args:
            data (list): Entweder flache Liste von Punkten oder Liste von Listen (Sessions).
            draw_path (bool): Ob der Pfad gezeichnet werden soll.
            png_file (str): Der Zieldateiname für das PNG-Bild.
            config_key_hint (str, optional): Der Schlüssel aus HEATMAP_CONFIG, um Radius/Blur zu finden.
            is_multi_session_data (bool): Gibt an, ob 'data' eine Liste von Sessions ist.
        """
        # --- Daten für PNG vorbereiten (immer flache Liste) ---
        if is_multi_session_data and isinstance(data, list) and data and isinstance(data[0], list):
            logger.debug(f"Bereite Daten aus {len(data)} Sessions für PNG {png_file} vor.")
            flat_data_for_png = [point for session in data for point in session]
        elif isinstance(data, list):
            flat_data_for_png = data  # Ist bereits eine flache Liste
        else:
            logger.error(f"Ungültiger Datentyp für PNG-Erstellung: {type(data)}")
            return

        if not flat_data_for_png:
            logger.warning(f"Keine Daten zum Erstellen von PNG {png_file} übergeben.")
            return

        # Verwende pathlib für Pfade
        png_path = self.heatmaps_dir / Path(png_file).name
        output_dir = png_path.parent  # Bereits ein Path-Objekt

        # Stelle sicher, dass der Ordner existiert (redundant, da in __init__ gemacht, aber sicher ist sicher)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Ordners für PNG {output_dir}: {e}")
            return

        temp_html_handle = None
        temp_html_path_obj = None  # pathlib Objekt
        create_temp_file = self.crop_enabled
        temp_png_path = png_path.with_suffix(png_path.suffix + ".tmp") if create_temp_file else png_path
        final_png_path = png_path
        driver = None

        try:
            # --- Erstelle temporäre Karte NUR für Screenshot ---
            logger.debug(f"Erstelle temporäre Satellitenkarte für Screenshot von {final_png_path}...")
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
            # Verwende die vorbereiteten flachen Daten
            for point in flat_data_for_png:
                try:
                    latitude = float(point['lat'])
                    longitude = float(point['lon'])
                    all_points.append([latitude, longitude])
                    if draw_path:
                        path_points.append([latitude, longitude])
                except (ValueError, KeyError, TypeError):
                    continue

            if all_points:
                # Radius/Blur Konfiguration (bleibt gleich)
                radius = 15;
                blur = 10;
                found_config = False
                # ... (Logik zum Finden von Radius/Blur basierend auf config_key_hint oder png_file) ...
                if config_key_hint and config_key_hint in HEATMAP_CONFIG:
                    radius = HEATMAP_CONFIG[config_key_hint].get("radius", radius)
                    blur = HEATMAP_CONFIG[config_key_hint].get("blur", blur)
                    found_config = True
                else:
                    for key, config_val in HEATMAP_CONFIG.items():
                        # Vergleiche den Dateinamen des PNG-Outputs
                        if isinstance(config_val, dict) and Path(
                                config_val.get("png_output", "")).name == final_png_path.name:
                            radius = config_val.get("radius", radius)
                            blur = config_val.get("blur", blur)
                            found_config = True
                            break
                if not found_config:
                    logger.warning(
                        f"Keine spezifische Radius/Blur-Konfiguration für {final_png_path.name} gefunden, verwende Defaults.")

                plugins.HeatMap(all_points, radius=radius, blur=blur).add_to(screenshot_map)

                if draw_path and len(path_points) > 1:
                    folium.PolyLine(path_points, color="blue", weight=1.0, opacity=1).add_to(screenshot_map)

                # Bounds-Anpassung (bleibt gleich)
                try:
                    points_array = np.array(all_points)
                    min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
                    min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()
                    # ... (Rest der Bounds-Logik wie in create_heatmap) ...
                    if min_lat < max_lat or min_lon < max_lon:
                        lat_margin = (max_lat - min_lat) * 0.05;
                        lon_margin = (max_lon - min_lon) * 0.05
                        epsilon = 1e-9
                        if lat_margin < epsilon: lat_margin = 0.0001
                        if lon_margin < epsilon: lon_margin = 0.0001
                        bounds = [[min_lat - lat_margin, min_lon - lon_margin],
                                  [max_lat + lat_margin, max_lon + lon_margin]]
                        screenshot_map.fit_bounds(bounds)
                    else:
                        screenshot_map.location = [min_lat, min_lon]
                        screenshot_map.zoom_start = max(GEO_CONFIG.get("zoom_start", 15), 18)
                except Exception as fit_err:
                    logger.error(f"Fehler beim Anpassen des Kartenausschnitts (fit_bounds) für Screenshot: {fit_err}")

            # Temporäre HTML mit pathlib erstellen
            temp_html_handle, temp_html_path_str = tempfile.mkstemp(suffix=".html", prefix="screenshot_")
            os.close(temp_html_handle)
            temp_html_path_obj = Path(temp_html_path_str)  # Konvertiere zu Path-Objekt
            screenshot_map.save(str(temp_html_path_obj))
            logger.debug(f"Temporäre Screenshot-HTML gespeichert: {temp_html_path_obj}")
            # --- Ende temporäre Karte ---

            # --- Selenium Screenshot (Plattformlogik bleibt gleich) ---
            options = ChromeOptions();
            service = None;
            system_name = platform.system()
            options.add_argument("--headless");
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox");
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1200")

            try:
                # ... (Plattformspezifische Service-Initialisierung wie zuvor) ...
                if system_name == "Linux":
                    system_driver_paths = ['/usr/bin/chromedriver', '/usr/lib/chromium-browser/chromedriver']
                    found_driver_path = None
                    for path in system_driver_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            found_driver_path = path;
                            logger.info(f"Verwende systeminstallierten ChromeDriver: {found_driver_path}");
                            break
                    if found_driver_path:
                        service = ChromeService(executable_path=found_driver_path)
                    else:
                        logger.warning("System-ChromeDriver nicht gefunden/ausführbar.")
                        if ChromeDriverManager:
                            logger.info("Versuche Fallback: webdriver-manager..."); service = ChromeService(
                                executable_path=ChromeDriverManager().install())
                        else:
                            raise WebDriverException(
                                "System-ChromeDriver nicht gefunden und webdriver-manager nicht installiert.")
                elif system_name == "Windows":
                    if ChromeDriverManager:
                        logger.info("Windows: Verwende webdriver-manager."); service = ChromeService(
                            executable_path=ChromeDriverManager().install())
                    else:
                        raise ImportError("webdriver-manager nicht installiert (benötigt für Windows).")
                else:  # Andere Systeme
                    if ChromeDriverManager:
                        logger.info(f"System '{system_name}': Versuche webdriver-manager."); service = ChromeService(
                            executable_path=ChromeDriverManager().install())
                    else:
                        raise ImportError(f"webdriver-manager nicht installiert (benötigt für {system_name}).")

                if service:
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    raise WebDriverException("ChromeDriver Service konnte nicht initialisiert werden.")

                # Lade HTML und mache Screenshot
                file_uri = temp_html_path_obj.as_uri()  # pathlib's as_uri() verwenden
                logger.debug(f"Lade HTML für Screenshot: {file_uri}")
                driver.get(file_uri)
                time.sleep(5)
                driver.save_screenshot(str(temp_png_path))  # Pfad als String übergeben
                logger.info(f"Screenshot erfolgreich erstellt: {temp_png_path}")

            except (WebDriverException, ImportError, Exception) as driver_err:
                logger.error(f"Fehler bei ChromeDriver: {driver_err}", exc_info=True)
                if temp_html_path_obj and temp_html_path_obj.exists():
                    try:
                        temp_html_path_obj.unlink()
                    except OSError:
                        pass
                return  # Abbruch
            finally:
                if driver: driver.quit(); logger.debug("ChromeDriver beendet.")
            # --- Ende Selenium ---

            # --- PNG Cropping (Logik bleibt gleich, aber mit pathlib) ---
            if self.crop_enabled:
                logger.info(f"Cropping für {final_png_path} wird durchgeführt.")
                try:
                    img = Image.open(str(temp_png_path))
                    width, height = img.size
                    crop_box = None
                    # ... (Berechnung der crop_box wie zuvor) ...
                    if self.use_center_crop:
                        percentage = self.crop_center_percentage / 100.0;
                        min_dimension = min(width, height)
                        crop_side = int(min_dimension * percentage)
                        if crop_side > 0:
                            left = int((width - crop_side) / 2); top = int((
                                                                                       height - crop_side) / 2); right = left + crop_side; bottom = top + crop_side; crop_box = (
                                left, top, right, bottom)
                        else:
                            logger.warning("Berechnete Crop-Seitenlänge <= 0. Kein Zuschnitt.")
                    else:
                        left_px = self.crop_pixel_left;
                        top_px = self.crop_pixel_top;
                        right_px = width - self.crop_pixel_right;
                        bottom_px = height - self.crop_pixel_bottom
                        if left_px < right_px and top_px < bottom_px:
                            crop_box = (left_px, top_px, right_px, bottom_px)
                        else:
                            logger.error(
                                f"Ungültige Pixel-Offset-Werte: L={left_px}, T={top_px}, R={right_px}, B={bottom_px}")

                    if crop_box and crop_box[0] < crop_box[2] and crop_box[1] < crop_box[3]:
                        cropped_img = img.crop(crop_box)
                        cropped_img.save(str(final_png_path))
                        logger.info(f"Bild erfolgreich auf {final_png_path} zugeschnitten.")
                        if create_temp_file and temp_png_path.exists():
                            try:
                                temp_png_path.unlink()
                            except OSError as rm_err:
                                logger.warning(f"Konnte temporäre PNG {temp_png_path} nicht löschen: {rm_err}")
                    else:
                        logger.error(f"Ungültige/keine Crop-Box: {crop_box}. Originalbild wird verwendet.")
                        if create_temp_file and temp_png_path.exists():
                            try:
                                if final_png_path.exists(): final_png_path.unlink()
                                temp_png_path.rename(final_png_path)
                                logger.info(f"Temporäres PNG zu {final_png_path} umbenannt (kein Crop).")
                            except OSError as ren_err:
                                logger.error(f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")
                        elif not create_temp_file:
                            logger.info(f"Kein Cropping, {final_png_path} direkt erstellt.")
                except Exception as crop_err:
                    logger.error(f"Fehler beim Zuschneiden: {crop_err}", exc_info=True)
                    if create_temp_file and temp_png_path.exists():
                        try:
                            if final_png_path.exists(): final_png_path.unlink()
                            temp_png_path.rename(final_png_path)
                            logger.info(f"Temporäres PNG zu {final_png_path} umbenannt (Crop fehlgeschlagen).")
                        except OSError as ren_err:
                            logger.error(f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")
            # --- ENDE PNG Cropping ---

        except Exception as e:
            logger.error(f"Allgemeiner Fehler beim Erstellen der PNG Datei {final_png_path}: {e}", exc_info=True)
            if create_temp_file and temp_png_path.exists():
                try:
                    temp_png_path.unlink()
                except OSError:
                    pass
        finally:
            # --- Temporäre HTML-Datei löschen ---
            if temp_html_path_obj and temp_html_path_obj.exists():
                try:
                    temp_html_path_obj.unlink()
                    logger.debug(f"Temporäre HTML-Datei {temp_html_path_obj} gelöscht.")
                except OSError as e:
                    logger.warning(f"Konnte temporäre HTML-Datei {temp_html_path_obj} nicht löschen: {e}")
            # ---


# --- __main__ Block für Tests (angepasst) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

    # Testdaten für mehrere Sessions
    test_data_s1 = [{'lat': 46.8118, 'lon': 7.1328}, {'lat': 46.8119, 'lon': 7.1329}]
    test_data_s2 = [{'lat': 46.8120, 'lon': 7.1330}, {'lat': 46.81185, 'lon': 7.13285}]
    test_data_multi = [test_data_s1, test_data_s2]  # Liste von Listen
    test_data_single = test_data_s1 + test_data_s2  # Flache Liste für Vergleich

    generator = HeatmapGenerator()

    # Test 1: Interaktive HTML (Single Session - wie bisher)
    print("\nTeste create_heatmap (Single Session)...")
    test_html_single = "heatmap_test_single.html"  # Im heatmaps Ordner
    generator.create_heatmap(test_data_single, test_html_single, draw_path=True, is_multi_session=False)

    # Test 2: Interaktive HTML (Multi Session - NEU)
    print("\nTeste create_heatmap (Multi Session)...")
    test_html_multi = "heatmap_test_multi.html"  # Im heatmaps Ordner
    # Wichtig: is_multi_session=True übergeben!
    generator.create_heatmap(test_data_multi, test_html_multi, draw_path=True, is_multi_session=True)

    # Test 3: PNG Erstellung (nimmt kombinierte Daten, auch wenn Multi übergeben wird)
    print("\nTeste save_html_as_png (mit Multi-Session Daten, PNG zeigt aber kombiniert)...")
    test_png_multi = "heatmap_test_multi_screenshot.png"  # Im heatmaps Ordner
    generator.save_html_as_png(test_data_multi, True, test_png_multi, config_key_hint=None, is_multi_session_data=True)

    print("\nTests abgeschlossen. Prüfe die Dateien im 'heatmaps' Ordner.")
