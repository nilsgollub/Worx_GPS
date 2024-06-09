FROM arm64v8/python:3.9-slim-buster

WORKDIR /app

# Ordner für Heatmaps erstellen
RUN mkdir /app/output

# Kopieren der benötigten Dateien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Worx_GPS.py .
COPY .env .

# Volume für den Zugriff auf /config/www
VOLUME /config/www

# Befehl zum Ausführen des Skripts
CMD ["python3", "Worx_GPS.py"]
