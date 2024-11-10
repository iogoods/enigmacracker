# Verwende das Python 3.11 Slim-Image
FROM python:3.11-slim

# Setze das Arbeitsverzeichnis im Container
WORKDIR /app

# Kopiere alle Dateien in den Container
COPY . /app

# Installiere alle notwendigen Python-Pakete
RUN pip install --no-cache-dir -r requirements.txt

# Setze Umgebungsvariablen
ENV ELECTRUMX_SERVER_URL="http://localhost:8000"  

# Run the script when the container launches
CMD ["python", "enigmacracker.py"]
