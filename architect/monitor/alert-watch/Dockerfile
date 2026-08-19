FROM python:3.12-slim
WORKDIR /app
COPY alert-watch/app.py .
COPY optional_services.py .
EXPOSE 9103
CMD ["python", "-u", "app.py"]
