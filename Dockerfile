FROM python:3.12-slim

LABEL description="DXF to TRUMPF GEO Converter"
LABEL maintainer="sysadmin-homelab.de"

# Install inotify-tools for watch mode
RUN apt-get update && apt-get install -y --no-install-recommends \
    inotify-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir ezdxf

WORKDIR /app
COPY converter.py /app/converter.py
COPY entrypoint.sh /app/entrypoint.sh

# Volumes
VOLUME ["/input", "/output"]

# Environment variables with defaults
ENV INPUT_DIR=/input
ENV OUTPUT_DIR=/output
ENV WATCH_MODE=false

ENTRYPOINT ["/app/entrypoint.sh"]
