# Security and deployment

[Documentation](README.md) · [Project overview](../README.md)

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

Run security checks with `python -m unittest api.tests.test_security api.tests.test_jobs api.tests.test_errors`.

## Related guides

- [Configuration](configuration.md)
- [Protected server cookies](usage.md#protected-server-cookies)
- [Updates and troubleshooting](troubleshooting.md)
