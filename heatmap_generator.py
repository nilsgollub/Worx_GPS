# heatmap_generator.py
import folium
import folium.plugins as plugins
import numpy as np
import logging
from pathlib import Path
# Stelle sicher, dass HEATMAP_CONFIG hier importiert wird
from config import GEO_CONFIG, HEATMAP_CONFIG
import io
import platform
import os
import shutil
# NEU: Importiere datetime für Zeitstempel-Formatierung
from datetime import datetime

# Importiere Selenium und verwandte Bibliotheken
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from PIL import Image
    import time

    SELENIUM_AVAILABLE = True
    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        ChromeDriverManager = None
        logging.info(
            "webdriver-manager nicht gefunden. Automatische Treiberinstallation für Chrome deaktiviert (außerhalb von Pi).")

except ImportError:
    SELENIUM_AVAILABLE = False
    Image = None
    logging.warning(
        "Selenium, Pillow oder webdriver-manager nicht installiert. PNG-Export ist nicht verfügbar.")
    logging.warning(
        "Installieren mit: pip install selenium pillow webdriver-manager")

logger = logging.getLogger(__name__)

# Standardfarben für Multi-Session-Pfade (unverändert)
DEFAULT_PATH_COLORS = ['blue', 'green', 'red', 'purple', 'orange', 'darkred',
                       'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                       'lightgreen', 'gray', 'black', 'lightgray']


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

        # --- Cropping Konfiguration (unverändert) ---
        self.crop_enabled = GEO_CONFIG.get("crop_enabled", False)
        self.crop_center_percentage = GEO_CONFIG.get("crop_center_percentage")
        self.use_center_crop = False
        self.crop_pixel_left = GEO_CONFIG.get("crop_pixel_left")
        self.crop_pixel_top = GEO_CONFIG.get("crop_pixel_top")
        self.crop_pixel_right = GEO_CONFIG.get("crop_pixel_right")
        self.crop_pixel_bottom = GEO_CONFIG.get("crop_pixel_bottom")

        if self.crop_enabled:
            if self.crop_center_percentage is not None and isinstance(self.crop_center_percentage, (int,
                                                                                                    float)) and 0 < self.crop_center_percentage <= 100:
                self.use_center_crop = True
                if self.crop_center_percentage < 100:
                    logger.info(
                        f"PNG Cropping (Center Percentage) aktiviert: {self.crop_center_percentage}%")
                else:
                    logger.info(
                        "PNG Cropping (Center Percentage) ist 100%, kein Zuschnitt erfolgt.")
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

        logger.info(
            f"HeatmapGenerator initialisiert. Karten werden in '{self.heatmaps_dir}' gespeichert.")
        if not SELENIUM_AVAILABLE:
            logger.warning(
                "PNG-Generierung ist aufgrund fehlender Bibliotheken deaktiviert.")
        elif self.crop_enabled and Image is None:
            logger.warning(
                "PNG Cropping ist aktiviert, aber Pillow ist nicht installiert. Cropping wird deaktiviert.")
            self.crop_enabled = False

    # --- NEU: Hilfsfunktion zur Zeitstempelformatierung ---
    def _format_timestamp(self, timestamp):
        """Formatiert einen Unix-Timestamp oder ISO-String lesbar."""
        if timestamp is None:
            return "N/A"
        try:
            # Versuche, als Unix-Timestamp (float oder int) zu interpretieren
            dt_object = datetime.fromtimestamp(float(timestamp))
            return dt_object.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            try:
                # Versuche, als ISO-String zu interpretieren
                # Entferne mögliche Zeitzoneninfo am Ende (z.B. +00:00 oder Z)
                ts_str = str(timestamp).split('+')[0].split('Z')[0]
                # Behandle Millisekunden, falls vorhanden
                if '.' in ts_str:
                    dt_object = datetime.fromisoformat(ts_str.split('.')[0])
                else:
                    dt_object = datetime.fromisoformat(ts_str)
                return dt_object.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                # Wenn beides fehlschlägt, gib den Originalwert zurück
                logger.warning(f"Konnte Zeitstempel nicht formatieren: {timestamp}")
                return str(timestamp)

    # --- ENDE NEU ---

    def create_heatmap(self, data, html_file, draw_path, is_multi_session=False):
        """
        Erstellt eine interaktive Heatmap (HTML).

        Args:
            data (list): Entweder eine flache Liste von Punkten [{'lat': y, 'lon': x, 'timestamp': ts, ...}]
                         oder eine Liste von Listen von Punkten [[{...}, {...}], [{...}, {...}]]
                         für Multi-Session-Karten.
            html_file (str): Der Zieldateiname für die HTML-Datei (relativ zum heatmaps_dir).
            draw_path (bool): Ob der Pfad (PolyLine) gezeichnet werden soll.
            is_multi_session (bool): Gibt an, ob 'data' eine Liste von Sessions ist.
        """
        initial_zoom = GEO_CONFIG.get("zoom_start", 22)
        max_zoom_level = GEO_CONFIG.get("max_zoom", 22)

        google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        google_attr = 'Google Satellite'

        map_obj = folium.Map(
            location=self.map_center,
            zoom_start=initial_zoom,
            tiles=google_tiles_url,
            attr=google_attr,
            control_scale=True,
            max_zoom=max_zoom_level
        )
        osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        folium.TileLayer(
            tiles="OpenStreetMap",
            attr=osm_attr,
            name='OpenStreetMap',
            overlay=False,
            control=True,
        ).add_to(map_obj)

        all_points_for_bounds = []

        # --- Konfigurationswerte für diese Karte holen ---
        config_key = self._find_config_key_by_output(html_file)
        map_config = HEATMAP_CONFIG.get(config_key, {})
        heatmap_radius = map_config.get("radius", 3)
        heatmap_blur = map_config.get("blur", 3)
        path_color_default = "blue"
        path_weight = map_config.get("path_weight", 1.0)
        path_opacity = map_config.get("path_opacity", 0.8)
        show_markers = map_config.get("show_start_end_markers", True)
        path_colors_list = map_config.get("path_colors", DEFAULT_PATH_COLORS)
        # --- NEU: Option für HeatMapWithTime ---
        use_time_heatmap = map_config.get("use_heatmap_with_time", False)
        # --- ENDE NEU ---

        if is_multi_session and isinstance(data, list) and data and isinstance(data[0], list):
            logger.info(
                f"Erstelle Multi-Session Heatmap für {html_file} mit {len(data)} Sessions.")
            path_groups = []
            # --- NEU: Daten für HeatMapWithTime sammeln (falls genutzt) ---
            heatmap_time_data = []
            heatmap_time_index = []
            has_timestamps = False  # Prüfen, ob überhaupt Zeitstempel da sind
            # --- ENDE NEU ---

            for idx, session_data in enumerate(reversed(data)):
                session_index = len(data) - 1 - idx
                heatmap_layer_name = f"Heatmap -{idx + 1}"
                path_layer_name = f"Pfad -{idx + 1}"
                show_layer = (idx == 0)

                heatmap_feature_group = folium.FeatureGroup(
                    name=heatmap_layer_name, show=show_layer)

                session_points_coords = []  # Nur Koordinaten für normale Heatmap
                session_points_full = []  # Ganze Punkte für Zeitstempel etc.
                path_points_coords = []  # Nur Koordinaten für Polyline

                for point in session_data:
                    try:
                        latitude = float(point['lat'])
                        longitude = float(point['lon'])
                        timestamp = point.get('timestamp')  # Zeitstempel holen
                        if timestamp is not None:
                            has_timestamps = True

                        session_points_coords.append([latitude, longitude])
                        session_points_full.append(point)  # Ganzen Punkt speichern
                        if draw_path:
                            path_points_coords.append([latitude, longitude])
                    except (ValueError, KeyError, TypeError):
                        continue

                if session_points_coords:
                    all_points_for_bounds.extend(session_points_coords)

                    # --- NEU: Heatmap oder HeatMapWithTime hinzufügen ---
                    if use_time_heatmap and has_timestamps:
                        # Daten für diesen Zeitschritt (Session) hinzufügen
                        heatmap_time_data.append(session_points_coords)
                        # Zeitindex hinzufügen (z.B. erster Zeitstempel der Session)
                        first_ts = session_points_full[0].get('timestamp')
                        heatmap_time_index.append(self._format_timestamp(first_ts))
                        # HeatMapWithTime wird später hinzugefügt
                    else:
                        # Normale Heatmap zur Gruppe hinzufügen
                        plugins.HeatMap(session_points_coords, radius=heatmap_radius, blur=heatmap_blur).add_to(
                            heatmap_feature_group)
                        heatmap_feature_group.add_to(map_obj)
                    # --- ENDE NEU ---

                    # Pfad hinzufügen (wenn gewünscht und möglich)
                    if draw_path and len(path_points_coords) > 1:
                        path_feature_group = folium.FeatureGroup(
                            name=path_layer_name, show=show_layer)
                        current_path_color = path_colors_list[idx % len(
                            path_colors_list)]

                        folium.PolyLine(
                            path_points_coords,
                            color=current_path_color,
                            weight=path_weight,
                            opacity=path_opacity
                        ).add_to(path_feature_group)

                        # Start-/End-Marker hinzufügen
                        if show_markers:
                            # --- NEU: Zeitstempel für Popups holen ---
                            start_ts = session_points_full[0].get('timestamp')
                            end_ts = session_points_full[-1].get('timestamp')
                            start_popup = f"Start Session {session_index + 1}<br>Zeit: {self._format_timestamp(start_ts)}"
                            end_popup = f"Ende Session {session_index + 1}<br>Zeit: {self._format_timestamp(end_ts)}"
                            # --- ENDE NEU ---

                            folium.CircleMarker(
                                location=path_points_coords[0],
                                radius=3, color=current_path_color, fill=True,
                                fill_color=current_path_color, fill_opacity=0.9,
                                popup=start_popup  # Geändertes Popup
                            ).add_to(path_feature_group)
                            folium.CircleMarker(
                                location=path_points_coords[-1],
                                radius=3, color=current_path_color, fill=True,
                                fill_color=current_path_color, fill_opacity=0.9,
                                popup=end_popup  # Geändertes Popup
                            ).add_to(path_feature_group)

                        path_groups.append(path_feature_group)
                else:
                    logger.warning(
                        f"Session {session_index} enthält keine gültigen Punkte für {html_file}.")

            # --- NEU: HeatMapWithTime zur Karte hinzufügen (falls genutzt) ---
            if use_time_heatmap and heatmap_time_data and heatmap_time_index:
                logger.info(f"Füge HeatMapWithTime für {html_file} hinzu.")
                # Index muss sortiert sein, reversed() oben stellt das sicher
                plugins.HeatMapWithTime(
                    data=heatmap_time_data,
                    index=heatmap_time_index,
                    radius=heatmap_radius,
                    blur=heatmap_blur,
                    auto_play=False,
                    display_index=True,
                    name="Heatmap (Zeitverlauf)"  # Eigener Name im LayerControl
                ).add_to(map_obj)
            elif use_time_heatmap and not has_timestamps:
                logger.warning(
                    f"HeatMapWithTime für {html_file} aktiviert, aber keine Zeitstempel in Daten gefunden. Fallback zur normalen Heatmap.")
            # --- ENDE NEU ---

            for pg in path_groups:
                pg.add_to(map_obj)

        elif isinstance(data, list):  # Normale, einzelne Session/Datenmenge
            logger.info(f"Erstelle Single-Session Heatmap für {html_file}.")
            single_session_points_coords = []
            single_session_points_full = []
            single_path_points_coords = []
            has_timestamps_single = False  # Prüfen für einzelne Session

            for point in data:
                try:
                    latitude = float(point['lat'])
                    longitude = float(point['lon'])
                    timestamp = point.get('timestamp')
                    if timestamp is not None:
                        has_timestamps_single = True

                    single_session_points_coords.append([latitude, longitude])
                    single_session_points_full.append(point)
                    if draw_path:
                        single_path_points_coords.append([latitude, longitude])
                except (ValueError, KeyError, TypeError):
                    logger.warning(
                        f"Ungültige Koordinaten in Punkt übersprungen: {point}")
                    continue

            if single_session_points_coords:
                all_points_for_bounds = single_session_points_coords

                # --- NEU: Heatmap oder HeatMapWithTime hinzufügen ---
                if use_time_heatmap and has_timestamps_single:
                    logger.info(f"Füge HeatMapWithTime für {html_file} hinzu.")
                    # Daten für HeatMapWithTime vorbereiten (jeder Punkt ein Zeitschritt)
                    time_data = [[coords] for coords in single_session_points_coords]
                    time_index = [self._format_timestamp(p.get('timestamp')) for p in single_session_points_full]

                    plugins.HeatMapWithTime(
                        data=time_data,
                        index=time_index,
                        radius=heatmap_radius,
                        blur=heatmap_blur,
                        auto_play=False,
                        display_index=True,
                        name="Heatmap (Zeitverlauf)"
                    ).add_to(map_obj)
                elif use_time_heatmap and not has_timestamps_single:
                    logger.warning(
                        f"HeatMapWithTime für {html_file} aktiviert, aber keine Zeitstempel gefunden. Fallback zur normalen Heatmap.")
                    plugins.HeatMap(single_session_points_coords, radius=heatmap_radius, blur=heatmap_blur,
                                    name="Heatmap").add_to(map_obj)
                else:
                    # Normale Heatmap
                    plugins.HeatMap(single_session_points_coords, radius=heatmap_radius, blur=heatmap_blur,
                                    name="Heatmap").add_to(map_obj)
                # --- ENDE NEU ---

                # Pfad hinzufügen (wenn gewünscht und möglich)
                if draw_path and len(single_path_points_coords) > 1:
                    path_group = folium.FeatureGroup(name="Pfad", show=True)
                    current_path_color = path_colors_list[0] if path_colors_list else path_color_default

                    folium.PolyLine(
                        single_path_points_coords,
                        color=current_path_color,
                        weight=path_weight,
                        opacity=path_opacity
                    ).add_to(path_group)

                    # Start-/End-Marker hinzufügen
                    if show_markers:
                        # --- NEU: Zeitstempel für Popups holen ---
                        start_ts_single = single_session_points_full[0].get('timestamp')
                        end_ts_single = single_session_points_full[-1].get('timestamp')
                        start_popup_single = f"Start<br>Zeit: {self._format_timestamp(start_ts_single)}"
                        end_popup_single = f"Ende<br>Zeit: {self._format_timestamp(end_ts_single)}"
                        # --- ENDE NEU ---

                        folium.CircleMarker(
                            location=single_path_points_coords[0],
                            radius=3, color=current_path_color, fill=True,
                            fill_color=current_path_color, fill_opacity=0.9,
                            popup=start_popup_single  # Geändertes Popup
                        ).add_to(path_group)
                        folium.CircleMarker(
                            location=single_path_points_coords[-1],
                            radius=3, color=current_path_color, fill=True,
                            fill_color=current_path_color, fill_opacity=0.9,
                            popup=end_popup_single  # Geändertes Popup
                        ).add_to(path_group)

                    path_group.add_to(map_obj)

            else:
                logger.warning(
                    f"Keine gültigen Punkte zum Erstellen der Heatmap {html_file} gefunden.")
        else:
            logger.error(
                f"Ungültiger Datentyp für Heatmap-Erstellung: {type(data)}. Erwartet: list.")
            return

        # Kartengrenzen anpassen (fit_bounds) - (unverändert)
        if all_points_for_bounds:
            try:
                points_array = np.array(all_points_for_bounds)
                min_lat, max_lat = points_array[:, 0].min(
                ), points_array[:, 0].max()
                min_lon, max_lon = points_array[:, 1].min(
                ), points_array[:, 1].max()

                if min_lat < max_lat or min_lon < max_lon:
                    lat_margin = (max_lat - min_lat) * 0.05
                    lon_margin = (max_lon - min_lon) * 0.05
                    epsilon = 1e-9
                    if lat_margin < epsilon:
                        lat_margin = 0.0001
                    if lon_margin < epsilon:
                        lon_margin = 0.0001

                    bounds = [
                        [min_lat - lat_margin, min_lon - lon_margin],
                        [max_lat + lat_margin, max_lon + lon_margin]
                    ]
                    map_obj.fit_bounds(bounds, max_zoom=max_zoom_level)
                    logger.debug(
                        f"Kartenausschnitt für {html_file} angepasst an Grenzen: {bounds}")
                else:
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

        # Messwerkzeug hinzufügen (unverändert)
        plugins.MeasureControl(
            position='topleft',
            primary_length_unit='meters',
            secondary_length_unit='kilometers',
            primary_area_unit='sqmeters',
            secondary_area_unit='hectares'
        ).add_to(map_obj)

        # LayerControl hinzufügen (bleibt collapsed=True)
        folium.LayerControl(collapsed=True).add_to(map_obj)

        # Speichern der HTML-Datei - (unverändert)
        try:
            html_path = self.heatmaps_dir / Path(html_file).name
            map_obj.save(str(html_path))
            logger.info(f"Interaktive Heatmap erstellt: {html_path}")
        except Exception as e:
            logger.error(
                f"Fehler beim Speichern der interaktiven Heatmap {html_path}: {e}", exc_info=True)

    def _find_config_key_by_output(self, output_filename):
        """Hilfsmethode, um den HEATMAP_CONFIG-Schlüssel anhand des Ausgabedateinamens zu finden."""
        output_path = Path(output_filename).name
        for key, config_val in HEATMAP_CONFIG.items():
            if isinstance(config_val, dict):
                if Path(config_val.get("output", "")).name == output_path or \
                        Path(config_val.get("png_output", "")).name == output_path:
                    return key
        logger.warning(
            f"Kein Konfigurationsschlüssel für Ausgabedatei '{output_filename}' gefunden.")
        return None

    # --- save_html_as_png Methode bleibt weitgehend unverändert ---
    # (Die PNG-Generierung berücksichtigt HeatMapWithTime und Zeitstempel-Popups NICHT)
    def save_html_as_png(self, data, draw_path, png_file, config_key_hint=None, is_multi_session_data=False, width=1024,
                         height=768, delay=5):
        """
        Erstellt eine PNG-Version einer Heatmap mit Selenium und Chrome/ChromeDriver.
        Führt optional ein Cropping basierend auf GEO_CONFIG durch.
        HINWEIS: Diese Methode rendert derzeit KEINE Start/End-Marker, Zeitstempel-Popups,
                 HeatMapWithTime oder Messwerkzeuge.
                 Sie verwendet die konfigurierten Pfad-Stile.
        """
        if not SELENIUM_AVAILABLE:
            logger.error("PNG-Export nicht möglich. Selenium/Pillow fehlt.")
            return

        temp_html_path = self.heatmaps_dir / f"temp_{Path(png_file).stem}.html"
        output_path_png = self.heatmaps_dir / Path(png_file).name
        temp_png_path = output_path_png.with_suffix(
            output_path_png.suffix + ".tmp") if self.crop_enabled else output_path_png
        final_png_path = output_path_png

        try:
            # --- Erstelle temporäre Karte für PNG (vereinfacht) ---
            initial_zoom_png = GEO_CONFIG.get("zoom_start", 22)
            max_zoom_level_png = GEO_CONFIG.get("max_zoom", 22)
            google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
            google_attr = 'Google Satellite'

            png_map_obj = folium.Map(
                location=self.map_center,
                zoom_start=initial_zoom_png,
                tiles=google_tiles_url,
                attr=google_attr,
                control_scale=False,
                zoom_control=False,
                max_zoom=max_zoom_level_png
            )

            all_points_for_png = []
            path_points_for_png = []

            # Datenpunkte sammeln (unverändert)
            if is_multi_session_data and isinstance(data, list) and data and isinstance(data[0], list):
                for session in data:
                    for point in session:
                        try:
                            lat, lon = float(point['lat']), float(point['lon'])
                            all_points_for_png.append([lat, lon])
                            if draw_path:
                                path_points_for_png.append([lat, lon])
                        except (ValueError, KeyError, TypeError):
                            continue
            elif isinstance(data, list):
                for point in data:
                    try:
                        lat, lon = float(point['lat']), float(point['lon'])
                        all_points_for_png.append([lat, lon])
                        if draw_path:
                            path_points_for_png.append([lat, lon])
                    except (ValueError, KeyError, TypeError):
                        continue

            if all_points_for_png:
                # Radius/Blur bestimmen (unverändert)
                config_key = config_key_hint or self._find_config_key_by_output(
                    png_file)
                map_config = HEATMAP_CONFIG.get(config_key, {})
                radius = map_config.get("radius", 3)
                blur = map_config.get("blur", 3)
                plugins.HeatMap(all_points_for_png, radius=radius,
                                blur=blur).add_to(png_map_obj)

                # Pfad für PNG (verwendet konfiguriertes Styling, unverändert)
                if draw_path and len(path_points_for_png) > 1:
                    png_path_weight = map_config.get("path_weight", 1.0)
                    png_path_opacity = map_config.get("path_opacity", 0.8)
                    png_path_colors_list = map_config.get(
                        "path_colors", DEFAULT_PATH_COLORS)
                    png_path_color = png_path_colors_list[0] if png_path_colors_list else "blue"
                    folium.PolyLine(
                        path_points_for_png,
                        color=png_path_color,
                        weight=png_path_weight,
                        opacity=png_path_opacity
                    ).add_to(png_map_obj)

                # Kartenausschnitt anpassen (unverändert)
                try:
                    points_array = np.array(all_points_for_png)
                    min_lat, max_lat = points_array[:,
                                       0].min(), points_array[:, 0].max()
                    min_lon, max_lon = points_array[:,
                                       1].min(), points_array[:, 1].max()
                    if min_lat < max_lat or min_lon < max_lon:
                        bounds = [[min_lat, min_lon], [max_lat, max_lon]]
                        png_map_obj.fit_bounds(
                            bounds, max_zoom=max_zoom_level_png)
                    else:
                        png_map_obj.location = [min_lat, min_lon]
                        png_map_obj.zoom_start = min(
                            max(initial_zoom_png, 22), max_zoom_level_png)
                except Exception as fit_err:
                    logger.warning(
                        f"Fehler beim Anpassen des PNG-Kartenausschnitts für {png_file}: {fit_err}. Verwende Standard.")
                    png_map_obj.location = self.map_center
                    png_map_obj.zoom_start = initial_zoom_png
            else:
                logger.warning(
                    f"Keine Daten zum Generieren der PNG-Datei {png_file}.")

            png_map_obj.save(str(temp_html_path))

            # --- Selenium Screenshot mit Chrome (Rest unverändert) ---
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"--window-size={width},{height}")

            driver = None
            service = None
            system_name = platform.system()
            arch = platform.machine()

            try:
                # Plattformspezifische Treiberbehandlung (unverändert)
                driver_path = None
                if system_name == "Linux":
                    system_driver_paths = [
                        '/usr/lib/chromium-browser/chromedriver', '/usr/bin/chromedriver']
                    for path in system_driver_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            driver_path = path
                            logger.info(
                                f"Verwende System-ChromeDriver (Linux): {driver_path}")
                            break
                    if not driver_path:
                        logger.warning(
                            "System-ChromeDriver auf Linux nicht gefunden. Versuche webdriver-manager (falls installiert).")
                        if ChromeDriverManager:
                            try:
                                driver_path = ChromeDriverManager().install()
                                logger.info(
                                    f"Verwende ChromeDriver via webdriver-manager (Linux Fallback): {driver_path}")
                            except Exception as wdm_err:
                                logger.error(
                                    f"Fehler bei webdriver-manager auf Linux: {wdm_err}")
                                raise FileNotFoundError(
                                    "ChromeDriver nicht gefunden und webdriver-manager fehlgeschlagen.")
                        else:
                            raise FileNotFoundError(
                                "ChromeDriver auf Linux nicht gefunden und webdriver-manager nicht installiert.")
                elif system_name == "Windows":
                    if ChromeDriverManager:
                        try:
                            driver_path = ChromeDriverManager().install()
                            logger.info(
                                f"Verwende ChromeDriver via webdriver-manager (Windows): {driver_path}")
                        except Exception as wdm_err:
                            logger.error(
                                f"Fehler bei webdriver-manager auf Windows: {wdm_err}")
                            raise FileNotFoundError(
                                "ChromeDriver konnte via webdriver-manager nicht installiert werden.")
                    else:
                        driver_in_path = shutil.which("chromedriver.exe")
                        if driver_in_path:
                            driver_path = driver_in_path
                            logger.info(
                                f"Verwende ChromeDriver aus PATH (Windows): {driver_path}")
                        else:
                            raise FileNotFoundError(
                                "webdriver-manager nicht installiert und chromedriver.exe nicht im PATH gefunden.")
                else:  # Andere Systeme
                    if ChromeDriverManager:
                        try:
                            driver_path = ChromeDriverManager().install()
                            logger.info(
                                f"Verwende ChromeDriver via webdriver-manager ({system_name}): {driver_path}")
                        except Exception as wdm_err:
                            logger.error(
                                f"Fehler bei webdriver-manager auf {system_name}: {wdm_err}")
                            raise FileNotFoundError(
                                f"ChromeDriver konnte via webdriver-manager für {system_name} nicht installiert werden.")
                    else:
                        driver_in_path = shutil.which("chromedriver")
                        if driver_in_path:
                            driver_path = driver_in_path
                            logger.info(
                                f"Verwende ChromeDriver aus PATH ({system_name}): {driver_path}")
                        else:
                            raise FileNotFoundError(
                                f"webdriver-manager nicht installiert und chromedriver nicht im PATH für {system_name} gefunden.")

                if driver_path:
                    service = ChromeService(executable_path=driver_path)
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    raise webdriver.support.wait.WebDriverException(
                        "ChromeDriver Pfad konnte nicht ermittelt werden.")

                local_url = temp_html_path.resolve().as_uri()
                driver.get(local_url)
                logger.debug(
                    f"Warte {delay} Sekunden, bis die Karte '{temp_html_path}' für PNG geladen ist...")
                time.sleep(delay)
                driver.save_screenshot(str(temp_png_path))
                logger.info(f"Screenshot erfolgreich erstellt: {temp_png_path}")

            except (FileNotFoundError, webdriver.support.wait.WebDriverException, Exception) as e:
                logger.error(
                    f"Fehler beim Erstellen des PNG-Screenshots für {png_file}: {e}", exc_info=True)
                if temp_html_path.exists():
                    temp_html_path.unlink()
                return
            finally:
                if driver:
                    driver.quit()

            # --- PNG Cropping (unverändert) ---
            if self.crop_enabled and Image is not None:
                logger.info(f"Cropping für {final_png_path} wird durchgeführt.")
                try:
                    img = Image.open(str(temp_png_path))
                    img_width, img_height = img.size
                    crop_box = None
                    if self.use_center_crop:
                        percentage = self.crop_center_percentage / 100.0
                        min_dimension = min(img_width, img_height)
                        crop_side = int(min_dimension * percentage)
                        if crop_side > 0:
                            left = int((img_width - crop_side) / 2)
                            top = int((img_height - crop_side) / 2)
                            right = left + crop_side
                            bottom = top + crop_side
                            crop_box = (left, top, right, bottom)
                            logger.debug(
                                f"Berechnete Crop-Box (Center %): {crop_box}")
                        else:
                            logger.warning(
                                "Berechnete Crop-Seitenlänge <= 0. Kein Zuschnitt.")
                    else:  # Pixel-Offset
                        left_px = self.crop_pixel_left
                        top_px = self.crop_pixel_top
                        right_px = img_width - self.crop_pixel_right
                        bottom_px = img_height - self.crop_pixel_bottom
                        if left_px < right_px and top_px < bottom_px:
                            crop_box = (left_px, top_px, right_px, bottom_px)
                            logger.debug(
                                f"Berechnete Crop-Box (Pixel Offset): {crop_box}")
                        else:
                            logger.error(
                                f"Ungültige Pixel-Offset-Werte ergeben ungültige Box: L={left_px}, T={top_px}, R={right_px}, B={bottom_px}")

                    if crop_box and crop_box[0] < crop_box[2] and crop_box[1] < crop_box[3]:
                        cropped_img = img.crop(crop_box)
                        cropped_img.save(str(final_png_path))
                        logger.info(
                            f"Bild erfolgreich auf {final_png_path} zugeschnitten.")
                        if temp_png_path != final_png_path and temp_png_path.exists():
                            try:
                                temp_png_path.unlink()
                            except OSError as rm_err:
                                logger.warning(
                                    f"Konnte temporäre PNG {temp_png_path} nicht löschen: {rm_err}")
                    else:
                        logger.error(
                            f"Ungültige/keine Crop-Box berechnet: {crop_box}. Originalbild wird verwendet.")
                        if temp_png_path != final_png_path and temp_png_path.exists():
                            try:
                                if final_png_path.exists():
                                    final_png_path.unlink()
                                temp_png_path.rename(final_png_path)
                                logger.info(
                                    f"Temporäres PNG zu {final_png_path} umbenannt (kein Crop).")
                            except OSError as ren_err:
                                logger.error(
                                    f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")
                        elif temp_png_path == final_png_path:
                            logger.info(
                                f"Kein Cropping, {final_png_path} wurde direkt erstellt.")
                except Exception as crop_err:
                    logger.error(
                        f"Fehler beim Zuschneiden von {temp_png_path}: {crop_err}", exc_info=True)
                    if temp_png_path != final_png_path and temp_png_path.exists():
                        try:
                            if final_png_path.exists():
                                final_png_path.unlink()
                            temp_png_path.rename(final_png_path)
                            logger.info(
                                f"Temporäres PNG zu {final_png_path} umbenannt (Crop fehlgeschlagen).")
                        except OSError as ren_err:
                            logger.error(
                                f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")
            elif temp_png_path != final_png_path and temp_png_path.exists():
                try:
                    if final_png_path.exists():
                        final_png_path.unlink()
                    temp_png_path.rename(final_png_path)
                    logger.info(
                        f"Temporäres PNG zu {final_png_path} umbenannt (Cropping deaktiviert).")
                except OSError as ren_err:
                    logger.error(
                        f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")

        finally:
            try:
                if temp_html_path.exists():
                    temp_html_path.unlink()
                    logger.debug(
                        f"Temporäre HTML-Datei {temp_html_path} gelöscht.")
            except OSError as e:
                logger.error(
                    f"Fehler beim Löschen der temporären HTML-Datei {temp_html_path}: {e}")


# Beispiel für die Verwendung (kann entfernt oder in __main__ verschoben werden)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
    # --- Beispielhafte Konfiguration in config.py ANPASSEN ---
    # Füge die neuen Optionen zu deiner HEATMAP_CONFIG in config.py hinzu:
    """
    HEATMAP_CONFIG = {
        "last_10": {
            ...,
            "use_heatmap_with_time": True, # Beispiel: Aktivieren für diese Karte
        },
        "heatmap_aktuell": {
             ...,
            "use_heatmap_with_time": True, # Beispiel: Aktivieren für diese Karte
        }
        # ...
    }
    """
    # Stelle sicher, dass GEO_CONFIG Keys existieren
    GEO_CONFIG["map_center"] = (46.8118, 7.1328)
    GEO_CONFIG["zoom_start"] = 22
    GEO_CONFIG["max_zoom"] = 22
    GEO_CONFIG["crop_enabled"] = False

    # Beispiel-Datenpunkte MIT Zeitstempel
    import time

    ts_now = time.time()
    single_data_ts = [
        {'lat': 46.8117, 'lon': 7.1327, 'value': 1, 'timestamp': ts_now - 3},
        {'lat': 46.8118, 'lon': 7.1328, 'value': 1, 'timestamp': ts_now - 2},
        {'lat': 46.8119, 'lon': 7.1329, 'value': 1, 'timestamp': ts_now - 1},
        {'lat': 46.81185, 'lon': 7.13285, 'value': 1, 'timestamp': ts_now},
    ]
    multi_data_ts = [
        [{'lat': 46.8117, 'lon': 7.1327, 'timestamp': ts_now - 13},
         {'lat': 46.81175, 'lon': 7.13275, 'timestamp': ts_now - 12},
         {'lat': 46.81172, 'lon': 7.1328, 'timestamp': ts_now - 11}],  # Session 1
        [{'lat': 46.8119, 'lon': 7.1329, 'timestamp': ts_now - 3},
         {'lat': 46.81195, 'lon': 7.13295, 'timestamp': ts_now - 2},
         {'lat': 46.81192, 'lon': 7.13285, 'timestamp': ts_now - 1}],  # Session 2
    ]

    # Beispielhafte HEATMAP_CONFIG für Tests hier definieren
    HEATMAP_CONFIG["test_single_ts"] = {
        "output": "heatmaps/test_single_ts.html",
        "png_output": "heatmaps/test_single_ts.png",
        "radius": 5, "blur": 5,
        "path_weight": 2.0, "path_opacity": 1.0, "show_start_end_markers": True,
        "path_colors": ["#FF5733"],
        "use_heatmap_with_time": True  # Teste HeatMapWithTime
    }
    HEATMAP_CONFIG["test_multi_ts"] = {
        "output": "heatmaps/test_multi_ts.html",
        "png_output": "heatmaps/test_multi_ts.png",
        "radius": 3, "blur": 3,
        "path_weight": 1.5, "path_opacity": 0.7, "show_start_end_markers": True,
        "use_heatmap_with_time": True  # Teste HeatMapWithTime
    }

    gen = HeatmapGenerator()

    logger.info("Teste einzelne Heatmap mit Zeitstempel (HTML)...")
    gen.create_heatmap(single_data_ts, "heatmaps/test_single_ts.html",
                       draw_path=True, is_multi_session=False)
    # PNG Test bleibt gleich (rendert keine Zeit-Features)
    # if SELENIUM_AVAILABLE:
    #    logger.info("Teste einzelne Heatmap mit Zeitstempel (PNG)...")
    #    gen.save_html_as_png(single_data_ts, draw_path=True, png_file="heatmaps/test_single_ts.png",
    #                         config_key_hint="test_single_ts")

    logger.info("Teste Multi-Session Heatmap mit Zeitstempel (HTML)...")
    gen.create_heatmap(multi_data_ts, "heatmaps/test_multi_ts.html",
                       draw_path=True, is_multi_session=True)
    # PNG Test bleibt gleich
    # if SELENIUM_AVAILABLE:
    #    logger.info("Teste Multi-Session Heatmap mit Zeitstempel (PNG)...")
    #    gen.save_html_as_png(multi_data_ts, draw_path=True, png_file="heatmaps/test_multi_ts.png",
    #                         config_key_hint="test_multi_ts", is_multi_session_data=True)

    logger.info("Heatmap-Generierungstests abgeschlossen.")
