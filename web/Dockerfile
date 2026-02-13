FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git android-tools-adb ca-certificates procps \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY web /app/web
COPY agent-core /app/agent-core
COPY main.py /app/main.py
COPY run-config.json /app/run-config.json
COPY web/entrypoint.sh /app/entrypoint.sh

RUN mkdir -p /app/output /app/web/data/apks /app/web/data/scenarios /app/output-frontend \
  && chmod +x /app/entrypoint.sh \
  && useradd -m -u 10001 appuser \
  && chown -R appuser:appuser /app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
