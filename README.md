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

## API contracts

`api/contracts.py` defines request and response models. Generated frontend types
live in `web/src/api/contracts.ts`. After changing a model, regenerate and check
the contracts using the API's Python environment:

```sh
python -m scripts.generate_api_types
python -m scripts.generate_api_types --check
python -m unittest api.tests.test_contracts
```

Use `CreateJobInput` for job submissions; omitted settings use server defaults.
Responses include all fields, with `null` for unavailable values. Playlist indexes
are one-based; an empty selection means all items. Durations and ETA are seconds,
and sizes and speeds use bytes and bytes per second. Destinations are configured
names, not client-supplied filesystem paths. Preview and job endpoint wiring will
be added in subsequent milestones.

## Application configuration

Configuration is read from environment variables at API startup. Invalid values
or unusable storage directories stop startup. Restart the API after changes.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VESPERTAPE_DATA_DIR` | `data` locally, `/data` in Docker | Application storage |
| `VESPERTAPE_DOWNLOAD_DIR` | `<data directory>/downloads` | Download storage |
| `VESPERTAPE_WORKER_COUNT` | `1` | Positive integer; used when workers are implemented |
| `VESPERTAPE_ALLOWED_MODES` | `["video","audio"]` | JSON array of allowed modes |
| `VESPERTAPE_ALLOWED_QUALITIES` | `["best","1080p","720p","480p"]` | JSON array of allowed qualities |
| `VESPERTAPE_ALLOWED_FORMATS` | `["auto","mp4","webm","mp3","m4a","flac","wav"]` | JSON array of allowed formats |

Option arrays must be nonempty, unique, and use the supported values above.
Their first entries become public defaults. `GET /api/settings` exposes these
defaults, allowed values, worker count, and the `default` destination name.
Directory paths stay on the server; paths are resolved relative to the API's
working directory and created on startup. Use distinct data and download paths.
The default Docker download directory persists in the existing `/data` volume.
For custom paths in Docker, add the environment variables and matching writable
volume mounts to `docker-compose.yml`. Local execution reads exported environment
variables; it does not automatically load `.env` files.

Run configuration checks with `python -m unittest api.tests.test_settings`.

## SQLite storage and migrations

The API creates `vespertape.sqlite3` in the configured data directory on startup.
In Docker this persists in the existing `/data` volume. SQLite uses WAL mode,
foreign-key enforcement, full synchronous writes, and a five-second lock timeout.
Use local storage with SQLite locking support for the data directory.

`api/database.py` owns connections and an ordered migration list. Each request or
worker should open its own `app.state.database.connection()` context in the thread
that uses it. Successful transactions commit; exceptions roll back; connections
always close.

Startup takes a write lock, checks the `schema_migrations` ledger, and applies
pending migrations in one transaction. Failed migrations stop startup and roll
back schema changes and ledger entries. A database with newer or incompatible
migration history also stops startup. The baseline establishes the ledger; job
tables will be added in Milestone #3.

Append consecutive migrations with individual SQL statements; keep released
migrations unchanged. Automatic downgrades are not supported. Before upgrading,
stop the service and back up the data volume, including the database and any
`-wal` and `-shm` files. Restore that backup when reverting a schema upgrade.

API tests live in `api/tests/`. Run them from the repository root with
`python -m unittest discover -s api/tests -t .`.

## API errors and validation

API failures use the same JSON envelope:

```json
{"error":{"code":"validation_error","message":"Request validation failed","details":[{"location":["body","url"],"message":"Invalid value","code":"value_error"}]}}
```

Invalid requests return HTTP 422 with field locations and error codes. Unknown
routes return 404 (`not_found`), unsupported methods return 405
(`method_not_allowed`), and unexpected failures return 500 (`internal_error`).
Error responses omit submitted values and internal exception text. Future
application errors should use `ApiException` with intentionally public messages.
OpenAPI documents the shared error schema at `/docs`.

URL requests accept HTTP or HTTPS without embedded credentials. Playlist indexes
must be unique positive integers. Destination names currently accept `default`;
optional filenames must be a single safe name, at most 200 UTF-8 bytes, without
yt-dlp template substitutions. Server allowlists are checked with
`AppSettings.validate_download_settings()` when job submission is implemented.
Network-target checks and link extraction remain part of Milestone #2.
