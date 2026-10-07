# VesperTape implementation plan

## Progress tracker

Update milestone status and task checkboxes as work is completed.

| Milestone | Status |
| --- | --- |
| 0. Project scaffold | Done |
| 1. API and configuration | Done |
| 2. Link preview | Done |
| 3. Persistent queue and worker | Done |
| 4. Core download UI | Done |
| 5. Download controls and history | Done |
| 6. Advanced options | Not started |
| 7. Security and deployment | Not started |
| 8. Final checks and documentation | Not started |

## 0. Project scaffold

- [x] Create `web/` React and TypeScript app.
- [x] Create `api/` FastAPI app with a health endpoint.
- [x] Add one Dockerfile and one Compose service.
- [x] Add starter screen based on the design study.
- [x] Ignore `vespertape-ui-design-system.html` in Git.
- [x] Pin frontend and Python dependencies with lock files.
- [x] Build and launch the container; confirm the API health endpoint works.

## 1. API and configuration

- [x] Define shared API response and request shapes for previews, settings, jobs, and errors.
- [x] Add typed application settings for data paths, download paths, worker count, and allowed options.
- [x] Add SQLite connection and migration strategy.
- [x] Add consistent error responses and request validation.

## 2. Link preview

- [x] Add `POST /api/preview` using yt-dlp metadata extraction without downloading media.
- [x] Return title, uploader, thumbnail, duration, formats, and playlist information.
- [x] Support choosing one item, the full playlist, or a playlist range.
- [x] Show loading, unsupported link, private link, and no-format states in the UI.
- [x] Validate URL scheme and reject local or private network targets where possible.

## 3. Persistent queue and worker

- [x] Store download jobs and status in SQLite.
- [x] Add `POST /api/jobs` to validate settings and enqueue a job.
- [x] Run one download at a time by default in a background worker.
- [x] Persist progress, speed, estimated time, output name, and failure details.
- [x] Resume queued or interrupted work safely after an app restart.
- [x] Send live job updates to the UI using Server-Sent Events.

## 4. Core download UI

- [x] Choose the final layout variant from the design study.
- [x] Match the selected layout to the design tokens and responsive breakpoints.
- [x] Connect URL preview and playlist selection to the API.
- [x] Add audio/video mode, quality, format, destination, and optional file name controls.
- [x] Connect Add to Downloads to job creation and display API validation errors.

## 5. Download controls and history

- [x] Show queued, downloading, paused, complete, canceled, and failed jobs.
- [x] Add pause/resume, cancel, retry, and remove actions.
- [x] Show progress, transfer speed, and estimated time when yt-dlp provides them.
- [x] Persist and display recent completed downloads.
- [x] Add a safe endpoint to retrieve completed files from the configured download volume.

## 6. Advanced options

- [ ] Add subtitles, metadata, thumbnail, chapters, and remux settings.
- [ ] Add archive behavior, playlist filters, output templates, and file conflict rules.
- [ ] Add retry count, rate limit, fragment concurrency, proxy, and HTTP headers.
- [ ] Add cookie-file configuration using a protected path mounted into the container.
- [ ] Validate custom yt-dlp options against an allowlist before enqueueing jobs.
- [ ] Document that browser cookies must be available on the downloader host; they do not come from the user's device.

## 7. Security and deployment

- [ ] Keep downloads and application data in persistent Docker volumes.
- [ ] Restrict output paths to configured directories and prevent path traversal.
- [ ] Avoid logging cookie data, credentials, or sensitive request headers.
- [ ] Add optional single-user access protection before exposing the service beyond a trusted network.
- [ ] Add health checks, graceful shutdown, and recovery for active jobs.
- [ ] Confirm the container runs as a non-root user and document volume permissions.

## 8. Final checks and documentation

- [ ] Add API tests for preview, validation, queue state, and job actions.
- [ ] Add frontend checks for the main flow and job states.
- [ ] Verify a real video and audio download, including FFmpeg post-processing.
- [ ] Verify restart recovery and persistent files with Docker Compose.
- [ ] Document setup, configuration, supported behavior, updates, and troubleshooting.
