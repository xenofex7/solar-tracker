FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.lock.txt .
RUN pip install -r requirements.lock.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--preload", "--access-logfile", "-", "app:app"]
