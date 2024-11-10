# Verwende das Python 3.11 Slim-Image
FROM python:3.11-slim

# Setze das Arbeitsverzeichnis im Container
WORKDIR /app

# Kopiere alle Dateien in den Container
COPY . /app

# Installieren Sie System-Abhängigkeiten, die für die Kompilierung von Python-Paketen erforderlich sind
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Installiere alle notwendigen Python-Pakete
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Setze Umgebungsvariablen
ENV ELECTRUMX_SERVER_URL="http://localhost:8000"  

# Run the script when the container launches
CMD ["python", "enigmacracker.py"]