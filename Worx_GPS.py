import paho.mqtt.client as mqtt
import time
import random
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import json
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load environment variables from .env file
load_dotenv("secrets.env")

# Get MQTT credentials from environment variables after loading
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# MQTT-Einstellungen
CONTROL_TOPIC = "worx/control"
GPS_TOPIC = "worx/gps"
STATUS_TOPIC = "worx/status"
MAP_FILE = "heatmap.html"
LAST_10_MOWS_FILE = "last_10_mows.csv"
PROBLEM_DATA_FILE = "problem_data.csv"
MOW_HISTORY_FILE = "mow_history.jsonl"  # Datei für einzelne Mähvorgänge

# Grundstücksgrenzen (als Liste von Koordinaten)
BOUNDARY_COORDS = [(46.812107, 7.132857), (46.812085, 7.133173), (46.811819, 7.133167), (46.811838, 7.132838)]

# Datenstrukturen
last_mow_data = []
problem_data = pd.DataFrame(columns=["Latitude", "Longitude", "Timestamp"])
all_mows_data = pd.DataFrame(columns=["Latitude", "Longitude", "Timestamp"])


# MQTT-Callback-Funktionen
def on_connect(client, userdata, flags, rc):
    print("Verbunden mit MQTT-Broker")
    client.subscribe(GPS_TOPIC)
    client.subscribe(STATUS_TOPIC)

    # Lade vorherige Mähdaten beim Verbinden, falls vorhanden
    if os.path.exists(LAST_10_MOWS_FILE):
        global all_mows_data
        all_mows_data = pd.read_csv(LAST_10_MOWS_FILE)


def on_message(client, userdata, msg):
    global last_mow_data, problem_data, all_mows_data

    if msg.topic == GPS_TOPIC:
        payload = msg.payload.decode()
        if payload:
            last_mow_data = process_gps_data(payload, is_gps=True)  # Mark as GPS data
            create_heatmap(last_mow_data, "Letzter Mähvorgang", MAP_FILE)

            # Speichere den aktuellen Mähvorgang als JSON Lines
            mow_data = {
                "start_time": datetime.fromtimestamp(last_mow_data[0][2]).isoformat() + 'Z',
                "end_time": datetime.fromtimestamp(last_mow_data[-1][2]).isoformat() + 'Z',
                "gps_data": last_mow_data
            }
            with open(MOW_HISTORY_FILE, "a") as f:
                f.write(json.dumps(mow_data) + "\n")

            # Füge die neuen Daten zu den gesamten Mähdaten hinzu
            all_mows_data = pd.concat(
                [all_mows_data, pd.DataFrame(last_mow_data, columns=["Latitude", "Longitude", "Timestamp"])])

            # Behalte nur die letzten 10 Mähvorgänge
            all_mows_data = all_mows_data.sort_values("Timestamp", ascending=False).head(
                10 * 3600)  # 10 Mähvorgänge * 3600 Sekunden pro Mähvorgang

            # Speichere die aktualisierten Mähdaten
            all_mows_data.to_csv(LAST_10_MOWS_FILE, index=False)

            # Erstelle die Heatmap für die letzten 10 Mähvorgänge
            create_heatmap(all_mows_data.values.tolist(), "Letzte 10 Mähvorgänge", "last_10_heatmap.html")

    elif msg.topic == STATUS_TOPIC:  # Handle problem data here
        payload = msg.payload.decode()
        process_problem_data(payload)
        create_problem_heatmap(problem_data, "Problemzonen", "problem_heatmap.html")


# Update process_gps_data function to handle both cases
def process_gps_data(payload, is_gps=True):
    data = []
    for point in payload.split(";"):
        if point:
            if is_gps:
                lat, lon, timestamp = point.split(",")
                data.append((float(lat), float(lon), int(timestamp)))
            else:  # Problem data
                lat, lon = point.split(",")
                data.append((float(lat), float(lon)))  # No timestamp for problem data
    return data


def process_problem_data(payload):
    global problem_data
    lat, lon, timestamp = payload.split(",")
    problem_data = problem_data.append({"Latitude": float(lat), "Longitude": float(lon), "Timestamp": int(timestamp)},
                                       ignore_index=True)
    problem_data.to_csv(PROBLEM_DATA_FILE, index=False)  # Speichern der Problemdaten


def create_heatmap(data, title, filename):
    df = pd.DataFrame(data, columns=["Latitude", "Longitude", "Timestamp"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s")

    # Filter für die letzten 7 Tage (nur für die zweite Heatmap)
    if title == "Letzter Mähvorgang":
        df_filtered = df
    else:
        df_filtered = df[df["Timestamp"] >= datetime.now() - timedelta(days=7)]

    m = folium.Map(location=[df_filtered["Latitude"].mean(), df_filtered["Longitude"].mean()], zoom_start=18,
                   tiles="OpenStreetMap")
    folium.Marker(location=[df["Latitude"].iloc[0], df["Longitude"].iloc[0]], icon=folium.Icon(color="green")).add_to(
        m)  # Startpunkt
    folium.Marker(location=[df["Latitude"].iloc[-1], df["Longitude"].iloc[-1]], icon=folium.Icon(color="red")).add_to(
        m)  # Endpunkt

    # Heatmap erstellen
    heatmap = sns.kdeplot(
        x=df_filtered["Longitude"],
        y=df_filtered["Latitude"],
        cmap="Reds",
        shade=True,
        bw_adjust=0.5,
    )
    plt.figure(figsize=(10, 8))  # Größe der Heatmap anpassen
    plt.title(title)
    plt.axis("off")  # Achsenbeschriftungen entfernen
    plt.savefig("heatmap.png", bbox_inches="tight", pad_inches=0)  # Heatmap als PNG speichern
    plt.close()

    # Heatmap als ImageOverlay zur Karte hinzufügen
    folium.raster_layers.ImageOverlay(
        image="heatmap.png",
        bounds=[[df_filtered["Latitude"].min(), df_filtered["Longitude"].min()],
                [df_filtered["Latitude"].max(), df_filtered["Longitude"].max()]],
        opacity=0.7,
    ).add_to(m)

    # Grundstücksgrenzen hinzufügen
    folium.PolyLine(BOUNDARY_COORDS, color="blue", weight=2.5, opacity=1).add_to(m)

    # LayerControl hinzufügen
    folium.LayerControl().add_to(m)

    m.save(filename)


def create_problem_heatmap(data, title, filename):
    if not data.empty:
        m = folium.Map(location=[data["Latitude"].mean(), data["Longitude"].mean()], zoom_start=18,
                       tiles="OpenStreetMap")

        for _, row in data.iterrows():
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=5,
                color="red",
                fill=True,
                fill_color="red",
                fill_opacity=0.7,
                popup=f"Problem at {row['Timestamp']}"
            ).add_to(m)

        # LayerControl hinzufügen
        folium.LayerControl().add_to(m)

        m.save(filename)


# MQTT-Client erstellen und verbinden
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.connect(MQTT_HOST, MQTT_PORT, 60)

# MQTT-Schleife starten
client.loop_forever()
