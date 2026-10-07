# Development and testing

[Documentation](README.md) · [Project overview](../README.md)

Commands in this guide start at the repository root unless a command changes
directory.

## Local API

Local execution requires FFmpeg and Node 22+ on PATH. Docker includes both.

Run these commands from the repository root:

```sh
cd api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
uvicorn main:app --reload --port 8000 --no-access-log
```

`web/package-lock.json` pins the frontend dependencies. `api/requirements.lock` pins the Python dependencies used by Docker and pip.

## Frontend development

Run the API in Docker or locally, then start the frontend in another terminal:

```sh
cd web
npm ci
npm run dev
```

Open the Vite URL it prints, usually `http://localhost:5173`. Vite proxies `/api`
to port 8000 and preserves the browser-facing Host for the API’s same-origin
checks. If you change the API port, update `web/vite.config.ts` accordingly.

After changing API code used by Docker, run `docker compose up --build -d`;
the container does not mount the source code.


## Frontend structure

`web/src/App.tsx` composes the app window, download form, and job lists.

| Location | Responsibility |
| --- | --- |
| `src/api/client.ts` | HTTP requests, public API errors, and the jobs event feed |
| `src/api/contracts.ts` | Generated API types; regenerate instead of editing |
| `src/hooks/` | Preview cancellation and selection, settings, submissions, job state, and transient messages |
| `src/components/preview/` | Link input, preview card, and playlist controls |
| `src/components/settings/` | Output settings, save settings, folder picker, and advanced options |
| `src/components/downloads/` | Active jobs, history, downloaded items, and job actions |
| `src/components/forms/` | Shared typed input fields and submission errors |
| `src/utils/` | Format compatibility, labels, thumbnail lookup, and playlist ordering |
| `src/styles/theme.css` | App styles and responsive rules |

Use `npm run format` from `web/` to format frontend source and configuration.
`npm run format:check` checks formatting without changing files. Generated API
contracts are excluded so the Python generator remains their sole owner.

## Frontend checks

From `web/`, run `npm run build` and `npm test`. On a new machine, install the test browser with `npx playwright install chromium`. Browser tests use controlled API responses to check playlist submissions, compatible format switching, validation errors, selection guards, and the mobile layout. They do not download live media.

If a preview reports YouTube verification or rate limiting, YouTube is restricting requests from the downloader server’s network. Wait before retrying. A valid URL does not guarantee access from the server; persistent verification may require the protected server-side cookie file described in [Using VesperTape](usage.md#protected-server-cookies). Preview extraction reports these errors instead of accepting incomplete metadata with no formats.

## Verification and live smoke check

Run the offline checks from the repository root using an environment with the
locked API dependencies installed:

```sh
python -m unittest discover -s api/tests -t .
python -m scripts.generate_api_types --check
cd web
npm ci
npx playwright install chromium
npm run build
npm test
```

Alternatively, test the current Python source using the Compose image without
installing Python dependencies locally (macOS/Linux):

```sh
docker compose build vespertape
docker run --rm -v "$PWD:/app:ro" --entrypoint python vespertape-vespertape \
  -m unittest discover -s api/tests -t .
```

The default image name assumes the project is named `vespertape`; use your image
name if you set a custom Compose project name. Mounting the repository includes
the contract generator and launcher, which are absent from the runtime image.
Offline tests use temporary storage and controlled extractor/API responses.
They cover preview errors, request validation, FIFO queue claims, job controls,
file access, worker interruption, recovery, and the browser submission flow.

For a real network and FFmpeg check, run:

```sh
python3 scripts/smoke_downloads.py --url 'https://www.youtube.com/watch?v=jNQXAC9IVRw'
```

Use a short public video you are permitted to download. The script builds the
current project, starts a separate Compose project on a random localhost port,
and uses its own temporary named volume. It previews the video, downloads MP4
and MP3 with metadata post-processing, checks their streams with FFprobe, and
retrieves their files through the API. During the video transfer it kills and
starts the container to exercise partial-transfer recovery. A final restart checks
that completed history and downloadable files persist. It removes its own
container, network, and volume on exit. Your normal Compose service and storage
are unaffected. Internet access and source availability are required; the check
does not mount server cookies. `--timeout 600` increases the per-download limit;
`--image IMAGE` reuses an already built image. Transfers are limited to 128 KiB/s
to make the recovery checkpoint observable; very short or tiny videos can finish
before that checkpoint and should be replaced with a longer source.

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

## Related guides

- [API reference](api.md)
- [Configuration](configuration.md)
- [Setup and storage](setup.md)
