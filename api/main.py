import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

if __package__:
    from .security import AccessProtection
    from .contracts import ErrorResponse, HealthResponse, SettingsResponse, PreviewRequest, PreviewResponse, CreateJobRequest, JobResponse, JobsResponse, JobActionRequest
    from .settings import AppSettings
    from .database import Database
    from .preview import extract_preview, validate_target
    from .errors import install_error_handlers, ApiException
    from .jobs import JobStore
    from .worker import WorkerPool
else:
    from security import AccessProtection
    from contracts import ErrorResponse, HealthResponse, SettingsResponse, PreviewRequest, PreviewResponse, CreateJobRequest, JobResponse, JobsResponse, JobActionRequest
    from settings import AppSettings
    from database import Database
    from preview import extract_preview, validate_target
    from errors import install_error_handlers, ApiException
    from jobs import JobStore
    from worker import WorkerPool

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AppSettings.from_env()
    settings.prepare_directories()
    database = Database(settings.data_dir / "vespertape.sqlite3")
    database.initialize()
    app.state.settings = settings
    app.state.database = database
    app.state.jobs = JobStore(database)
    app.state.workers = WorkerPool(app.state.jobs, settings)
    app.state.workers.start()
    try:
        yield
    finally:
        await asyncio.to_thread(app.state.workers.stop)


app = FastAPI(
    title="VesperTape", version="0.1.0", lifespan=lifespan,
    responses={code: {"model": ErrorResponse} for code in (404, 405, 422, 500)},
)
install_error_handlers(app)
app.add_middleware(AccessProtection)


@app.get("/api/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return app.state.settings.public_settings()


@app.post("/api/preview", response_model=PreviewResponse)
def preview(request: PreviewRequest) -> PreviewResponse:
    return extract_preview(request.url, app.state.settings.cookie_file)


@app.post("/api/jobs", response_model=JobResponse, status_code=201)
def create_job(request: CreateJobRequest) -> JobResponse:
    # Resolve omitted nested settings against configured server defaults.
    defaults = app.state.settings.public_settings().defaults.model_dump()
    defaults.update(request.settings.model_dump(exclude_unset=True))
    request.settings = request.settings.model_validate(defaults)
    app.state.settings.validate_download_settings(request.settings)
    settings = request.settings
    audio_formats = {'auto', 'mp3', 'm4a', 'flac', 'wav'}
    video_formats = {'auto', 'mp4', 'webm'}
    if settings.format not in (audio_formats if settings.mode == 'audio' else video_formats):
        raise ApiException(422, 'validation_error', 'The format is incompatible with the selected mode')
    validate_target(request.url)
    return app.state.jobs.create(request)


@app.get("/api/jobs", response_model=JobsResponse)
def list_jobs() -> JobsResponse:
    return JobsResponse(jobs=app.state.jobs.snapshot()[1])


@app.get("/api/jobs/events", response_class=StreamingResponse,
         responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}})
async def job_events(request: Request):
    async def stream():
        revision = None
        heartbeat = 0
        while not await request.is_disconnected():
            current, jobs = await asyncio.to_thread(app.state.jobs.snapshot)
            if current != revision:
                yield f'id: {current}\nevent: jobs\ndata: {JobsResponse(jobs=jobs).model_dump_json()}\n\n'
                revision = current
                heartbeat = 0
            elif heartbeat >= 15:
                yield ': keepalive\n\n'
                heartbeat = 0
            heartbeat += 1
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
    })


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    return app.state.jobs.get(job_id)


@app.post("/api/jobs/{job_id}/actions", response_model=JobResponse)
def job_action(job_id: str, request: JobActionRequest) -> JobResponse:
    return app.state.workers.action(job_id, request.action)


@app.delete("/api/jobs/{job_id}", status_code=204)
def remove_job(job_id: str):
    app.state.workers.remove(job_id)
    return Response(status_code=204)


@app.get("/api/jobs/{job_id}/files/{filename}", response_class=FileResponse)
def completed_file(job_id: str, filename: str):
    job = app.state.jobs.get(job_id)
    if job.status != 'complete':
        raise ApiException(409, 'invalid_job_state', 'Files are available after the download completes')
    names = job.output_files or ([job.output_name] if job.output_name else [])
    root = app.state.settings.download_dir.resolve()
    directory = root if job.output_directory == 'root' else root / job.id
    if job.output_directory == 'root' and job.output_folder:
        if Path(job.output_folder).name != job.output_folder or job.output_folder in ('.', '..'):
            raise ApiException(404, 'not_found', 'Completed file not found')
        directory = root / job.output_folder
    path = directory / filename
    if (filename not in names or Path(filename).name != filename
            or directory.is_symlink() or path.is_symlink()
            or not path.resolve().is_relative_to(root)
            or not path.resolve().is_relative_to(directory.resolve()) or not path.is_file()):
        raise ApiException(404, 'not_found', 'Completed file not found')
    return FileResponse(path, filename=filename, media_type='application/octet-stream',
                        headers={'X-Content-Type-Options': 'nosniff'})


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_dist / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        requested = (web_dist / path).resolve()
        if requested.is_relative_to(web_dist) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(web_dist / "index.html")
