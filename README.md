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

The app supports metadata-only link previews and playlist selection. Job persistence and downloads are not implemented yet.

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
names, not client-supplied filesystem paths. The preview endpoint is available; job endpoint wiring follows in Milestone #3.

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
Preview links and extractor-generated requests are checked against public network addresses.


## Link previews

`POST /api/preview` accepts `{"url":"https://example.com/video"}` and returns
`PreviewResponse`: source URL, video or playlist kind, title, items, and total
playlist size when the extractor supplies it. Items include uploader, thumbnail,
duration, and available media formats; unavailable metadata is `null`.
Extraction uses yt-dlp with `download=False` and disables its disk cache.
The UI displays loading, errors, empty playlists, and items without formats.

Playlist previews inspect at most 100 entries to limit extraction work. Full
playlist selection uses an empty `item_indices` list, while one-item and inclusive
range selections use the original one-based playlist indexes visible in the
preview. The full selection also includes entries beyond the preview limit when
job submission is implemented. Selection is currently local to the preview UI;
no download is queued. A private or unavailable entry may prevent previewing its
playlist. Requests have a 15-second socket timeout and limited retries, but large
playlists can still take time to inspect. Editing the URL cancels the browser
request and discards stale responses; server extraction may finish in its thread.

Preview errors use the shared envelope with `unsupported_link`, `private_link`,
`preview_failed`, `invalid_target`, or `blocked_target`. Private-link detection
uses yt-dlp's error messages and may vary between extractors. Raw extractor errors
and submitted URLs are not logged by the preview service or echoed in errors.

Only HTTP and HTTPS URLs without credentials are accepted. DNS answers must all
be globally routable; loopback, private, link-local, and other non-public addresses
are rejected for the source and extractor-generated requests. Ambient proxy
configuration is disabled for previews. These are best-effort checks: transport
redirects and DNS rebinding are not fully covered. Use network-level egress
restrictions for untrusted deployments. Thumbnails load directly in the browser
from the metadata URL with no referrer. Previews require outbound internet access
and a working CA certificate bundle; site authentication is not configured yet.

Run preview checks with `python -m unittest api.tests.test_preview`.
