"""Validated host configuration, loaded once during application startup."""

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if __package__:
    from .contracts import (
        DownloadFormat, DownloadMode, DownloadQuality, DownloadSettings, ErrorDetail, SettingsResponse,
    )
    from .errors import ApiException
else:
    from contracts import (
        DownloadFormat, DownloadMode, DownloadQuality, DownloadSettings, ErrorDetail, SettingsResponse,
    )
    from errors import ApiException


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    data_dir: Path = Path("data")
    download_dir: Path | None = None
    cookie_file: Path | None = None
    worker_count: int = Field(default=1, ge=1, strict=True)
    allowed_modes: tuple[DownloadMode, ...] = get_args(DownloadMode)
    allowed_qualities: tuple[DownloadQuality, ...] = get_args(DownloadQuality)
    allowed_formats: tuple[DownloadFormat, ...] = get_args(DownloadFormat)

    @field_validator("data_dir", "download_dir", mode="before")
    @classmethod
    def normalize_path(cls, value):
        if value is None:
            return None
        if not str(value).strip():
            raise ValueError("Directory path cannot be empty")
        return Path(value).expanduser().resolve()

    @field_validator("cookie_file", mode="before")
    @classmethod
    def protected_cookie_file(cls, value):
        if value is None or value == "":
            return None
        path = Path(value).expanduser()
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ValueError("Cookie file must be an existing absolute regular file")
        if path.stat().st_mode & 0o007 or not os.access(path, os.R_OK):
            raise ValueError("Cookie file must be readable and inaccessible to other users")
        return path.resolve()

    @field_validator("allowed_modes", "allowed_qualities", "allowed_formats")
    @classmethod
    def validate_allowlist(cls, value):
        if not value:
            raise ValueError("Allowed options cannot be empty")
        if len(set(value)) != len(value):
            raise ValueError("Allowed options must be unique")
        return value

    @model_validator(mode="after")
    def resolve_download_dir(self):
        if self.download_dir is None:
            object.__setattr__(self, "download_dir", self.data_dir / "downloads")
        if self.download_dir == self.data_dir:
            raise ValueError("Download directory must differ from the application data directory")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppSettings":
        env = os.environ if environ is None else environ
        values = {}
        for name in cls.model_fields:
            key = f"VESPERTAPE_{name.upper()}"
            if key not in env:
                continue
            value = env[key]
            if name.startswith("allowed_"):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    raise ValueError(f"{key} must be a JSON array") from None
                if not isinstance(value, list):
                    raise ValueError(f"{key} must be a JSON array")
            elif name == "worker_count":
                try:
                    value = int(value)
                except ValueError:
                    raise ValueError(f"{key} must be an integer") from None
            values[name] = value
        return cls.model_validate(values)

    def prepare_directories(self) -> None:
        """Fail startup if configured storage cannot be created or written."""
        for directory in (self.data_dir, self.download_dir):
            directory.mkdir(parents=True, exist_ok=True)
            if not os.access(directory, os.W_OK | os.X_OK):
                raise ValueError("Configured storage directory is not writable")

    def public_settings(self) -> SettingsResponse:
        return SettingsResponse(
            defaults=DownloadSettings(
                mode=self.allowed_modes[0],
                quality=self.allowed_qualities[0],
                format=self.allowed_formats[0],
            ),
            allowed_modes=list(self.allowed_modes),
            allowed_qualities=list(self.allowed_qualities),
            allowed_formats=list(self.allowed_formats),
            destinations=["default"],
            worker_count=self.worker_count,
            cookie_file_available=self.cookie_file is not None,
        )

    def validate_download_settings(self, settings: DownloadSettings) -> None:
        details = []
        for field, allowed in (
            ("mode", self.allowed_modes),
            ("quality", self.allowed_qualities),
            ("format", self.allowed_formats),
        ):
            if getattr(settings, field) not in allowed:
                details.append(ErrorDetail(
                    location=["body", "settings", field],
                    code="option_not_allowed", message="Option is disabled by server configuration",
                ))
        if settings.use_cookie_file and self.cookie_file is None:
            details.append(ErrorDetail(location=["body", "settings", "use_cookie_file"],
                code="option_not_allowed", message="No cookie file is configured on the server"))
        for lower, upper in (("playlist_start", "playlist_end"), ("minimum_duration", "maximum_duration")):
            if getattr(settings, upper) is not None and getattr(settings, lower) is not None and getattr(settings, lower) > getattr(settings, upper):
                details.append(ErrorDetail(location=["body", "settings", upper], code="invalid_range", message="End must be at least the start"))
        if settings.filename and settings.output_template:
            details.append(ErrorDetail(location=["body", "settings", "output_template"], code="conflicting_options", message="Choose either a filename or an output template"))
        if settings.mode == "audio" and (settings.remux != "auto" or settings.embed_subtitles):
            details.append(ErrorDetail(location=["body", "settings", "mode"], code="conflicting_options", message="Remux and embedded subtitles require video mode"))
        if settings.proxy:
            if __package__:
                from .preview import validate_target
            else:
                from preview import validate_target
            validate_target(settings.proxy.replace("socks5://", "http://", 1))
        if details:
            raise ApiException(422, "validation_error", "Request validation failed", details)
