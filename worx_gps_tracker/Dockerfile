# Basis-Image für ARM-Architektur (Raspberry Pi)
FROM arm64v8/python:3.9-slim-buster

# Arbeitsverzeichnis im Container
WORKDIR /app

# Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev

# Virtuelle Python-Umgebung erstellen
RUN python3 -m venv /app/venv

# Virtuelle Umgebung aktivieren
ENV PATH="/app/venv/bin:$PATH"

# Kopieren der benötigten Dateien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Worx_GPS.py .
COPY .env .

# Volume für den Zugriff auf /config/www
VOLUME /config/www
ARG USER_ID
ARG GROUP_ID
RUN addgroup --gid $GROUP_ID user
RUN adduser --disabled-password --gecos "" --uid $USER_ID --gid $GROUP_ID user

# Benutzer auf "root" setzen
USER root

# Befehl zum Ausführen des Skripts
CMD ["python3", "Worx_GPS.py"]
