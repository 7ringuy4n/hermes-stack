FROM python:3.12-slim
WORKDIR /app
# ffmpeg: default video path is still→H.264 (Zalo send-attachment).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates fonts-dejavu-core fonts-noto-core ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-whisper.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# ASR is optional: the base image stays slim unless the stack asks for it.
ARG INSTALL_WHISPER=0
RUN if [ "$INSTALL_WHISPER" = "1" ]; then \
      pip install --no-cache-dir -r requirements-whisper.txt; \
    fi
COPY app.py ocr_stub.py video_summary.py office_file.py image_backends.py text_poster.py overlay.py video_clip.py fonts.py info_card.py ./
COPY fonts ./fonts
COPY comfy_workflows ./comfy_workflows
ENV MEDIA_CACHE_DIR=/data/media
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
