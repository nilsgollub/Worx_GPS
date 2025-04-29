# heatmap_generator.py
import folium
import folium.plugins as plugins
import numpy as np
import logging
from pathlib import Path
from config import GEO_CONFIG, HEATMAP_CONFIG
import io
import platform
import os
import shutil
from datetime import datetime
from utils import flatten_data
import branca.colormap as cm  # NEU: Import für Colormap

# Selenium Imports (unverändert)
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
        logging.info("webdriver-manager nicht gefunden...")
except ImportError:
    SELENIUM_AVAILABLE = False
    Image = None
    logging.warning("Selenium, Pillow oder webdriver-manager nicht installiert...")

logger = logging.getLogger(__name__)

DEFAULT_PATH_COLORS = ['blue', 'green', 'red', 'purple', 'orange', 'darkred',
                       'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                       'lightgreen', 'gray', 'black', 'lightgray']


class HeatmapGenerator:
    # __init__ (unverändert)
    def __init__(self, heatmaps_base_dir="heatmaps"):
        self.map_center = GEO_CONFIG.get("map_center", (46.811819, 7.132838))
        self.heatmaps_dir = Path(heatmaps_base_dir)
        self.heatmaps_dir.mkdir(parents=True, exist_ok=True)
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
                    logger.info(f"PNG Cropping (Center Percentage) aktiviert: {self.crop_center_percentage}%")
                else:
                    logger.info("PNG Cropping (Center Percentage) ist 100%, kein Zuschnitt.");
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
                        "PNG Cropping aktiviert, aber weder 'crop_center_percentage' noch 'crop_pixel_*' gültig. Deaktiviert.");
                    self.crop_enabled = False
        logger.info(f"HeatmapGenerator initialisiert. Karten in '{self.heatmaps_dir}'.")
        if not SELENIUM_AVAILABLE:
            logger.warning("PNG-Generierung deaktiviert (Bibliotheken fehlen).")
        elif self.crop_enabled and Image is None:
            logger.warning("PNG Cropping aktiviert, aber Pillow fehlt. Deaktiviert.");
            self.crop_enabled = False

    # _format_timestamp (unverändert)
    def _format_timestamp(self, timestamp):
        if timestamp is None: return "N/A"
        try:
            dt_object = datetime.fromtimestamp(float(timestamp))
            return dt_object.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            try:
                ts_str = str(timestamp).split('+')[0].split('Z')[0]
                if '.' in ts_str:
                    dt_object = datetime.fromisoformat(ts_str.split('.')[0])
                else:
                    dt_object = datetime.fromisoformat(ts_str)
                return dt_object.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                logger.warning(f"Konnte Zeitstempel nicht formatieren: {timestamp}")
                return str(timestamp)

    # --- create_heatmap angepasst ---
    def create_heatmap(self, data, html_file, draw_path, is_multi_session=False):
        """Erstellt eine interaktive Karte (Heatmap oder farbkodierter Pfad)."""
        initial_zoom = GEO_CONFIG.get("zoom_start", 22)
        max_zoom_level = GEO_CONFIG.get("max_zoom", 22)
        google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        google_attr = 'Google Satellite'

        map_obj = folium.Map(location=self.map_center, zoom_start=initial_zoom, tiles=google_tiles_url,
                             attr=google_attr, control_scale=True, max_zoom=max_zoom_level)
        osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        folium.TileLayer(tiles="OpenStreetMap", attr=osm_attr, name='OpenStreetMap', overlay=False,
                         control=True).add_to(map_obj)

        all_points_for_bounds = []
        config_key = self._find_config_key_by_output(html_file)
        map_config = HEATMAP_CONFIG.get(config_key, {})

        # Allgemeine Parameter
        path_weight = map_config.get("path_weight", 1.0)
        path_opacity = map_config.get("path_opacity", 0.8)
        show_markers = map_config.get("show_start_end_markers", True)
        path_colors_list = map_config.get("path_colors", DEFAULT_PATH_COLORS)

        # Spezifische Flags
        visualize_quality_path = map_config.get("visualize_quality_path", False)
        use_satellite_weight_heatmap = map_config.get("use_satellite_weight", False)
        use_time_heatmap = map_config.get("use_heatmap_with_time", False)

        # Daten vorbereiten (flach für Bounds, original für Iteration)
        # Wichtig: 'data' für Multi-Session-Iteration verwenden, 'flat_data_list' nur für Bounds/Single-Path
        flat_data_list = flatten_data(data)
        sessions_to_draw = data if is_multi_session and isinstance(data, list) and data and isinstance(data[0],
                                                                                                       list) else [
            data]  # Stellt sicher, dass es immer eine Liste von Sessions ist

        if not flat_data_list:  # Prüfe, ob überhaupt Daten da sind
            logger.warning(f"Keine Datenpunkte für Karte {html_file} vorhanden.")
            plugins.MeasureControl(position='topleft', primary_length_unit='meters').add_to(map_obj)
            folium.LayerControl(collapsed=True).add_to(map_obj)
            map_obj.save(str(self.heatmaps_dir / Path(html_file).name))
            return

        # --- Logik für Kartentyp ---
        if visualize_quality_path:
            # --- Farbkodierten Pfad zeichnen (jetzt mit Multi-Session Support) ---
            logger.info(f"Zeichne farbkodierten Qualitätspfad für {html_file}.")

            # Colormap-Setup (nur einmal benötigt)
            colors = map_config.get('quality_colormap_colors', ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'])
            index = map_config.get('quality_colormap_index', [4, 6, 8, 10])
            caption = map_config.get('quality_legend_caption', 'GPS Qualität (Satelliten)')
            default_color = 'grey'

            sat_values = [p.get('satellites') for p in flat_data_list if p.get('satellites') is not None]
            min_sats_data = min(sat_values) if sat_values else min(index) if index else 0
            max_sats_data = max(sat_values) if sat_values else max(index) if index else 12
            full_index = sorted(list(set([min_sats_data] + index + [max_sats_data + 1])))
            colormap = cm.StepColormap(colors, index=full_index, vmin=min_sats_data, vmax=max_sats_data,
                                       caption=caption)

            path_groups = []  # Liste für die FeatureGroups der Sessions

            # Iteriere durch die Sessions (auch wenn es nur eine ist)
            for idx, session_data in enumerate(reversed(sessions_to_draw)):
                if not session_data: continue  # Leere Session überspringen

                session_index_display = len(sessions_to_draw) - idx  # Für Anzeige (1-basiert, neueste zuerst)
                path_layer_name = f"Qualität Pfad -{session_index_display}"
                show_layer = (idx == 0)  # Nur die neueste Session standardmäßig anzeigen
                path_feature_group = folium.FeatureGroup(name=path_layer_name, show=show_layer)

                session_points_coords = []  # Für Marker

                # Zeichne die Segmente für diese Session
                for i in range(len(session_data) - 1):
                    p1 = session_data[i]
                    p2 = session_data[i + 1]
                    try:
                        lat1, lon1 = float(p1['lat']), float(p1['lon'])
                        lat2, lon2 = float(p2['lat']), float(p2['lon'])
                        sats = p1.get('satellites')

                        # Koordinaten für Marker sammeln
                        if i == 0: session_points_coords.append([lat1, lon1])
                        session_points_coords.append([lat2, lon2])

                        if sats is not None:
                            try:
                                segment_color = colormap(int(sats))
                            except ValueError:
                                if int(sats) < colormap.vmin:
                                    segment_color = colormap(colormap.vmin)
                                elif int(sats) > colormap.vmax:
                                    segment_color = colormap(colormap.vmax)
                                else:
                                    segment_color = default_color
                        else:
                            segment_color = default_color

                        locations = [(lat1, lon1), (lat2, lon2)]
                        folium.PolyLine(locations=locations, color=segment_color, weight=path_weight,
                                        opacity=path_opacity).add_to(path_feature_group)  # Zum Gruppenlayer hinzufügen

                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning(f"Überspringe Pfadsegment in Session {session_index_display} wegen Fehler: {e}")
                        continue

                # Start-/Endmarker für die Session hinzufügen (falls gewünscht und Punkte vorhanden)
                if show_markers and len(session_points_coords) > 1:
                    start_point_data = session_data[0]
                    end_point_data = session_data[-1]
                    start_ts = start_point_data.get('timestamp')
                    end_ts = end_point_data.get('timestamp')
                    start_popup = f"Start Session {session_index_display}<br>Zeit: {self._format_timestamp(start_ts)}"
                    end_popup = f"Ende Session {session_index_display}<br>Zeit: {self._format_timestamp(end_ts)}"
                    # Verwende eine neutrale Farbe für Marker, da der Pfad schon bunt ist
                    marker_color = 'darkblue'
                    folium.CircleMarker(location=session_points_coords[0], radius=3, color=marker_color,
                                        fill=True, fill_color=marker_color, fill_opacity=0.9,
                                        popup=start_popup).add_to(path_feature_group)
                    folium.CircleMarker(location=session_points_coords[-1], radius=3, color=marker_color,
                                        fill=True, fill_color=marker_color, fill_opacity=0.9,
                                        popup=end_popup).add_to(path_feature_group)

                path_groups.append(path_feature_group)  # Füge die fertige Gruppe zur Liste hinzu

            # Füge alle Session-Gruppen zur Karte hinzu
            for pg in path_groups:
                pg.add_to(map_obj)

            # Füge die Colormap-Legende hinzu (nur einmal)
            colormap.add_to(map_obj)

            # Punkte für Bounds (aus allen flachen Daten)
            all_points_for_bounds = [[float(p['lat']), float(p['lon'])] for p in flat_data_list if
                                     'lat' in p and 'lon' in p]

        else:
            # --- Bisherige Logik für Heatmap und normale Pfade ---
            # (Dieser Teil bleibt weitgehend unverändert, nur die Datenquelle für Bounds wird ggf. angepasst)
            logger.info(f"Erstelle Standard-Karte (Heatmap/Pfad) für {html_file}.")
            heat_data = []
            if use_satellite_weight_heatmap:
                logger.warning(f"'use_satellite_weight' für Heatmap aktiv, aber ignoriert.")
                heat_data = [[float(p['lat']), float(p['lon'])] for p in flat_data_list if 'lat' in p and 'lon' in p]
            else:
                heat_data = [[float(p['lat']), float(p['lon'])] for p in flat_data_list if 'lat' in p and 'lon' in p]

            if heat_data:
                heatmap_radius = map_config.get("radius", 3)
                heatmap_blur = map_config.get("blur", 3)
                if use_time_heatmap:
                    logger.warning(
                        f"'use_heatmap_with_time' aktiv, aber nicht implementiert. Zeige normale Heatmap.")
                    plugins.HeatMap(heat_data, radius=heatmap_radius, blur=heatmap_blur, name="Heatmap").add_to(
                        map_obj)
                else:
                    plugins.HeatMap(heat_data, radius=heatmap_radius, blur=heatmap_blur, name="Heatmap").add_to(
                        map_obj)
                all_points_for_bounds = heat_data
            else:
                logger.warning(f"Keine gültigen Heatmap-Daten für {html_file} gefunden.")
                all_points_for_bounds = [[float(p['lat']), float(p['lon'])] for p in flat_data_list if
                                         'lat' in p and 'lon' in p]

            if draw_path:
                if is_multi_session:  # Hier 'is_multi_session' verwenden, da 'sessions_to_draw' oben definiert wurde
                    logger.info(f"Zeichne Pfade für Multi-Session Karte {html_file}.")
                    path_groups = []
                    for idx, session_data in enumerate(
                            reversed(sessions_to_draw)):  # sessions_to_draw verwenden
                        if not session_data: continue
                        session_index_display = len(sessions_to_draw) - idx
                        path_layer_name = f"Pfad -{session_index_display}"
                        show_layer = (idx == 0)
                        path_points_coords = []
                        session_points_full = []
                        for point in session_data:
                            try:
                                path_points_coords.append([float(point['lat']), float(point['lon'])])
                                session_points_full.append(point)
                            except (ValueError, KeyError, TypeError):
                                continue

                        if len(path_points_coords) > 1:
                            path_feature_group = folium.FeatureGroup(name=path_layer_name, show=show_layer)
                            current_path_color = path_colors_list[idx % len(path_colors_list)]
                            folium.PolyLine(path_points_coords, color=current_path_color, weight=path_weight,
                                            opacity=path_opacity).add_to(path_feature_group)
                            if show_markers:
                                start_ts = session_points_full[0].get('timestamp')
                                end_ts = session_points_full[-1].get('timestamp')
                                start_popup = f"Start Session {session_index_display}<br>Zeit: {self._format_timestamp(start_ts)}"
                                end_popup = f"Ende Session {session_index_display}<br>Zeit: {self._format_timestamp(end_ts)}"
                                folium.CircleMarker(location=path_points_coords[0], radius=3,
                                                    color=current_path_color, fill=True, fill_color=current_path_color,
                                                    fill_opacity=0.9, popup=start_popup).add_to(path_feature_group)
                                folium.CircleMarker(location=path_points_coords[-1], radius=3,
                                                    color=current_path_color, fill=True, fill_color=current_path_color,
                                                    fill_opacity=0.9, popup=end_popup).add_to(path_feature_group)
                            path_groups.append(path_feature_group)
                    for pg in path_groups: pg.add_to(map_obj)
                else:  # Single Session
                    logger.info(f"Zeichne Pfad für Single-Session Karte {html_file}.")
                    single_path_points_coords = []
                    single_session_points_full = []
                    # Hier sessions_to_draw[0] verwenden, da es nur eine Session gibt
                    for point in sessions_to_draw[0]:
                        try:
                            single_path_points_coords.append([float(point['lat']), float(point['lon'])])
                            single_session_points_full.append(point)
                        except (ValueError, KeyError, TypeError):
                            continue

                    if len(single_path_points_coords) > 1:
                        path_group = folium.FeatureGroup(name="Pfad", show=True)
                        current_path_color = path_colors_list[0] if path_colors_list else "blue"
                        folium.PolyLine(single_path_points_coords, color=current_path_color, weight=path_weight,
                                        opacity=path_opacity).add_to(path_group)
                        if show_markers:
                            start_ts_single = single_session_points_full[0].get('timestamp')
                            end_ts_single = single_session_points_full[-1].get('timestamp')
                            start_popup_single = f"Start<br>Zeit: {self._format_timestamp(start_ts_single)}"
                            end_popup_single = f"Ende<br>Zeit: {self._format_timestamp(end_ts_single)}"
                            folium.CircleMarker(location=single_path_points_coords[0], radius=3,
                                                color=current_path_color, fill=True, fill_color=current_path_color,
                                                fill_opacity=0.9, popup=start_popup_single).add_to(path_group)
                            folium.CircleMarker(location=single_path_points_coords[-1], radius=3,
                                                color=current_path_color, fill=True, fill_color=current_path_color,
                                                fill_opacity=0.9, popup=end_popup_single).add_to(path_group)
                        path_group.add_to(map_obj)

            # Falls keine Bounds aus Heatmap, nimm sie aus Pfadpunkten (jetzt aus flat_data_list)
            if not all_points_for_bounds:
                all_points_for_bounds = [[float(p['lat']), float(p['lon'])] for p in flat_data_list if
                                         'lat' in p and 'lon' in p]

        # --- Gemeinsame Elemente für alle Kartentypen ---
        # Kartengrenzen anpassen (fit_bounds) - (unverändert)
        if all_points_for_bounds:
            try:
                points_array = np.array(all_points_for_bounds)
                if points_array.size > 0 and points_array.ndim == 2 and points_array.shape[1] == 2:
                    min_lat, max_lat = points_array[:, 0].min(), points_array[:, 0].max()
                    min_lon, max_lon = points_array[:, 1].min(), points_array[:, 1].max()
                    if min_lat < max_lat or min_lon < max_lon:
                        lat_margin = (max_lat - min_lat) * 0.05
                        lon_margin = (max_lon - min_lon) * 0.05
                        epsilon = 1e-9
                        if lat_margin < epsilon: lat_margin = 0.0001
                        if lon_margin < epsilon: lon_margin = 0.0001
                        bounds = [[min_lat - lat_margin, min_lon - lon_margin],
                                  [max_lat + lat_margin, max_lon + lon_margin]]
                        map_obj.fit_bounds(bounds, max_zoom=max_zoom_level)
                        logger.debug(f"Kartenausschnitt für {html_file} angepasst an Grenzen: {bounds}")
                    else:
                        map_obj.location = [min_lat, min_lon]
                        map_obj.zoom_start = min(max(initial_zoom, 18), max_zoom_level)
                        logger.debug(
                            f"Nur ein Punkt in {html_file}, zentriere Karte auf {map_obj.location} mit Zoom {map_obj.zoom_start}")
                else:
                    logger.warning(f"Ungültige Datenstruktur für Bounds-Anpassung in {html_file}. Verwende Standard.")
                    map_obj.location = self.map_center
                    map_obj.zoom_start = initial_zoom
            except Exception as fit_err:
                logger.error(f"Fehler bei fit_bounds für {html_file}: {fit_err}", exc_info=True)
                map_obj.location = self.map_center
                map_obj.zoom_start = initial_zoom
        else:
            logger.warning(f"Keine Punkte für Bounds-Anpassung in {html_file}. Verwende Standard.")
            map_obj.location = self.map_center
            map_obj.zoom_start = initial_zoom

        # Messwerkzeug hinzufügen (unverändert)
        plugins.MeasureControl(position='topleft', primary_length_unit='meters', secondary_length_unit='kilometers',
                               primary_area_unit='sqmeters', secondary_area_unit='hectares').add_to(map_obj)

        # LayerControl hinzufügen (unverändert)
        folium.LayerControl(collapsed=True).add_to(map_obj)

        # Speichern der HTML-Datei (unverändert)
        try:
            html_path = self.heatmaps_dir / Path(html_file).name
            map_obj.save(str(html_path))
            logger.info(f"Interaktive Karte erstellt: {html_path}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Karte {html_path}: {e}", exc_info=True)

    # _find_config_key_by_output (unverändert)
    def _find_config_key_by_output(self, output_filename):
        output_path = Path(output_filename).name
        for key, config_val in HEATMAP_CONFIG.items():
            if isinstance(config_val, dict):
                if Path(config_val.get("output", "")).name == output_path or Path(
                        config_val.get("png_output", "")).name == output_path:
                    return key
        logger.warning(f"Kein Konfigurationsschlüssel für Ausgabedatei '{output_filename}' gefunden.")
        return None

    # --- save_html_as_png angepasst ---
    # Muss ebenfalls Multi-Session für Qualitätspfade behandeln, wenn PNGs dafür aktiviert werden
    def save_html_as_png(self, data, draw_path, png_file, config_key_hint=None, is_multi_session_data=False, width=1024,
                         height=768, delay=5):
        if not SELENIUM_AVAILABLE: logger.error("PNG-Export nicht möglich. Selenium/Pillow fehlt."); return

        temp_html_path = self.heatmaps_dir / f"temp_{Path(png_file).stem}.html"
        output_path_png = self.heatmaps_dir / Path(png_file).name
        temp_png_path = output_path_png.with_suffix(
            output_path_png.suffix + ".tmp") if self.crop_enabled else output_path_png
        final_png_path = output_path_png

        try:
            initial_zoom_png = GEO_CONFIG.get("zoom_start", 22)
            max_zoom_level_png = GEO_CONFIG.get("max_zoom", 22)
            google_tiles_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
            google_attr = 'Google Satellite'

            png_map_obj = folium.Map(location=self.map_center, zoom_start=initial_zoom_png, tiles=google_tiles_url,
                                     attr=google_attr, control_scale=False, zoom_control=False,
                                     max_zoom=max_zoom_level_png)

            flat_data_list_png = flatten_data(data)
            sessions_to_draw_png = data if is_multi_session_data and isinstance(data, list) and data and isinstance(
                data[0], list) else [data]
            all_points_for_bounds_png = []

            config_key = config_key_hint or self._find_config_key_by_output(png_file)
            map_config = HEATMAP_CONFIG.get(config_key, {})
            visualize_quality_path_png = map_config.get("visualize_quality_path", False)

            if not flat_data_list_png:
                logger.warning(f"Keine Daten zum Generieren der PNG-Datei {png_file}.")
                png_map_obj.save(str(temp_html_path))
            elif visualize_quality_path_png:
                # --- Farbkodierten Pfad für PNG zeichnen (Multi-Session) ---
                logger.debug(f"Zeichne farbkodierten Qualitätspfad für PNG {png_file}.")
                colors = map_config.get('quality_colormap_colors',
                                        ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'])
                index = map_config.get('quality_colormap_index', [4, 6, 8, 10])
                default_color = 'grey'
                path_weight_png = map_config.get("path_weight", 1.0)
                path_opacity_png = map_config.get("path_opacity", 0.8)

                sat_values = [p.get('satellites') for p in flat_data_list_png if p.get('satellites') is not None]
                min_sats_data = min(sat_values) if sat_values else min(index) if index else 0
                max_sats_data = max(sat_values) if sat_values else max(index) if index else 12
                full_index = sorted(list(set([min_sats_data] + index + [max_sats_data + 1])))
                colormap_png = cm.StepColormap(colors, index=full_index, vmin=min_sats_data, vmax=max_sats_data)

                # Iteriere durch Sessions für PNG
                # HINWEIS: LayerControl wird im PNG nicht funktionieren, daher zeichnen wir alle Pfade direkt
                for session_data in sessions_to_draw_png:
                    if not session_data: continue
                    for i in range(len(session_data) - 1):
                        p1 = session_data[i]
                        p2 = session_data[i + 1]
                        try:
                            lat1, lon1 = float(p1['lat']), float(p1['lon'])
                            lat2, lon2 = float(p2['lat']), float(p2['lon'])
                            sats = p1.get('satellites')
                            if sats is not None:
                                try:
                                    segment_color = colormap_png(int(sats))
                                except ValueError:
                                    if int(sats) < colormap_png.vmin:
                                        segment_color = colormap_png(colormap_png.vmin)
                                    elif int(sats) > colormap_png.vmax:
                                        segment_color = colormap_png(colormap_png.vmax)
                                    else:
                                        segment_color = default_color
                            else:
                                segment_color = default_color
                            locations = [(lat1, lon1), (lat2, lon2)]
                            folium.PolyLine(locations=locations, color=segment_color, weight=path_weight_png,
                                            opacity=path_opacity_png).add_to(png_map_obj)
                        except (ValueError, KeyError, TypeError):
                            continue

                all_points_for_bounds_png = [[float(p['lat']), float(p['lon'])] for p in flat_data_list_png if
                                             'lat' in p and 'lon' in p]
                # --- ENDE Farbkodierter Pfad PNG ---
            else:
                # --- Heatmap / Normaler Pfad für PNG (unverändert) ---
                heat_data_for_png = []
                path_points_for_png = []
                use_satellite_weight_png = map_config.get("use_satellite_weight", False)

                if use_satellite_weight_png:
                    logger.warning(f"'use_satellite_weight' für Heatmap PNG aktiv, aber ignoriert.")
                    heat_data_for_png = [[float(p['lat']), float(p['lon'])] for p in flat_data_list_png if
                                         'lat' in p and 'lon' in p]
                else:
                    heat_data_for_png = [[float(p['lat']), float(p['lon'])] for p in flat_data_list_png if
                                         'lat' in p and 'lon' in p]

                if heat_data_for_png:
                    radius = map_config.get("radius", 3)
                    blur = map_config.get("blur", 3)
                    plugins.HeatMap(heat_data_for_png, radius=radius, blur=blur).add_to(png_map_obj)
                    all_points_for_bounds_png = heat_data_for_png

                if draw_path and len(flat_data_list_png) > 1:
                    path_points_for_png = [[float(p['lat']), float(p['lon'])] for p in flat_data_list_png if
                                           'lat' in p and 'lon' in p]
                    if path_points_for_png:
                        png_path_weight = map_config.get("path_weight", 1.0)
                        png_path_opacity = map_config.get("path_opacity", 0.8)
                        png_path_colors_list = map_config.get("path_colors", DEFAULT_PATH_COLORS)
                        png_path_color = png_path_colors_list[0] if png_path_colors_list else "blue"
                        # Für PNG zeichnen wir bei Multi-Session vereinfacht nur einen Pfad
                        folium.PolyLine(path_points_for_png, color=png_path_color, weight=png_path_weight,
                                        opacity=png_path_opacity).add_to(png_map_obj)
                        if not all_points_for_bounds_png:
                            all_points_for_bounds_png = path_points_for_png

            # Kartenausschnitt für PNG anpassen (unverändert)
            if all_points_for_bounds_png:
                try:
                    points_array_png = np.array(all_points_for_bounds_png)
                    if points_array_png.size > 0 and points_array_png.ndim == 2 and points_array_png.shape[1] == 2:
                        min_lat, max_lat = points_array_png[:, 0].min(), points_array_png[:, 0].max()
                        min_lon, max_lon = points_array_png[:, 1].min(), points_array_png[:, 1].max()
                        if min_lat < max_lat or min_lon < max_lon:
                            bounds = [[min_lat, min_lon], [max_lat, max_lon]]
                            png_map_obj.fit_bounds(bounds, max_zoom=max_zoom_level_png)
                        else:
                            png_map_obj.location = [min_lat, min_lon];
                            png_map_obj.zoom_start = min(max(initial_zoom_png, 18), max_zoom_level_png)
                    else:
                        logger.warning(f"Ungültige Datenstruktur für PNG Bounds-Anpassung {png_file}.")
                        png_map_obj.location = self.map_center;
                        png_map_obj.zoom_start = initial_zoom_png
                except Exception as fit_err:
                    logger.warning(
                        f"Fehler beim Anpassen des PNG-Kartenausschnitts für {png_file}: {fit_err}. Verwende Standard.")
                    png_map_obj.location = self.map_center;
                    png_map_obj.zoom_start = initial_zoom_png
            else:
                logger.warning(f"Keine Punkte für PNG Bounds-Anpassung {png_file}.")
                png_map_obj.location = self.map_center;
                png_map_obj.zoom_start = initial_zoom_png

            png_map_obj.save(str(temp_html_path))

            # --- Selenium Screenshot mit Chrome (Rest unverändert) ---
            options = ChromeOptions();
            options.add_argument("--headless");
            options.add_argument("--disable-gpu");
            options.add_argument("--no-sandbox");
            options.add_argument("--disable-dev-shm-usage");
            options.add_argument(f"--window-size={width},{height}")
            driver = None;
            service = None;
            system_name = platform.system();
            arch = platform.machine()
            try:
                driver_path = None
                # ... (ChromeDriver Pfadfindung bleibt gleich) ...
                if system_name == "Linux":
                    system_driver_paths = ['/usr/lib/chromium-browser/chromedriver', '/usr/bin/chromedriver']
                    for path in system_driver_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK): driver_path = path; logger.info(
                            f"Verwende System-ChromeDriver (Linux): {driver_path}"); break
                    if not driver_path:
                        logger.warning("System-ChromeDriver auf Linux nicht gefunden. Versuche webdriver-manager...")
                        if ChromeDriverManager:
                            try:
                                driver_path = ChromeDriverManager().install();
                                logger.info(
                                    f"Verwende ChromeDriver via webdriver-manager (Linux Fallback): {driver_path}")
                            except Exception as wdm_err:
                                logger.error(
                                    f"Fehler bei webdriver-manager auf Linux: {wdm_err}");
                                raise FileNotFoundError(
                                    "ChromeDriver nicht gefunden und webdriver-manager fehlgeschlagen.")
                        else:
                            raise FileNotFoundError(
                                "ChromeDriver auf Linux nicht gefunden und webdriver-manager nicht installiert.")
                elif system_name == "Windows":
                    if ChromeDriverManager:
                        try:
                            driver_path = ChromeDriverManager().install();
                            logger.info(
                                f"Verwende ChromeDriver via webdriver-manager (Windows): {driver_path}")
                        except Exception as wdm_err:
                            logger.error(
                                f"Fehler bei webdriver-manager auf Windows: {wdm_err}");
                            raise FileNotFoundError(
                                "ChromeDriver konnte via webdriver-manager nicht installiert werden.")
                    else:
                        driver_in_path = shutil.which("chromedriver.exe")
                        if driver_in_path:
                            driver_path = driver_in_path;
                            logger.info(
                                f"Verwende ChromeDriver aus PATH (Windows): {driver_path}")
                        else:
                            raise FileNotFoundError(
                                "webdriver-manager nicht installiert und chromedriver.exe nicht im PATH gefunden.")
                else:  # Andere Systeme
                    if ChromeDriverManager:
                        try:
                            driver_path = ChromeDriverManager().install();
                            logger.info(
                                f"Verwende ChromeDriver via webdriver-manager ({system_name}): {driver_path}")
                        except Exception as wdm_err:
                            logger.error(
                                f"Fehler bei webdriver-manager auf {system_name}: {wdm_err}");
                            raise FileNotFoundError(
                                f"ChromeDriver konnte via webdriver-manager für {system_name} nicht installiert werden.")
                    else:
                        driver_in_path = shutil.which("chromedriver")
                        if driver_in_path:
                            driver_path = driver_in_path;
                            logger.info(
                                f"Verwende ChromeDriver aus PATH ({system_name}): {driver_path}")
                        else:
                            raise FileNotFoundError(
                                f"webdriver-manager nicht installiert und chromedriver nicht im PATH für {system_name} gefunden.")

                if driver_path:
                    service = ChromeService(executable_path=driver_path);
                    driver = webdriver.Chrome(service=service,
                                              options=options)
                else:
                    raise webdriver.support.wait.WebDriverException("ChromeDriver Pfad konnte nicht ermittelt werden.")

                local_url = temp_html_path.resolve().as_uri()
                driver.get(local_url)
                logger.debug(f"Warte {delay} Sekunden, bis die Karte '{temp_html_path}' für PNG geladen ist...")
                time.sleep(delay)
                driver.save_screenshot(str(temp_png_path))
                logger.info(f"Screenshot erfolgreich erstellt: {temp_png_path}")
            except (FileNotFoundError, webdriver.support.wait.WebDriverException, Exception) as e:
                logger.error(f"Fehler beim Erstellen des PNG-Screenshots für {png_file}: {e}", exc_info=True)
                if temp_html_path.exists(): temp_html_path.unlink()
                return
            finally:
                if driver: driver.quit()

            # --- PNG Cropping (unverändert) ---
            if self.crop_enabled and Image is not None:
                logger.info(f"Cropping für {final_png_path} wird durchgeführt.")
                try:
                    img = Image.open(str(temp_png_path));
                    img_width, img_height = img.size;
                    crop_box = None
                    if self.use_center_crop:
                        percentage = self.crop_center_percentage / 100.0;
                        min_dimension = min(img_width, img_height);
                        crop_side = int(min_dimension * percentage)
                        if crop_side > 0:
                            left = int((img_width - crop_side) / 2);
                            top = int((
                                              img_height - crop_side) / 2);
                            right = left + crop_side;
                            bottom = top + crop_side;
                            crop_box = (
                                left, top, right, bottom);
                            logger.debug(f"Berechnete Crop-Box (Center %): {crop_box}")
                        else:
                            logger.warning("Berechnete Crop-Seitenlänge <= 0. Kein Zuschnitt.")
                    else:
                        left_px = self.crop_pixel_left;
                        top_px = self.crop_pixel_top;
                        right_px = img_width - self.crop_pixel_right;
                        bottom_px = img_height - self.crop_pixel_bottom
                        if left_px < right_px and top_px < bottom_px:
                            crop_box = (left_px, top_px, right_px, bottom_px);
                            logger.debug(
                                f"Berechnete Crop-Box (Pixel Offset): {crop_box}")
                        else:
                            logger.error(
                                f"Ungültige Pixel-Offset-Werte ergeben ungültige Box: L={left_px}, T={top_px}, R={right_px}, B={bottom_px}")
                    if crop_box and crop_box[0] < crop_box[2] and crop_box[1] < crop_box[3]:
                        cropped_img = img.crop(crop_box);
                        cropped_img.save(str(final_png_path));
                        logger.info(f"Bild erfolgreich auf {final_png_path} zugeschnitten.")
                        if temp_png_path != final_png_path and temp_png_path.exists():
                            try:
                                temp_png_path.unlink()
                            except OSError as rm_err:
                                logger.warning(f"Konnte temporäre PNG {temp_png_path} nicht löschen: {rm_err}")
                    else:
                        logger.error(f"Ungültige/keine Crop-Box berechnet: {crop_box}. Originalbild wird verwendet.")
                        if temp_png_path != final_png_path and temp_png_path.exists():
                            try:
                                if final_png_path.exists(): final_png_path.unlink()
                                temp_png_path.rename(final_png_path);
                                logger.info(f"Temporäres PNG zu {final_png_path} umbenannt (kein Crop).")
                            except OSError as ren_err:
                                logger.error(f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")
                        elif temp_png_path == final_png_path:
                            logger.info(f"Kein Cropping, {final_png_path} wurde direkt erstellt.")
                except Exception as crop_err:
                    logger.error(f"Fehler beim Zuschneiden von {temp_png_path}: {crop_err}", exc_info=True)
                    if temp_png_path != final_png_path and temp_png_path.exists():
                        try:
                            if final_png_path.exists(): final_png_path.unlink()
                            temp_png_path.rename(final_png_path);
                            logger.info(f"Temporäres PNG zu {final_png_path} umbenannt (Crop fehlgeschlagen).")
                        except OSError as ren_err:
                            logger.error(f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")
            elif temp_png_path != final_png_path and temp_png_path.exists():
                try:
                    if final_png_path.exists(): final_png_path.unlink()
                    temp_png_path.rename(final_png_path);
                    logger.info(f"Temporäres PNG zu {final_png_path} umbenannt (Cropping deaktiviert).")
                except OSError as ren_err:
                    logger.error(f"Konnte temp PNG nicht zu {final_png_path} umbenennen: {ren_err}")

        finally:
            try:
                if temp_html_path.exists(): temp_html_path.unlink(); logger.debug(
                    f"Temporäre HTML-Datei {temp_html_path} gelöscht.")
            except OSError as e:
                logger.error(f"Fehler beim Löschen der temporären HTML-Datei {temp_html_path}: {e}")

    # --- ENDE save_html_as_png ---


# __main__ (angepasst für Test)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

    GEO_CONFIG["map_center"] = (46.8118, 7.1328)
    GEO_CONFIG["zoom_start"] = 22
    GEO_CONFIG["max_zoom"] = 22
    GEO_CONFIG["crop_enabled"] = False

    import time;

    ts_now = time.time()
    # Mehrere Sessions für den Test
    multi_data_sats = [
        [  # Session 1 (älter)
            {'lat': 46.8117, 'lon': 7.1327, 'satellites': 3, 'timestamp': ts_now - 15},
            {'lat': 46.81175, 'lon': 7.13275, 'satellites': 5, 'timestamp': ts_now - 14},
            {'lat': 46.8118, 'lon': 7.1328, 'satellites': 7, 'timestamp': ts_now - 13},
        ],
        [  # Session 2 (neuer)
            {'lat': 46.81185, 'lon': 7.13285, 'satellites': 9, 'timestamp': ts_now - 5},
            {'lat': 46.8119, 'lon': 7.1329, 'satellites': 11, 'timestamp': ts_now - 4},
            {'lat': 46.81195, 'lon': 7.13285, 'satellites': 4, 'timestamp': ts_now - 3},
        ]
    ]

    HEATMAP_CONFIG["test_quality_path_10"] = {
        "output": "heatmaps/test_quality_path_10.html",
        "png_output": "heatmaps/test_quality_path_10.png",
        "generate_png": False,
        "path_weight": 3.0,
        "path_opacity": 0.85,
        "show_start_end_markers": True,  # Marker für Multi-Session
        "visualize_quality_path": True,
        "quality_colormap_colors": ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'],
        "quality_colormap_index": [4, 6, 8, 10],
        "quality_legend_caption": "Anzahl Satelliten (Multi-Test)",
        "use_heatmap_with_time": False,
        "use_satellite_weight": False,
    }

    gen = HeatmapGenerator()

    logger.info("Teste Qualitäts-Pfadkarte für 10 Sessions (HTML)...")
    # Wichtig: draw_path=True und is_multi=True übergeben!
    gen.create_heatmap(multi_data_sats, "heatmaps/test_quality_path_10.html", draw_path=True, is_multi_session=True)

    logger.info("Heatmap-Generierungstests abgeschlossen.")
