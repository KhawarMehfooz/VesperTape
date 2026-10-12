# Updates and troubleshooting

[Documentation](README.md) · [Project overview](../README.md)

Before updating, stop the service and back up the application volume and host
download folder. Keep your private `.env` and any protected cookie file separately.
Pull the new code, then run `docker compose up --build -d` (include the cookie
override if configured). Dependency versions are pinned, so rebuilding alone does
not update yt-dlp. Update the lock file deliberately when a source change requires
a new extractor, and repeat the offline and live checks. Restore your matching
code/image and storage backup if reverting a database migration.

| Symptom | Check or action |
| --- | --- |
| Container does not start | Run `docker compose ps -a` and `docker compose logs --tail 100 vespertape storage-init`; check settings and volume permissions. |
| Browser cannot connect | Check the configured port and bind address, Docker status, and `/api/health`. |
| Settings return 404 or UI looks outdated | Rebuild/recreate the image and refresh the browser. |
| Preview or download fails | Check source availability and outbound access; verification/rate-limit errors may require waiting or refreshing protected host cookies. |
| Audio conversion or video merge fails locally | Install FFmpeg and Node 22+ on PATH; Docker includes both. |
| Files are absent from your computer's Downloads folder | Check the launcher's `.env` mapping and Docker Desktop folder sharing; files are written on the downloader host. |
| Resume/retry returns 409 | Wait for the current worker to stop and retry the action. |
| API file retrieval returns 404 | The recorded file may have been moved or deleted; history does not restore media. |
| Live progress stalls behind a reverse proxy | Disable buffering for `/api/jobs/events`; confirm same-origin routing and authentication. |

Avoid sharing logs or configuration containing credentials. Removing a job leaves
its downloaded files; deleting the application volume removes history, archives,
and partial transfers. Playlist progress reflects the current item/stream.
Unavailable sources, unsupported codec/container combinations, and provider
restrictions can still fail even when URL validation succeeds.

## Related guides

- [Setup and storage](setup.md)
- [Deployment](deployment.md)
- [Development and testing](development.md)
