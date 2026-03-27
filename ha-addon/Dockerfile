# --- Final Python Image ---
FROM python:3.11-slim
WORKDIR /app

# Systemabhängigkeiten installieren (falls nötig)
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Gesamtes Projekt kopieren
COPY . .

# HINWEIS: Das Frontend muss lokal am PC gebaut werden (npm run build)
# Der fertige dist-Ordner wird dann hier inkludiert

# HA Add-on Data Persistenz
# Die SQLite DB und Heatmaps müssen nach /data verschoben werden (persistenter HA Speicher)
RUN mkdir -p /data/heatmaps && mkdir -p /data/data

# Skripte für den Add-on Start
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Port 5001 für WebUI
EXPOSE 5001

CMD [ "/app/run.sh" ]
