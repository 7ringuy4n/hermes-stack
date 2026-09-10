FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.12 uvicorn[standard]==0.34.2 pydantic==2.11.3
COPY app.py .
EXPOSE 8105
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8105"]
