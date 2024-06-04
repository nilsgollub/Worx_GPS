import folium
rasenflaeche_coords = [
    (46.812099423685886, 7.13294504532412),
    (46.81207923114223, 7.133169680326546),
    (46.81205766182586, 7.13316565701307),
    (46.812054908295465, 7.1331294471917825),
    (46.81200809825755, 7.13312140056483),
    (46.812001214424996, 7.133160292595101),
    (46.811831412942134, 7.13314688155048),
    (46.811847475267406, 7.132844462487513),
    (46.811959452487436, 7.132857202980187),
    (46.811973679084794, 7.132917552682331),
    (46.81191814944163, 7.1329095060553795),
    (46.81191172452053, 7.133020817728223),
    (46.811929163590264, 7.133023499937206),
    (46.81192549220765, 7.133100613445501),
    (46.81202507837282, 7.133110001176946),
    (46.812027372982726, 7.133094578475288),
    (46.81205197798022, 7.133091556307457),
    (46.81206171583993, 7.132939570211207),
    (46.812099423685886, 7.13294504532412)  # Erstes Tupel wiederholt
]
START_POSITION = (46.811967713094056, 7.133148222656783)


# Erstelle eine Folium-Karte mit dem Mittelpunkt der Rasenfläche
lat_bounds = [min(lat for lat, _ in rasenflaeche_coords), max(lat for lat, _ in rasenflaeche_coords)]
lon_bounds = [min(lon for _, lon in rasenflaeche_coords), max(lon for _, lon in rasenflaeche_coords)]
map_center = [(lat_bounds[0] + lat_bounds[1]) / 2, (lon_bounds[0] + lon_bounds[1]) / 2]
m = folium.Map(location=map_center, zoom_start=18, tiles="OpenStreetMap")

# Füge die Rasenfläche als Polygon hinzu
folium.Polygon(
    locations=rasenflaeche_coords,
    color="blue",
    fill=True,
    fill_color="green",
    fill_opacity=0.5,
    weight=2,
).add_to(m)
# Startposition markieren
folium.Marker(
    location=START_POSITION,
    popup="Startposition",
    icon=folium.Icon(color='red', icon='play', prefix='fa')  # Roter Marker mit Play-Symbol
).add_to(m)
# Speichere die Karte als HTML-Datei
m.save("rasenflaeche.html")
