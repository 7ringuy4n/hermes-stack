FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    SECRET_PROBE_POLICY=/app/secret-probe.json
RUN pip install --no-cache-dir fastapi==0.115.12 uvicorn[standard]==0.34.2 httpx==0.28.1 valkey==6.1.1
COPY app.py .
COPY secret_probe.py .
COPY secret-probe.json .
COPY classify_client.py .
COPY messages ./messages
EXPOSE 8088
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8088"]
