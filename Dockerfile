# Use Python 3.8 as base image (compatible with Jetson/L4T)
FROM python:3.8-slim-buster

# Install system dependencies for pandas/geopy and chromium for heatmaps
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    chromium-browser \
    chromium-chromedriver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to keep image size down
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose the Flask port
EXPOSE 5000

# Start the Flask web server
CMD ["python", "web_ui/webui.py"]
