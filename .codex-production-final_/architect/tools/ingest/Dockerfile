FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends p7zip-full unrar-free \
    && rm -rf /var/lib/apt/lists/*
COPY tools/ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lib/vision_ocr.py lib/vision_refuse.py ./
COPY tools/ingest/app.py .
COPY tools/ingest/archive_media.py .
COPY tools/ingest/secret_gate.py .
COPY tools/ingest/learn-notify.json .
EXPOSE 8099
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8099"]
