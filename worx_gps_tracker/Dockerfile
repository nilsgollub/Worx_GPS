# Basis-Image für ARM-Architektur (Raspberry Pi)
FROM arm64v8/python:3.9-slim-buster

# Arbeitsverzeichnis im Container
WORKDIR /app

# Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    cifs-utils # Samba-Client-Tools installieren

# Virtuelle Python-Umgebung erstellen
RUN python3 -m venv /app/venv

# Virtuelle Umgebung aktivieren
ENV PATH="/app/venv/bin:$PATH"

# Kopieren der benötigten Dateien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Worx_GPS.py .
COPY .env .

# Samba-Freigabe einbinden (Anmeldedaten anpassen!)
RUN mkdir /mnt/worx_gps_tracker
CMD mount -t cifs -o username=$nilsgollub,password=$JhiswenP3003!,mfsymlinks //192.168.1.117/config/www/worx_gps_tracker /mnt/worx_gps_tracker
# Befehl zum Ausführen des Skripts
CMD ["python3", "Worx_GPS.py"]
