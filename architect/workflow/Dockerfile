FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY plan.py store.py postgres.py manager.py app.py classify_client.py .
EXPOSE 8108
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8108"]
