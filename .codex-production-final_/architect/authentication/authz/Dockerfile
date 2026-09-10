FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV PORT=8097
EXPOSE 8097
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8097"]
