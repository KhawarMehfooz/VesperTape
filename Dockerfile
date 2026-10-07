FROM node:lts-alpine AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-alpine AS runtime
WORKDIR /app

# yt-dlp uses FFmpeg for merging/post-processing and Node as its JS runtime.
RUN apk add --no-cache ffmpeg nodejs \
    && adduser -D -H -u 10001 app \
    && mkdir -p /data \
    && chown app:app /data

COPY api/requirements.lock ./api/requirements.lock
RUN pip install --no-cache-dir -r api/requirements.lock

COPY api/ ./api/
COPY --from=web-build /web/dist ./web/dist

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VESPERTAPE_DATA_DIR=/data

EXPOSE 8000
VOLUME ["/data"]
USER app
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
