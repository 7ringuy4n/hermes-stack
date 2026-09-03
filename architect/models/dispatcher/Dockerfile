FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates fonts-dejavu-core fonts-noto-core ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY models/dispatcher/requirements.txt models/dispatcher/requirements-whisper.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ARG INSTALL_WHISPER=0
RUN if [ "$INSTALL_WHISPER" = "1" ]; then \
      pip install --no-cache-dir -r requirements-whisper.txt; \
    fi
COPY lib/vision_ocr.py lib/vision_refuse.py ./
COPY models/dispatcher/app.py models/dispatcher/video_summary.py models/dispatcher/office_file.py models/dispatcher/image_backends.py models/dispatcher/text_poster.py models/dispatcher/video_clip.py models/dispatcher/fonts.py models/dispatcher/weather_sheet.py models/dispatcher/overlay.py models/dispatcher/env_flags.py ./
COPY models/dispatcher/fonts ./fonts
ENV MEDIA_CACHE_DIR=/data/media
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
