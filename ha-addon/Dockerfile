# --- Stage 1: Build Frontend (React/Vite) ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Kopiere nur package Dateien für besseres Caching
COPY frontend/package*.json ./
RUN npm install

# Kopiere restliche Frontend-Dateien und baue
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Final Python Image ---
FROM python:3.11-slim
WORKDIR /app

# Systemabhängigkeiten installieren (falls nötig)
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Gesamtes Projekt kopieren (ohne node_modules/frontend-src)
COPY . .

# Überschreibe frontend/dist mit dem Build aus Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# HA Add-on Data Persistenz
# Die SQLite DB und Heatmaps müssen nach /data verschoben werden (persistenter HA Speicher)
RUN mkdir -p /data/heatmaps && mkdir -p /data/data

# Skripte für den Add-on Start
COPY ha-addon/run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Port 5001 für WebUI
EXPOSE 5001

CMD [ "/app/run.sh" ]
