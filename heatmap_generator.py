# heatmap_generator.py
import folium
import folium.plugins as plugins
import numpy as np
import logging
from pathlib import Path
from config import GEO_CONFIG, HEATMAP_CONFIG
import io
import platform  # Importieren
import os  # Importieren
import shutil  # Importieren für shutil.which

# Importiere Selenium und verwandte Bibliotheken
try:
    from selenium import webdriver
    # --- Verwende Chrome ---
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    # --- ENDE ---
    from PIL import Image
    import time

    SELENIUM_AVAILABLE = True
    # Importiere webdriver-manager, falls vorhanden (für Windows/Fallback)
    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        ChromeDriverManager = None
        logging.info(
            "webdriver-manager nicht gefunden. Automatische Treiberinstallation für Chrome deaktiviert (außerhalb von Pi).")

except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium, Pillow oder webdriver-manager nicht installiert. PNG-Export ist nicht verfügbar.")
    logging.warning("Installieren mit: pip install selenium pillow webdriver-manager")

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    """
    Erstellt und verwaltet Heatmaps basierend auf GPS-Daten.
    Kann interaktive HTML-Heatmaps und statische PNG-Bilder generieren.
    """

    def __init__(self, heatmaps_base_dir="heatmaps"):
        """
        Initialisiert den HeatmapGenerator.

        Args:
            heatmaps_base_dir (str): Das Basisverzeichnis zum Speichern der Heatmaps.
        """
        self.map_center = GEO_CONFIG.get("map_center", (46.811819, 7.132838))
        self.heatmaps_dir = Path(heatmaps_base_dir)
        self.heatmaps_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"HeatmapGenerator initialisiert. Karten werden in '{self.heatmaps_dir}' gespeichert.")
        if not SELENIUM_AVAILABLE:
            logger.warning("PNG-Generierung ist aufgrund fehlender Bibliotheken deaktiviert.")

    def create_heatmap(self, data, html_file, draw_path, is_multi_session=False):
        """
        Erstellt eine interaktive Heatmap (HTML).

        Args:
            data (list): Entweder eine flache Liste von Punkten [{'lat': y, 'lon': x, ...}]
                         oder eine Liste von Listen von Punkten [[{...}, {...}], [{...}, {...}]]
                         für Multi-Session-Karten.
            html_file (str): Der Zieldateiname für die HTML-Datei (relativ zum heatmaps_dir).
            draw_path (bool): Ob der Pfad (PolyLine) gezeichnet werden soll.
            is_multi_session (bool): Gibt an, ob 'data' eine Liste von Sessions ist.
        """
        initial_zoom = GEO_CONFIG.get("zoom_start", 22)
        max_zoom_level = GEO_CONFIG.get("max_zoom", 22)  # Hole aus Config oder nimm Default 22

        google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        google_attr = 'Google Satellite'

        map_obj = folium.Map(
            location=self.map_center,
            zoom_start=initial_zoom,
            tiles=google_tiles_url,
            attr=google_attr,
            control_scale=True,  # Maßstab hinzufügen
            max_zoom=max_zoom_level
        )
        osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        folium.TileLayer(
            tiles="OpenStreetMap",
            attr=osm_attr,
            name='OpenStreetMap',
            overlay=False,  # Basiskarte, nicht Overlay
            control=True,
        ).add_to(map_obj)

        all_points_for_bounds = []  # Sammelt alle Punkte für die Kartengrenzen

        if is_multi_session and isinstance(data, list) and data and isinstance(data[0], list):
            logger.info(f"Erstelle Multi-Session Heatmap für {html_file} mit {len(data)} Sessions.")
            for idx, session_data in enumerate(reversed(data)):
                session_index = len(data) - 1 - idx
                layer_name = f"Mähvorgang -{idx + 1}"
                feature_group = folium.FeatureGroup(name=layer_name, show=(idx == 0))

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
                        continue

                if session_points:
                    all_points_for_bounds.extend(session_points)
                    config_key = self._find_config_key_by_output(html_file)
                    radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 3)
                    blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 3)

                    plugins.HeatMap(session_points, radius=radius, blur=blur).add_to(feature_group)

                    if draw_path and len(path_points) > 1:
                        folium.PolyLine(path_points, color="blue", weight=1.0, opacity=0.8).add_to(feature_group)

                    feature_group.add_to(map_obj)
                else:
                    logger.warning(f"Session {session_index} enthält keine gültigen Punkte für {html_file}.")

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
                    logger.warning(f"Ungültige Koordinaten in Punkt übersprungen: {point}")
                    continue

            if single_session_points:
                all_points_for_bounds = single_session_points
                config_key = self._find_config_key_by_output(html_file)
                radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 3)
                blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 3)

                plugins.HeatMap(single_session_points, radius=radius, blur=blur, name="Heatmap").add_to(map_obj)

                if draw_path and len(single_path_points) > 1:
                    folium.PolyLine(single_path_points, color="blue", weight=1.0, opacity=1, name="Pfad").add_to(
                        map_obj)
            else:
                logger.warning(f"Keine gültigen Punkte zum Erstellen der Heatmap {html_file} gefunden.")
        else:
            logger.error(f"Ungültiger Datentyp für Heatmap-Erstellung: {type(data)}. Erwartet: list.")
            return

        # Kartengrenzen anpassen (fit_bounds)
        if all_points_for_bounds:
            try:
                points_array = np.array(all_points_for_bounds)
                min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
                min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()

                if min_lat < max_lat or min_lon < max_lon:
                    lat_margin = (max_lat - min_lat) * 0.05
                    lon_margin = (max_lon - min_lon) * 0.05
                    epsilon = 1e-9
                    if lat_margin < epsilon: lat_margin = 0.0001
                    if lon_margin < epsilon: lon_margin = 0.0001

                    bounds = [
                        [min_lat - lat_margin, min_lon - lon_margin],
                        [max_lat + lat_margin, max_lon + lon_margin]
                    ]
                    map_obj.fit_bounds(bounds, max_zoom=max_zoom_level)
                    logger.debug(f"Kartenausschnitt für {html_file} angepasst an Grenzen: {bounds}")
                else:  # Nur ein Punkt oder alle Punkte identisch
                    map_obj.location = [min_lat, min_lon]
                    map_obj.zoom_start = min(max(initial_zoom, 22), max_zoom_level)
                    logger.debug(
                        f"Nur ein Punkt oder identische Punkte in {html_file}, zentriere Karte auf {map_obj.location} mit Zoom {map_obj.zoom_start}")

            except Exception as fit_err:
                logger.error(f"Fehler beim Anpassen des Kartenausschnitts (fit_bounds) für {html_file}: {fit_err}",
                             exc_info=True)
        else:
            logger.warning(
                f"Keine Punkte für Bounds-Anpassung in {html_file} vorhanden. Verwende Standardzentrum und -zoom.")
            map_obj.location = self.map_center
            map_obj.zoom_start = initial_zoom

        folium.LayerControl(collapsed=False).add_to(map_obj)

        # Speichern der HTML-Datei
        try:
            html_path = self.heatmaps_dir / Path(html_file).name
            map_obj.save(str(html_path))
            logger.info(f"Interaktive Heatmap erstellt: {html_path}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der interaktiven Heatmap {html_path}: {e}", exc_info=True)

    def _find_config_key_by_output(self, output_filename):
        """Hilfsmethode, um den HEATMAP_CONFIG-Schlüssel anhand des Ausgabedateinamens zu finden."""
        output_path = Path(output_filename).name  # Nur den Dateinamen vergleichen
        for key, config_val in HEATMAP_CONFIG.items():
            if isinstance(config_val, dict):
                # Vergleiche HTML- oder PNG-Ausgabe
                if Path(config_val.get("output", "")).name == output_path or \
                        Path(config_val.get("png_output", "")).name == output_path:
                    return key
        logger.warning(f"Kein Konfigurationsschlüssel für Ausgabedatei '{output_filename}' gefunden.")
        return None  # Kein Schlüssel gefunden

    def save_html_as_png(self, data, draw_path, png_file, config_key_hint=None, is_multi_session_data=False, width=1024,
                         height=768, delay=5):
        """
        Erstellt eine PNG-Version einer Heatmap mit Selenium und Chrome/ChromeDriver.

        Args:
            data (list): Datenpunkte (flach oder Liste von Listen).
            draw_path (bool): Ob der Pfad gezeichnet werden soll.
            png_file (str): Der Zieldateiname für die PNG-Datei (relativ zum heatmaps_dir).
            config_key_hint (str, optional): Ein Hinweis auf den HEATMAP_CONFIG-Schlüssel.
            is_multi_session_data (bool): Gibt an, ob 'data' eine Liste von Sessions ist.
            width (int): Breite des Browserfensters für den Screenshot.
            height (int): Höhe des Browserfensters für den Screenshot.
            delay (int): Wartezeit in Sekunden, bis die Karte geladen ist.
        """
        if not SELENIUM_AVAILABLE:
            logger.error("PNG-Export nicht möglich. Selenium/Pillow fehlt.")
            return

        temp_html_path = self.heatmaps_dir / f"temp_{Path(png_file).stem}.html"

        try:
            # --- Erstelle temporäre Karte für PNG ---
            initial_zoom_png = GEO_CONFIG.get("zoom_start", 22)
            max_zoom_level_png = GEO_CONFIG.get("max_zoom", 22)
            google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'  # Satellit für PNG
            google_attr = 'Google Satellite'

            png_map_obj = folium.Map(
                location=self.map_center,
                zoom_start=initial_zoom_png,
                tiles=google_tiles_url,
                attr=google_attr,
                control_scale=False,  # Maßstab im PNG oft nicht nötig
                zoom_control=False,  # Zoomsteuerung im PNG nicht nötig
                max_zoom=max_zoom_level_png
            )

            # --- Datenpunkte für PNG vorbereiten (immer flach) ---
            all_points_for_png = []
            path_points_for_png = []

            if is_multi_session_data and isinstance(data, list) and data and isinstance(data[0], list):
                for session in data:
                    for point in session:
                        try:
                            lat, lon = float(point['lat']), float(point['lon'])
                            all_points_for_png.append([lat, lon])
                            if draw_path: path_points_for_png.append([lat, lon])
                        except (ValueError, KeyError, TypeError):
                            continue
            elif isinstance(data, list):
                for point in data:
                    try:
                        lat, lon = float(point['lat']), float(point['lon'])
                        all_points_for_png.append([lat, lon])
                        if draw_path: path_points_for_png.append([lat, lon])
                    except (ValueError, KeyError, TypeError):
                        continue

            if all_points_for_png:
                # --- Radius/Blur bestimmen ---
                config_key = config_key_hint or self._find_config_key_by_output(png_file)
                radius = HEATMAP_CONFIG.get(config_key, {}).get("radius", 3)
                blur = HEATMAP_CONFIG.get(config_key, {}).get("blur", 3)
                plugins.HeatMap(all_points_for_png, radius=radius, blur=blur).add_to(png_map_obj)
                if draw_path and len(path_points_for_png) > 1:
                    folium.PolyLine(path_points_for_png, color="blue", weight=1.0, opacity=0.8).add_to(png_map_obj)

                # --- Kartenausschnitt anpassen ---
                try:
                    points_array = np.array(all_points_for_png)
                    min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
                    min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()
                    if min_lat < max_lat or min_lon < max_lon:
                        bounds = [[min_lat, min_lon], [max_lat, max_lon]]
                        png_map_obj.fit_bounds(bounds, max_zoom=max_zoom_level_png)
                    else:
                        png_map_obj.location = [min_lat, min_lon]
                        png_map_obj.zoom_start = min(max(initial_zoom_png, 22), max_zoom_level_png)
                except Exception as fit_err:
                    logger.warning(
                        f"Fehler beim Anpassen des PNG-Kartenausschnitts für {png_file}: {fit_err}. Verwende Standard.")
                    png_map_obj.location = self.map_center
                    png_map_obj.zoom_start = initial_zoom_png
            else:
                logger.warning(f"Keine Daten zum Generieren der PNG-Datei {png_file}.")
                # Hier entscheiden, ob eine leere Karte gespeichert werden soll

            # Speichere die temporäre HTML für Selenium
            png_map_obj.save(str(temp_html_path))

            # --- Selenium Screenshot mit Chrome ---
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")  # Oft nötig im headless mode
            options.add_argument("--no-sandbox")  # Wichtig für Linux/Docker
            options.add_argument("--disable-dev-shm-usage")  # Wichtig für Linux/Docker
            options.add_argument(f"--window-size={width},{height}")  # Fenstergröße setzen

            driver = None
            service = None
            system_name = platform.system()
            arch = platform.machine()  # Architektur prüfen

            try:
                # --- Plattformspezifische Treiberbehandlung für ChromeDriver ---
                driver_path = None

                # 1. Prüfe auf Linux (Raspberry Pi)
                if system_name == "Linux":
                    # Suche an Standardorten für apt install chromium-chromedriver
                    system_driver_paths = [
                        '/usr/lib/chromium-browser/chromedriver',
                        '/usr/bin/chromedriver'
                    ]
                    for path in system_driver_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            driver_path = path
                            logger.info(f"Verwende System-ChromeDriver (Linux): {driver_path}")
                            break
                    if not driver_path:
                        logger.warning(
                            "System-ChromeDriver auf Linux nicht gefunden. Versuche webdriver-manager (falls installiert).")
                        # Fallback zu webdriver-manager, falls auf Pi benötigt und installiert
                        if ChromeDriverManager:
                            try:
                                driver_path = ChromeDriverManager().install()
                                logger.info(
                                    f"Verwende ChromeDriver via webdriver-manager (Linux Fallback): {driver_path}")
                            except Exception as wdm_err:
                                logger.error(f"Fehler bei webdriver-manager auf Linux: {wdm_err}")
                                raise FileNotFoundError(
                                    "ChromeDriver nicht gefunden und webdriver-manager fehlgeschlagen.")
                        else:
                            raise FileNotFoundError(
                                "ChromeDriver auf Linux nicht gefunden und webdriver-manager nicht installiert.")

                # 2. Prüfe auf Windows
                elif system_name == "Windows":
                    if ChromeDriverManager:
                        try:
                            driver_path = ChromeDriverManager().install()
                            logger.info(f"Verwende ChromeDriver via webdriver-manager (Windows): {driver_path}")
                        except Exception as wdm_err:
                            logger.error(f"Fehler bei webdriver-manager auf Windows: {wdm_err}")
                            raise FileNotFoundError(
                                "ChromeDriver konnte via webdriver-manager nicht installiert werden.")
                    else:
                        # Alternativ: Prüfen, ob chromedriver.exe im PATH ist
                        driver_in_path = shutil.which("chromedriver.exe")
                        if driver_in_path:
                            driver_path = driver_in_path
                            logger.info(f"Verwende ChromeDriver aus PATH (Windows): {driver_path}")
                        else:
                            raise FileNotFoundError(
                                "webdriver-manager nicht installiert und chromedriver.exe nicht im PATH gefunden.")

                # 3. Andere Systeme (z.B. macOS)
                else:
                    if ChromeDriverManager:
                        try:
                            driver_path = ChromeDriverManager().install()
                            logger.info(f"Verwende ChromeDriver via webdriver-manager ({system_name}): {driver_path}")
                        except Exception as wdm_err:
                            logger.error(f"Fehler bei webdriver-manager auf {system_name}: {wdm_err}")
                            raise FileNotFoundError(
                                f"ChromeDriver konnte via webdriver-manager für {system_name} nicht installiert werden.")
                    else:
                        # Alternativ: Prüfen, ob chromedriver im PATH ist
                        driver_in_path = shutil.which("chromedriver")
                        if driver_in_path:
                            driver_path = driver_in_path
                            logger.info(f"Verwende ChromeDriver aus PATH ({system_name}): {driver_path}")
                        else:
                            raise FileNotFoundError(
                                f"webdriver-manager nicht installiert und chromedriver nicht im PATH für {system_name} gefunden.")

                # Initialisiere den Service und WebDriver
                if driver_path:
                    service = ChromeService(executable_path=driver_path)
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    # Sollte nicht passieren, wenn die Logik oben greift
                    raise webdriver.support.wait.WebDriverException("ChromeDriver Pfad konnte nicht ermittelt werden.")

                # --- Rest der Screenshot-Logik ---
                local_url = temp_html_path.resolve().as_uri()
                driver.get(local_url)
                logger.debug(f"Warte {delay} Sekunden, bis die Karte '{temp_html_path}' für PNG geladen ist...")
                time.sleep(delay)
                png_data = driver.get_screenshot_as_png()
                output_path_png = self.heatmaps_dir / Path(png_file).name
                img = Image.open(io.BytesIO(png_data))
                img.save(output_path_png)
                logger.info(f"PNG-Heatmap erfolgreich gespeichert: {output_path_png}")

            except (FileNotFoundError, webdriver.support.wait.WebDriverException,
                    Exception) as e:  # FileNotFoundError hinzugefügt
                logger.error(f"Fehler beim Erstellen des PNG-Screenshots für {png_file}: {e}", exc_info=True)
            finally:
                if driver:
                    driver.quit()

        finally:
            # Temporäre HTML-Datei löschen
            try:
                if temp_html_path.exists():
                    temp_html_path.unlink()
                    logger.debug(f"Temporäre HTML-Datei {temp_html_path} gelöscht.")
            except OSError as e:
                logger.error(f"Fehler beim Löschen der temporären HTML-Datei {temp_html_path}: {e}")


# Beispiel für die Verwendung (kann entfernt oder in __main__ verschoben werden)
if __name__ == '__main__':
    # Beispielhafte Konfiguration für Tests
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
    GEO_CONFIG["map_center"] = (46.8118, 7.1328)
    GEO_CONFIG["zoom_start"] = 22
    GEO_CONFIG["max_zoom"] = 22  # Testwert
    HEATMAP_CONFIG["test_single"] = {"output": "heatmaps/test_single.html", "png_output": "heatmaps/test_single.png",
                                     "radius": 5, "blur": 5}
    HEATMAP_CONFIG["test_multi"] = {"output": "heatmaps/test_multi.html", "png_output": "heatmaps/test_multi.png",
                                    "radius": 3, "blur": 3}

    # Beispiel-Datenpunkte
    single_data = [
        {'lat': 46.8117, 'lon': 7.1327, 'value': 1},
        {'lat': 46.8118, 'lon': 7.1328, 'value': 1},
        {'lat': 46.8119, 'lon': 7.1329, 'value': 1},
        {'lat': 46.81185, 'lon': 7.13285, 'value': 1},
    ]
    multi_data = [
        [{'lat': 46.8117, 'lon': 7.1327}, {'lat': 46.81175, 'lon': 7.13275}],  # Session 1
        [{'lat': 46.8119, 'lon': 7.1329}, {'lat': 46.81195, 'lon': 7.13295}],  # Session 2
    ]

    gen = HeatmapGenerator()

    # Teste einzelne Heatmap
    logger.info("Teste einzelne Heatmap (HTML)...")
    gen.create_heatmap(single_data, "heatmaps/test_single.html", draw_path=True, is_multi_session=False)
    if SELENIUM_AVAILABLE:
        logger.info("Teste einzelne Heatmap (PNG)...")
        gen.save_html_as_png(single_data, draw_path=True, png_file="heatmaps/test_single.png",
                             config_key_hint="test_single")

    # Teste Multi-Session Heatmap
    logger.info("Teste Multi-Session Heatmap (HTML)...")
    gen.create_heatmap(multi_data, "heatmaps/test_multi.html", draw_path=True, is_multi_session=True)
    if SELENIUM_AVAILABLE:
        logger.info("Teste Multi-Session Heatmap (PNG)...")
        gen.save_html_as_png(multi_data, draw_path=True, png_file="heatmaps/test_multi.png",
                             config_key_hint="test_multi", is_multi_session_data=True)

    logger.info("Heatmap-Generierungstests abgeschlossen.")
