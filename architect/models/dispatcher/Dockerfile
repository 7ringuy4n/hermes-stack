FROM python:3.12-slim
WORKDIR /app
# curl only for Low. ffmpeg is optional (Medium+ video); install later if needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ocr_stub.py video_summary.py office_file.py image_backends.py ./
COPY comfy_workflows ./comfy_workflows
ENV MEDIA_CACHE_DIR=/data/media
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
