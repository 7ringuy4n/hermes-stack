FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py classify.py chat_norm.py websearch.py .
COPY messages ./messages
COPY config ./config
ENV MODEL_ROUTER_PORT=8096
EXPOSE 8096
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8096"]
