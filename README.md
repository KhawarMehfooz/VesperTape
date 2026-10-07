# VesperTape

A self-hosted YouTube video downloader with a React interface and a Python service powered by yt-dlp.

## Development

Run the Python API in Docker:

```sh
docker compose up --build -d
```

The API is available at `http://localhost:8000`. Set `VESPERTAPE_API_PORT` to change the host port. Compose stores application data in the `vespertape-data` volume.

After API code changes, rerun `docker compose up --build -d`; Compose does not mount the source code. If the UI cannot load download settings, check `http://localhost:8000/api/settings`. A 404 can indicate an older container image; rebuild it and use Retry settings or refresh the page.

In a second terminal, run the React app locally:

```sh
cd web
npm ci
npm run dev
```

Open the Vite URL it prints, usually `http://localhost:5173`. Vite proxies `/api` requests to the Docker API on port 8000.

The app supports link previews, playlist selection, and a live persistent download queue.
The Classic Download Window layout (variant A of the design study) supports previewing a link, selecting playlist items, and adding audio or video downloads. Controls use server defaults and allowed options. Choose quality, format, a configured server destination, and an optional file name; API validation errors appear beside the submission controls. The app uses the static study’s original Classic Window markup, CSS, icons, panels, and responsive rules, with simplified VesperTape branding. Advanced options are displayed but disabled until supported by the API. The layout stacks at 700px and uses single-column settings at 410px.

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
names, not client-supplied filesystem paths. The preview and job endpoints are available.

## Application configuration

Configuration is read from environment variables at API startup. Invalid values
or unusable storage directories stop startup. Restart the API after changes.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VESPERTAPE_DATA_DIR` | `data` locally, `/data` in Docker | Application storage |
| `VESPERTAPE_DOWNLOAD_DIR` | `<data directory>/downloads` | Download storage |
| `VESPERTAPE_WORKER_COUNT` | `1` | Positive integer; concurrent downloads (default: one) |
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
migration history also stops startup. The baseline establishes the ledger; migration 2 adds jobs and the queue revision.

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

Preview and job requests accept YouTube video or playlist HTTP/HTTPS links without embedded credentials. The UI validates the hostname and media ID before sending a request; the API enforces the same restrictions. Watch, youtu.be, Shorts, live, embed, and playlist links are supported, including mobile and music subdomains. Channel pages, lookalike domains, malformed IDs, duplicate video/playlist parameters, and custom ports are rejected. Syntax validation does not establish availability: preview still checks whether YouTube can supply accessible media. Playlist indexes
must be unique positive integers. Destination names currently accept `default`;
optional filenames must be a single safe name, at most 200 UTF-8 bytes, without
yt-dlp template substitutions. Server allowlists are checked with
`AppSettings.validate_download_settings()` on submission.
Preview links and extractor-generated requests are checked against public network addresses.


## Link previews

`POST /api/preview` accepts `{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}` and returns
`PreviewResponse`: source URL, video or playlist kind, title, items, and total
playlist size when the extractor supplies it. Items include uploader, thumbnail,
duration, and available media formats; unavailable metadata is `null`.
Extraction uses yt-dlp with `download=False` and disables its disk cache.
The UI displays loading, errors, empty playlists, and items without formats.

Playlist previews inspect at most 100 entries to limit extraction work. Full
playlist selection uses an empty `item_indices` list, while one-item and inclusive
range selections use the original one-based playlist indexes visible in the
preview. The full selection also includes entries beyond the preview limit. Add to Downloads submits the current selection and settings to the job API. A private or unavailable entry may prevent previewing its
playlist. Requests have a 15-second socket timeout and limited retries, but large
playlists can still take time to inspect. Editing the URL cancels the browser
request and discards stale responses; server extraction may finish in its thread.

Preview errors use the shared envelope with `unsupported_link`, `private_link`,
`preview_failed`, `invalid_target`, `blocked_target`, `youtube_verification_required`, or `source_rate_limited`. Private-link detection
uses yt-dlp's error messages and may vary between extractors. Raw extractor errors
and submitted URLs are not logged by the preview service or echoed in errors.

User-supplied sources must be YouTube media links. Extractor-generated requests and thumbnail URLs can use other public HTTP/HTTPS hosts, such as YouTube’s media and image servers. DNS answers must all
be globally routable; loopback, private, link-local, and other non-public addresses
are rejected for the source and extractor-generated requests. Ambient proxy
configuration is disabled for previews. These are best-effort checks: transport
redirects and DNS rebinding are not fully covered. Use network-level egress
restrictions for untrusted deployments. Thumbnails load directly in the browser
from the metadata URL with no referrer. Previews require outbound internet access
and a working CA certificate bundle; site authentication is not configured yet.

Run preview checks with `python -m unittest api.tests.test_preview`.


## Persistent downloads

`POST /api/jobs` validates a public source URL and settings, persists the job, and
returns HTTP 201 with a `JobResponse`. Omitted settings use configured server
defaults, including partially specified settings. Audio accepts `auto`, `mp3`,
`m4a`, `flac`, or `wav`; video accepts `auto`, `mp4`, or `webm`. Incompatible
mode/format combinations and disabled server options return HTTP 422.

```sh
curl -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","selection":{"item_indices":[]},"settings":{"mode":"video","quality":"720p","format":"mp4"}}'
```

Replace the example URL with a public YouTube video or playlist URL. Empty playlist indexes
select the entire playlist; explicit indexes select those original one-based
entries. Job creation checks network eligibility; media availability and playlist
index existence are checked during extraction, with failures persisted on the job.
`GET /api/jobs` lists persisted jobs in submission order, and
`GET /api/jobs/{id}` retrieves one job. Raw extractor exceptions are never included
in failure responses.

Workers claim queued jobs atomically in submission order. The default worker count
is one; increase `VESPERTAPE_WORKER_COUNT` for parallel jobs. Run one API process
per data directory (no `uvicorn --workers`); a process lock prevents another API
instance from resetting active work during startup. Each job writes beneath
`<download directory>/<job ID>/`, with media IDs and playlist indexes in filenames
to avoid collisions. Audio conversion and video merging/remuxing require FFmpeg,
which is installed in Docker. Local API execution needs FFmpeg and Node 22 or newer on PATH. Previews and workers explicitly enable Node for YouTube’s JavaScript challenges; the pinned `yt-dlp-ejs` dependency supplies the solver scripts. See the [yt-dlp EJS setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

Progress is saved at most twice per second, plus transfer-finished updates. Speed,
ETA, and byte totals may be unavailable. Progress describes the current playlist
item or media stream, rather than an aggregate across the entire playlist. A job
stays downloading during post-processing and becomes complete only after yt-dlp
returns successfully and output exists. `output_name` is the last completed
media filename for a playlist. A failed playlist can retain successfully downloaded
items; its failure status remains visible.

Shutdown stops claiming work and interrupts active jobs at the next transfer or
post-processing hook. Extraction and FFmpeg may need time to reach that point.
Interrupted jobs return to queued; startup also requeues jobs left downloading by
a crash. Partial files and a per-job yt-dlp archive are retained: compatible partial
transfers resume and completed playlist items are skipped. Recovery requires the
same persistent download volume; source changes or servers without resume support
can cause a transfer to restart. Paused, failed, and completed jobs are not
requeued automatically. Pause/cancel/retry controls follow in milestone 5.

`GET /api/jobs/events` streams `event: jobs` messages containing a full
`JobsResponse`, with a durable revision as the event ID. Every connection receives
a current snapshot, including reconnections; intermediate transfer ticks are
coalesced. The feed checks for changes once per second and sends idle heartbeats
every 15 seconds. The React queue uses EventSource and reconnects automatically.
Reverse proxies should disable buffering for this endpoint.

Run queue, worker, API, and feed checks with
`python -m unittest api.tests.test_jobs`. Tests use controlled downloads and
temporary SQLite storage; a live media/FFmpeg and Docker restart smoke test remains
part of milestone 8.

## Frontend checks

From `web/`, run `npm run build` and `npm test`. On a new machine, install the test browser with `npx playwright install chromium`. Browser tests use controlled API responses to check playlist submissions, compatible format switching, validation errors, selection guards, and the mobile layout. They do not download live media.

If a preview reports YouTube verification or rate limiting, YouTube is restricting requests from the downloader server’s network. Wait before retrying. A valid URL does not guarantee access from the server; persistent verification may require server-side cookies (planned with the advanced authentication options). Preview extraction reports these errors instead of accepting incomplete metadata with no formats.
