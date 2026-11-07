FROM python:3.12-alpine

WORKDIR /app
COPY app.py .

ENTRYPOINT ["python3", "app.py"]
