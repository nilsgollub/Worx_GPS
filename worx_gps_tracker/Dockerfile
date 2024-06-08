FROM arm64v8/python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Worx_GPS.py .
COPY .env .

# Ordner für Heatmaps erstellen
RUN mkdir /app/output

# Befehl zum Ausführen des Skripts
CMD ["python3", "Worx_GPS.py"]
