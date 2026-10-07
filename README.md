# VesperTape

A self-hosted video downloader with a React interface and a Python service powered by yt-dlp.

## Run with Docker Compose

```sh
docker compose up --build
```

Open `http://localhost:8080`. Set `VESPERTAPE_PORT` to change the host port. Compose stores application data in the `vespertape-data` volume.

The current scaffold includes the app shell and an API health endpoint. Link inspection, job persistence, and downloads are not implemented yet.

## Local development

Run the API from the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000
```

In another terminal, start the Vite development server:

```sh
cd web
npm install
npm run dev
```

Vite proxies `/api` requests to the local FastAPI server.
