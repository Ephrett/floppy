# FLOPPY in a container. The engine (Ollama) and the model are downloaded into /data on first run,
# so mount a volume there: your key lives in /data/engine/seed.hex and must survive container restarts.
#
#   docker build -t floppy .
#   docker run -d --name floppy -p 8788:8788 -v floppy-data:/data floppy
#   open http://127.0.0.1:8788
#
# On a machine with an NVIDIA GPU, add: --gpus all
FROM python:3.12-slim

# zstd: the official Ollama package for Linux is a .tar.zst archive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tar zstd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# pywebview is a desktop-only dependency: in a container the interface is served over HTTP
RUN grep -v pywebview requirements.txt > /tmp/req.txt && pip install --no-cache-dir -r /tmp/req.txt

COPY . .
ENV FLOPPY_HOME=/data FLOPPY_PORT=8788 FLOPPY_BIND=0.0.0.0 PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8788
CMD ["python3", "app.py", "--hidden"]
