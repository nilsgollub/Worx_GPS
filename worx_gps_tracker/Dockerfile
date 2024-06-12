# Basis-Image für ARM-Architektur (Raspberry Pi)
FROM arm64v8/python:3.9-slim-buster

# Arbeitsverzeichnis im Container
WORKDIR /app

# Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev

# Virtuelle Python-Umgebung erstellen
RUN python3 -m venv /app/venv

# Virtuelle Umgebung aktivieren
ENV PATH="/app/venv/bin:$PATH"

# Ordner für Heatmaps erstellen
RUN mkdir /app/output

# Kopieren der benötigten Dateien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Worx_GPS.py .
COPY .env .

# Volume für den Zugriff auf /config/www
VOLUME /config/www/worx_gps_tracker
VOLUME /share
USER root
# Befehl zum Ausführen des Skripts
CMD ["python3", "Worx_GPS.py"]
