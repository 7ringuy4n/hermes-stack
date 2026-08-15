FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py worker.py .
EXPOSE 8104
# default: API; worker service overrides command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8104"]
