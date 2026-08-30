FROM python:3.12-slim
WORKDIR /app

# System libs: tesseract fallback + OpenCV/Paddle runtime deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie \
      libgomp1 libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional PaddleOCR (primary engine). INSTALL_PADDLE=1 on Media Worker stacks.
ARG INSTALL_PADDLE=1
COPY requirements-paddle.txt .
RUN if [ "$INSTALL_PADDLE" = "1" ]; then \
      pip install --no-cache-dir \
        paddlepaddle==3.2.0 \
        -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
      && pip install --no-cache-dir -r requirements-paddle.txt ; \
    fi

COPY app.py refuse.py result.py paddle_engine.py ./
ENV OCR_PADDLE=1 \
    OCR_VISION=inactive \
    OCR_PADDLE_MOBILE=1 \
    OCR_MEDIA_ROOT=/data/media \
    HOME=/tmp \
    FLAGS_use_mkldnn=0
EXPOSE 8091
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8091", "--workers", "1"]
