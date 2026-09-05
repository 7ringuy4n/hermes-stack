FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates fonts-dejavu-core fonts-inter fonts-noto-core ffmpeg \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi8 \
      shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
COPY models/dispatcher/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY lib/vision_ocr.py lib/vision_refuse.py ./
COPY models/dispatcher/app.py models/dispatcher/video_summary.py models/dispatcher/office_file.py models/dispatcher/image_backends.py models/dispatcher/text_poster.py models/dispatcher/video_clip.py models/dispatcher/fonts.py models/dispatcher/overlay.py models/dispatcher/env_flags.py ./
COPY models/dispatcher/fonts ./fonts
ENV MEDIA_CACHE_DIR=/data/media
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
