# API reference

[Documentation](README.md) · [Project overview](../README.md)

## Contracts

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
names, not client-supplied filesystem paths. Job responses include `thumbnail_url` for the current item and
`downloaded_items` with each completed item’s title, filename, and thumbnail.
`output_folder` names the playlist subfolder when one is used; `output_files`
contains filenames within the recorded output location.

## Errors and validation

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

Playlist previews list metadata for at most 100 entries without extracting each
video’s formats. Items with `formats_checked: false` have not had availability or
formats verified; the download worker checks those when processing the selection.
Individual video previews still extract formats. The browser stops waiting after
30 seconds and shows a timeout message; server extraction may finish afterward. Full
playlist selection uses an empty `item_indices` list, while one-item and inclusive
range selections use the original one-based playlist indexes visible in the
preview. The full selection also includes entries beyond the preview limit. Add to Downloads submits the current selection and settings to the job API. Private or unavailable entries may be omitted by YouTube from the playlist listing;
availability can still fail during download. Requests have a 15-second socket timeout and limited retries, but large
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
`<data directory>/work/<job ID>/`. Single-video files are placed in the configured download folder; playlist files
are grouped under a subfolder named after the playlist. Unsafe folder characters
are replaced, names are length-limited, and symlink destinations are rejected. Duplicate filenames receive numbered suffixes,
such as `video (1).mp4`, without overwriting existing files. On startup, earlier
job folders are moved into internal storage and completed downloads are placed
in the configured download folder. Completed playlists previously saved at its
root are grouped into their named folders on startup; file records are updated. Audio conversion and video merging/remuxing require FFmpeg,
which is installed in Docker. Local API execution needs FFmpeg and Node 22 or newer on PATH. Previews and workers explicitly enable Node for YouTube’s JavaScript challenges; the pinned `yt-dlp-ejs` dependency supplies the solver scripts. See the [yt-dlp EJS setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

Progress is saved at most twice per second, plus transfer-finished updates. Speed,
ETA, and byte totals may be unavailable. Progress describes the current playlist
item or media stream, rather than an aggregate across the entire playlist. A job
stays downloading during post-processing and becomes complete only after yt-dlp
returns successfully and output exists. `output_name` is the last completed
media filename for a playlist. Unavailable playlist items are skipped so later selected entries can download.
Completed jobs show a warning with the skipped count. Network, verification,
format, and post-processing errors still fail the job; successfully downloaded
items and the per-job archive are retained for retry. A playlist with no completed
output fails unless archive or duration-filter rules explain the empty result.

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
temporary SQLite storage. See [Development and testing](development.md) for the
live media, FFmpeg, and Docker restart smoke check.

## Related guides

- [Configuration](configuration.md)
- [Development and testing](development.md)
- [Deployment](deployment.md)
