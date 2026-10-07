FROM python:3.12-alpine

WORKDIR /app

# FFmpeg handles media merging; Node provides yt-dlp's JavaScript runtime.
RUN apk add --no-cache ffmpeg nodejs \
    && adduser -D -H -u 10001 app \
    && mkdir -p /data \
    && chown app:app /data

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY . ./api/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VESPERTAPE_DATA_DIR=/data

EXPOSE 8000
VOLUME ["/data"]
USER app
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
