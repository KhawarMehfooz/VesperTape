"""Wire contracts shared with the web app via scripts/generate_api_types.py.

Times are UTC ISO-8601 strings; durations and ETA are seconds; sizes and
transfer rates use bytes and bytes/second. Null means unavailable.
"""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

DownloadMode = Literal["video", "audio"]
DownloadQuality = Literal["best", "1080p", "720p", "480p"]
DownloadFormat = Literal["auto", "mp4", "webm", "mp3", "m4a", "flac", "wav"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"


class UrlRequest(Contract):
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        try:
            parsed = urlsplit(value)
            parsed.port  # Access validates malformed ports.
        except ValueError:
            raise ValueError("Provide a valid HTTP or HTTPS URL") from None
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Provide a valid HTTP or HTTPS URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL credentials are not supported")
        if any(character.isspace() or ord(character) < 32 for character in value) or "\\" in value:
            raise ValueError("Provide a valid HTTP or HTTPS URL")
        return value


class PreviewRequest(UrlRequest):
    pass


class MediaFormat(Contract):
    id: str
    extension: str
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    filesize_bytes: int | None = Field(default=None, ge=0)


class PreviewItem(Contract):
    id: str
    url: str
    title: str
    uploader: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    playlist_index: int | None = Field(default=None, ge=1)
    formats: list[MediaFormat] = Field(default_factory=list)


class PreviewResponse(Contract):
    source_url: str
    kind: Literal["video", "playlist"]
    title: str
    items: list[PreviewItem]
    total_items: int | None = Field(default=None, ge=0)


class PlaylistSelection(Contract):
    """Inclusive, one-based indexes; an empty list selects the full playlist."""

    item_indices: list[Annotated[int, Field(strict=True, ge=1)]] = Field(default_factory=list)

    @field_validator("item_indices")
    @classmethod
    def unique_indices(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Playlist indexes must be unique")
        return value


class DownloadSettings(Contract):
    mode: DownloadMode = "video"
    quality: DownloadQuality = "best"
    format: DownloadFormat = "auto"
    destination: str = "default"
    filename: str | None = None

    @field_validator("destination")
    @classmethod
    def known_destination(cls, value: str) -> str:
        if value != "default":
            raise ValueError("Unknown download destination")
        return value

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or value in (".", "..") or len(value.encode("utf-8")) > 200:
            raise ValueError("Provide a filename of at most 200 UTF-8 bytes")
        if any(character in '/\\<>:"|?*%' or ord(character) < 32 for character in value):
            raise ValueError("Filename contains unsupported characters")
        return value


class SettingsResponse(Contract):
    """Public capabilities; filesystem paths and secrets are not exposed."""

    defaults: DownloadSettings
    allowed_modes: list[Literal["video", "audio"]]
    allowed_qualities: list[str]
    allowed_formats: list[str]
    destinations: list[str]
    worker_count: int = Field(ge=1)


class CreateJobRequest(UrlRequest):
    selection: PlaylistSelection = Field(default_factory=PlaylistSelection)
    settings: DownloadSettings = Field(default_factory=DownloadSettings)


class ErrorDetail(Contract):
    location: list[str | int] = Field(default_factory=list)
    message: str
    code: str


class ApiError(Contract):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(Contract):
    error: ApiError


class JobProgress(Contract):
    downloaded_bytes: int = Field(default=0, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)
    percent: float | None = Field(default=None, ge=0, le=100)
    speed_bytes_per_second: float | None = Field(default=None, ge=0)
    eta_seconds: float | None = Field(default=None, ge=0)


class JobResponse(Contract):
    id: str
    source_url: str
    title: str | None = None
    status: Literal["queued", "downloading", "paused", "complete", "canceled", "failed"]
    selection: PlaylistSelection
    settings: DownloadSettings
    progress: JobProgress
    output_name: str | None = None
    error: ApiError | None = None
    created_at: str
    updated_at: str


class JobsResponse(Contract):
    jobs: list[JobResponse]


class JobActionRequest(Contract):
    action: Literal["pause", "resume", "cancel", "retry"]
