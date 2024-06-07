# Basis-Image für ARM-Architektur (Raspberry Pi)
FROM arm64v8/python:3.9-slim-buster

# Arbeitsverzeichnis im Container
WORKDIR /app

# Mounten des Ausgabeverzeichnisses
VOLUME /config/www/worx_gps_tracker/output

# Kopieren der benötigten Dateien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Worx_GPS.py .
COPY .env .

# Befehl zum Ausführen des Skripts
CMD ["python3", "Worx_GPS.py"]
