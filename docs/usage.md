# Using VesperTape

[Documentation](README.md) · [Project overview](../README.md)

## Supported links and downloads

VesperTape accepts YouTube videos and playlists, including watch, youtu.be,
Shorts, live, embed, mobile, and music links. Channel pages and other sites are
not supported. A valid link does not guarantee that YouTube will make it
available from the downloader host.

1. Paste a link and choose **Preview**.
2. For a playlist, select all items, one item, or an inclusive range.
3. Choose audio or video, quality, format, and optional customization.
4. Choose **Add to downloads** and follow progress in the queue.

Single videos are saved in the configured download folder. Playlists use a
subfolder named after the playlist. Open downloaded files on the downloader
host; list rows do not open browser Save dialogs.

Playlist previews list up to 100 entries without checking every video’s formats.
Full-playlist downloads also include entries beyond this preview limit.
Availability and formats are checked during the download. Unavailable playlist
items are skipped with a warning; network, verification, format, and processing
errors still fail the job. The preview UI stops waiting after 30 seconds and
shows a timeout message.

## Download controls and history


The queue shows queued, downloading, and paused jobs; recent downloads shows
completed, canceled, and failed jobs, newest first. Jobs and completed file names
persist in SQLite and return through the live feed after a reload or restart.

Use Pause/Resume to preserve and continue partial downloads, Cancel to stop a job,
and Retry to requeue failed or canceled jobs with their original settings.
Interruption is cooperative: yt-dlp stops at its next progress or processing hook.
Resume, retry, and removal may briefly ask you to try again while a worker stops.
Pause/cancel cannot interrupt an FFmpeg operation already in progress immediately.

Remove deletes a terminal job from history and leaves its files on the download
volume. Queue and history use plain rows with 16:9 thumbnails. The active row
shows the currently downloading item; completed playlists list their downloaded
items. Rows do not open Save dialogs or link to files. Open files in the configured
host download folder. The API can still retrieve individual completed outputs.
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
  existing files are not added to the job’s recorded outputs. A job with everything
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

## Related guides

- [Setup and storage](setup.md)
- [Configuration](configuration.md)
- [Troubleshooting](troubleshooting.md)
