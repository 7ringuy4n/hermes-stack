FROM python:3.12-slim
WORKDIR /app
COPY stack-exporter/app.py .
COPY optional_services.py .
EXPOSE 9102
CMD ["python", "-u", "app.py"]
