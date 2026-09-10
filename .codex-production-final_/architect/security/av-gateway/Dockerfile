FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      clamdscan netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV PORT=8098
EXPOSE 8098
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8098"]
