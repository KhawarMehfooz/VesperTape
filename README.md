# VesperTape

A self-hosted YouTube video downloader with a React interface and a Python service powered by yt-dlp.

## Development

Run the complete app in Docker with automatic local download storage:

```sh
# macOS / Linux
python3 scripts/start.py
```

```powershell
# Windows (Python 3)
py scripts/start.py
```

The launcher locates your OS Downloads folder and creates a `VesperTape`
subfolder. Windows uses the system's known Downloads folder (including redirected
folders); Linux uses the XDG Downloads location when configured; macOS uses
`~/Downloads`. Completed files are saved directly in that folder. Downloads appear there automatically,
without clicking a browser Save link. Docker must run on the same computer.

The mapping is saved in the ignored `.env` file, preserving other settings.
Later `docker compose up --build -d` commands reuse it. To choose another folder,
run `python3 scripts/start.py --downloads "/path/to/folder"` (use `py` on Windows).
`--configure-only` writes the mapping without starting Docker. Python 3.9+ and
Docker Compose are required. Docker Desktop must allow access to the chosen folder.

Without running the launcher, Compose defaults to the project's `downloads/` folder.
On Linux, use the launcher to configure your UID/GID so downloaded files belong to
your user. A short-lived root storage initializer prepares volume permissions;
the API and workers run as the configured non-root user.

On first startup with a new mapped folder, existing files from the old Docker
volume's `/data/downloads` are copied there without overwriting existing files.
The old files and job database are preserved. The launcher stops the old worker
before migration; queued work resumes after startup.

The API is available at `http://localhost:8000`. Set `VESPERTAPE_API_PORT` to change the host port. Compose stores application data in the `vespertape-data` volume.

After API code changes, rerun `docker compose up --build -d`; Compose does not mount the source code. If the UI cannot load download settings, check `http://localhost:8000/api/settings`. A 404 can indicate an older container image; rebuild it and use Retry settings or refresh the page.

The container serves the built React app at the same URL. For frontend development,
run the React app locally in a second terminal:

```sh
cd web
npm ci
npm run dev
```

Open the Vite URL it prints, usually `http://localhost:5173`. Vite proxies `/api` requests to the Docker API on port 8000.

The app supports link previews, playlist selection, and a live persistent download queue.
The Classic Download Window layout (variant A of the design study) supports previewing a link, selecting playlist items, and adding audio or video downloads. Controls use server defaults and allowed options. Choose quality, format, a configured server destination, and an optional file name; API validation errors appear beside the submission controls. The app uses the static study’s original Classic Window markup, CSS, icons, panels, and responsive rules, with simplified VesperTape branding. Advanced options support subtitles, metadata, thumbnails, chapters, remuxing, playlist filters, archives, output templates, and network settings. The layout stacks at 700px and uses single-column settings at 410px.

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
| `VESPERTAPE_DOWNLOAD_DIR` | `<data directory>/downloads` locally; `/downloads` in Compose | Download storage inside the API host/container |
| `VESPERTAPE_HOST_DOWNLOAD_DIR` | `./downloads` before launcher setup | Compose bind-mount source on your computer; launcher selects Downloads/VesperTape |
| `VESPERTAPE_UID` / `VESPERTAPE_GID` | `10001` | Compose runtime user/group; launcher uses your Linux UID/GID |
| `VESPERTAPE_ACCESS_PASSWORD` | Unset | Optional single-user password (minimum 16 characters); username `vespertape` |
| `VESPERTAPE_BIND_ADDRESS` | `127.0.0.1` | Compose host interface for the published port |
| `VESPERTAPE_WORKER_COUNT` | `1` | Positive integer; concurrent downloads (default: one) |
| `VESPERTAPE_ALLOWED_MODES` | `["video","audio"]` | JSON array of allowed modes |
| `VESPERTAPE_ALLOWED_QUALITIES` | `["best","1080p","720p","480p"]` | JSON array of allowed qualities |
| `VESPERTAPE_ALLOWED_FORMATS` | `["auto","mp4","webm","mp3","m4a","flac","wav"]` | JSON array of allowed formats |

Option arrays must be nonempty, unique, and use the supported values above.
Their first entries become public defaults. `GET /api/settings` exposes these
defaults, allowed values, worker count, and the `default` destination name.
Directory paths stay on the server; paths are resolved relative to the API's
working directory and created on startup. Use distinct data and download paths.
Compose downloads persist in the configured host bind mount; application data
persists separately in the `/data` named volume.
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
and a working CA certificate bundle; previews use the protected server cookie file when configured.

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
instance from resetting active work during startup. Each job keeps partial files and its archive internally under
`<data directory>/work/<job ID>/`. Completed files are placed directly in the
configured download folder. Duplicate filenames receive numbered suffixes,
such as `video (1).mp4`, without overwriting existing files. On startup, earlier
job folders are moved into internal storage and completed downloads are placed
in the main download folder; existing history links are updated. Audio conversion and video merging/remuxing require FFmpeg,
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
requeued automatically. Pause/cancel/retry controls are available in the download queue.

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

If a preview reports YouTube verification or rate limiting, YouTube is restricting requests from the downloader server’s network. Wait before retrying. A valid URL does not guarantee access from the server; persistent verification may require the protected server-side cookie file described below. Preview extraction reports these errors instead of accepting incomplete metadata with no formats.

### Download controls and history

The queue shows queued, downloading, and paused jobs; recent downloads shows
completed, canceled, and failed jobs, newest first. Jobs and completed file names
persist in SQLite and return through the live feed after a reload or restart.

Use Pause/Resume to preserve and continue partial downloads, Cancel to stop a job,
and Retry to requeue failed or canceled jobs with their original settings.
Interruption is cooperative: yt-dlp stops at its next progress or processing hook.
Resume, retry, and removal may briefly ask you to try again while a worker stops.
Pause/cancel cannot interrupt an FFmpeg operation already in progress immediately.

Remove deletes a terminal job from history and leaves its files on the download
volume. Save links retrieve completed files, including individual playlist outputs.
Missing or moved files return 404. File retrieval only serves recorded completed
outputs under the configured volume and rejects symlinks and path traversal.

API controls: `POST /api/jobs/{id}/actions` with an `action` of `pause`, `resume`,
`cancel`, or `retry`; `DELETE /api/jobs/{id}` removes a terminal job;
`GET /api/jobs/{id}/files/{filename}` retrieves a completed output.
Invalid state transitions return 409 and unknown jobs return 404.


## Advanced options

Expand **More ways to customize** before adding a download. Settings persist with
that job and are reused on retry. Existing jobs receive backward-compatible defaults.

- Download uploaded subtitles and/or automatic captions, choose comma-separated
  language codes (or `all`), convert to SRT/VTT/ASS, and embed subtitles in video.
  Embedding does not automatically enable subtitle downloading; select both.
- Embed metadata, thumbnail images, or chapter markers; save thumbnails separately;
  split chapters into additional files; or remux video to MP4, MKV, or WebM.
  These operations require FFmpeg and source metadata. Container support varies;
  an incompatible choice can fail during post-processing. Remux overrides the
  video container control and does not re-encode incompatible codecs.
- Filter the selected playlist using inclusive start/end indexes and minimum/maximum
  duration in seconds. Blank optional limits mean no limit. Items without a known
  duration do not match duration filters. A range excluding every explicitly
  selected index fails rather than downloading the full playlist.
- Enable the shared download archive to skip previously archived media IDs.
  The archive lives in the persistent data directory and applies only to
  archive-enabled jobs. It is updated after a successful job, including file-rule
  skips. It is independent of history removal and does not check whether old
  files still exist. Concurrent jobs may both download an item before either
  commits its archive; keep one worker to avoid that overlap. Every job also keeps
  its own recovery archive so resume/retry can skip already completed items.
- Set a filename stem template using `%(title)s`, `%(id)s`, `%(uploader)s`, or
  `%(playlist_index)03d`; title truncation such as `%(title).120B` is supported.
  Paths, arbitrary fields, and extension substitutions are rejected. The worker
  adds media ID, playlist index, and the output extension, sanitizes filenames,
  and limits their length. Choose either a custom filename or a template.
- Choose `rename` (default, numbered suffix), `skip` (preserve the existing file),
  or `fail` for destination conflicts. Files are never overwritten. Skipped
  existing files do not receive new history download links. A job with everything
  skipped by archive, duration filters, or file rules completes with no new files.
  A failed job can leave already published files; retries apply the same rules.
- Set 0–20 transfer/fragment retries, a rate limit in bytes per second (blank for
  unlimited), and 1–16 concurrent fragments. HTTP/HTTPS/SOCKS5 proxies must resolve
  to public addresses and cannot contain credentials. Public-network checks still
  apply to extracted URLs; a proxy changes where requests are sent, so use a
  trusted proxy. These network settings apply to downloads, not previews.
- Supply one HTTP header per line. The allowlist accepts `User-Agent`, `Referer`,
  `Origin`, and `Accept-Language`; duplicate names and control characters are
  rejected. Authentication headers and cookie contents are not accepted. These
  header values and proxy URLs are persisted in job settings, so do not put
  credentials in them.

Custom yt-dlp options are restricted to `--prefer-free-formats`, `--no-playlist`,
`--playlist-reverse`, and `--check-formats`. The API accepts these exact strings
in `settings.custom_options` and rejects all other options before creating a job.
The UI exposes the same allowlist. No arbitrary command, filesystem path,
postprocessor, or raw command-line parsing is exposed.

### Protected server cookies

Export a Netscape-format cookie file on the downloader host. Browser cookies must
be available on that host; they do **not** come from the user's device or browser
session automatically. Browser-profile extraction and cookie uploads are not
supported. Keep the file outside this repository and the download volume.

For Docker, set `VESPERTAPE_HOST_COOKIE_FILE` in the ignored `.env` to its absolute
host path, then use the optional read-only mount:

```sh
docker compose -f docker-compose.yml -f docker-compose.cookies.yml up --build -d
```

Ensure the container's configured UID/GID can read it. On Linux, use a file owned
by that UID with mode `600`, or a restricted matching group with mode `640`.
The file must not be accessible to other users; mode `644` is rejected. Docker
Desktop may require sharing its host folder. The override does not create a
missing cookie file or change its permissions. Use both Compose files in later
startup/rebuild commands to keep cookies enabled.

For local API execution, export `VESPERTAPE_COOKIE_FILE=/absolute/path/cookies.txt`.
Startup verifies a readable regular file with no permissions for other users and
rejects a symlink. The API exposes only whether a file is configured, never its
path or contents. Previews use it automatically; jobs use it when **Use server
cookie file** is checked. yt-dlp receives a temporary private copy, deleted after
extraction, so the original read-only file is never modified. Refresh exported
cookies on the host when they expire; authentication does not guarantee YouTube
will accept the downloader's network.

The mappings use yt-dlp's [documented Python options](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py)
and [post-processing options](https://github.com/yt-dlp/yt-dlp#post-processing-options).


## Security and deployment

Compose binds to `127.0.0.1` by default. Open `http://localhost:8000` for the
complete app. Downloads persist in the configured host folder and queue state,
partial files, and archives persist in the `vespertape-data` named volume.
Rebuilding or recreating the container preserves both. `docker compose down -v`
deletes the application volume, including queue history and partial downloads.

For single-user access protection, set `VESPERTAPE_ACCESS_PASSWORD` in the ignored
`.env` file to a unique password of at least 16 characters, then rebuild/recreate
the service. Use username `vespertape` in the browser's sign-in dialog. An empty
password disables authentication. All app routes, assets, API documentation,
file links, and the live feed require authentication; `/api/health` remains public
and returns only service status. Password values are hidden in configuration
representations and never returned by public settings. Keep `.env` private
(`chmod 600 .env` on macOS/Linux). Compose interpolation treats `$` specially;
use a single-quoted value in `.env` when the password contains dollar signs.

To allow connections from a trusted network, set `VESPERTAPE_BIND_ADDRESS` to a
specific host interface or `0.0.0.0`. For access beyond that network, enable the
password and put the service behind an HTTPS reverse proxy. Basic authentication
requires HTTPS to protect credentials in transit. Preserve the original `Host`
header and forward the HTTPS scheme using `X-Forwarded-Proto`; configure Uvicorn's
`--forwarded-allow-ips` for the trusted proxy address only. Browser mutations must
come from the same origin; cross-origin requests are rejected. Disable proxy
buffering for `/api/jobs/events`. Use the bundled same-origin UI for protected
deployments. Browser credentials remain cached until the browser session ends;
there is no application logout button. Changing the password and recreating the
container revokes the old credentials.

The service runs as UID/GID `10001` by default, with all Linux capabilities
dropped and privilege escalation disabled. The separate root storage initializer
only migrates old files and assigns ownership of the dedicated storage locations.
On Linux, run the launcher to use your own UID/GID, or configure
`VESPERTAPE_UID` and `VESPERTAPE_GID`; both storage mounts must be writable by
that identity. Use a dedicated download folder because initialization recursively
assigns its ownership. Cookie mounts remain read-only and must be readable by
the runtime identity. Do not share writable application storage with untrusted
users. Output filenames and templates cannot select paths; job storage rejects
symlinked directories and file links reject traversal and symlinks.

Docker probes `/api/health` every 30 seconds (with an initial 15-second grace
period). Check status with `docker compose ps`. An unhealthy status is diagnostic;
Docker's restart policy restarts exited processes, not merely unhealthy ones.
Compose forwards signals through an init process and allows two minutes for
shutdown. Uvicorn allows 20 seconds for open HTTP requests and live feeds before
canceling them and beginning worker shutdown. Workers stop claiming jobs and
requeue interrupted active work at the next download or processing hook. If extraction or FFmpeg exceeds that window,
Docker kills the process; startup recovers jobs left downloading from SQLite and
uses their retained partial files and per-job archives. Run only one API process
per data volume. Paused and terminal jobs retain their state.

Container commands disable request access logs so URL queries and file names
are not logged. Preview/worker loggers discard yt-dlp messages; public errors and
unhandled request failures omit raw exception text, submitted values, cookie
contents, and headers. For local API execution, also pass `--no-access-log` to
Uvicorn. Reverse-proxy logs should omit authorization headers, cookies, and
sensitive query strings. Existing public-network checks remain best effort; use
network egress restrictions when accepting untrusted users.

Run milestone 7 checks with `python -m unittest api.tests.test_security api.tests.test_jobs api.tests.test_errors`.
