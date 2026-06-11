FROM python:3.12-slim

LABEL description="DXF to TRUMPF GEO Converter"
LABEL maintainer="sysadmin-homelab.de"

RUN apt-get update && apt-get install -y --no-install-recommends \
    inotify-tools \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir ezdxf fastapi uvicorn python-multipart

WORKDIR /app

COPY converter.py /app/converter.py
COPY web.py /app/web.py
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

VOLUME ["/input", "/output"]

ENV INPUT_DIR=/input
ENV OUTPUT_DIR=/output
ENV WATCH_MODE=false

EXPOSE 8000

CMD ["uvicorn", "web:app", "--host", "0.0.0.0", "--port", "8000"]