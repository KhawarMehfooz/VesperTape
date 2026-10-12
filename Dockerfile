# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72 AS runtime
WORKDIR /app

# yt-dlp uses FFmpeg for merging/post-processing and Node as its JS runtime.
RUN apk add --no-cache ffmpeg nodejs \
    && adduser -D -H -u 10001 app \
    && mkdir -p /data \
    && chown app:app /data

COPY api/requirements.lock ./api/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip pip install -r api/requirements.lock

COPY api/*.py ./api/
COPY --from=web-build /web/dist ./web/dist

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VESPERTAPE_DATA_DIR=/data

EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
USER app
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-graceful-shutdown", "20"]
