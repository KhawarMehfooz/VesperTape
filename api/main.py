from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

if __package__:
    from .contracts import ErrorResponse, HealthResponse, SettingsResponse
    from .settings import AppSettings
    from .database import Database
    from .errors import install_error_handlers
else:
    from contracts import ErrorResponse, HealthResponse, SettingsResponse
    from settings import AppSettings
    from database import Database
    from errors import install_error_handlers

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AppSettings.from_env()
    settings.prepare_directories()
    database = Database(settings.data_dir / "vespertape.sqlite3")
    database.initialize()
    app.state.settings = settings
    app.state.database = database
    yield


app = FastAPI(
    title="VesperTape", version="0.1.0", lifespan=lifespan,
    responses={code: {"model": ErrorResponse} for code in (404, 405, 422, 500)},
)
install_error_handlers(app)


@app.get("/api/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return app.state.settings.public_settings()


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
