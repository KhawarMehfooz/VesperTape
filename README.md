# VesperTape

A self-hosted video downloader with a React interface and a Python service powered by yt-dlp.

## Development

Run the Python API in Docker:

```sh
docker compose up --build -d
```

The API is available at `http://localhost:8000`. Set `VESPERTAPE_API_PORT` to change the host port. Compose stores application data in the `vespertape-data` volume.

In a second terminal, run the React app locally:

```sh
cd web
npm ci
npm run dev
```

Open the Vite URL it prints, usually `http://localhost:5173`. Vite proxies `/api` requests to the Docker API on port 8000.

The current scaffold includes the app shell and an API health endpoint. Link inspection, job persistence, and downloads are not implemented yet.

## Run the API without Docker

Run these commands from the repository root:

```sh
cd api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
uvicorn main:app --reload --port 8000
```

`web/package-lock.json` pins the frontend dependencies. `api/requirements.lock` pins the Python dependencies used by Docker and pip.
