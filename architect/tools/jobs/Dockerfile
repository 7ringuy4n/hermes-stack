FROM python:3.12-slim
WORKDIR /app
COPY tools/jobs/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lib/vision_ocr.py lib/vision_refuse.py ./
COPY tools/jobs/app.py tools/jobs/worker.py ./
EXPOSE 8104
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8104"]
