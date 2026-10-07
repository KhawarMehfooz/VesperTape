from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="VesperTape", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_dist / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str) -> FileResponse:
        requested = (web_dist / path).resolve()
        if requested.is_relative_to(web_dist) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(web_dist / "index.html")
