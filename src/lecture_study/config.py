from __future__ import annotations

import ctypes
import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

DEFAULT_ROOT = Path.home() / "mba-studio"
DEFAULT_CONFIG = DEFAULT_ROOT / "config.toml"
AUDIO_EXTENSIONS = frozenset({
    ".wav", ".aiff", ".aif", ".caf",
    ".mp3",
    ".m4a", ".mp4", ".aac",
    ".3gp", ".3gpp", ".amr",
    ".ogg", ".opus", ".webm",
    ".flac",
})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DRIVE_REMOTE = 4


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    watch_dir: Path = DEFAULT_ROOT / "lezioni"
    library_dir: Path = DEFAULT_ROOT / "library"
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    highpass_hz: int = 80
    highpass_ratio_threshold: float = 1.0
    stable_seconds: int = 30
    scan_interval_seconds: int = 60
    whisper_model: str = "large-v3"
    ollama_url: str = "http://127.0.0.1:11435"
    ollama_model: str = "qwen2.5:7b"
    ollama_num_ctx: int = 16384
    ollama_timeout_seconds: int = 600
    retry_delays: tuple[int, ...] = (15, 30, 60, 120, 240)


def onedrive_roots() -> list[Path]:
    names = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")
    return [Path(os.environ[name]).resolve() for name in names if os.environ.get(name)]


def windows_drive_type(path: Path) -> int:
    anchor = path.anchor
    if anchor.startswith("\\\\"):
        return DRIVE_REMOTE
    return ctypes.windll.kernel32.GetDriveTypeW(anchor)


def check_local_dir(path: Path, *, roots: list[Path], drive_type: Callable[[Path], int]) -> None:
    resolved = path.resolve()
    for root in roots:
        if resolved == root or root in resolved.parents:
            raise ConfigError(f"{path} is inside OneDrive ({root})")
    if drive_type(resolved) == DRIVE_REMOTE:
        raise ConfigError(f"{path} is on a network drive")


def validate(
    settings: Settings,
    *,
    roots: list[Path] | None = None,
    drive_type: Callable[[Path], int] = windows_drive_type,
) -> None:
    roots = onedrive_roots() if roots is None else roots
    for path in (settings.watch_dir, settings.library_dir):
        check_local_dir(path, roots=roots, drive_type=drive_type)
    watch = settings.watch_dir.resolve()
    library = settings.library_dir.resolve()
    if library == watch or watch in library.parents:
        raise ConfigError("the library cannot be inside the watch folder")
    host = urlparse(settings.ollama_url).hostname
    if host not in LOOPBACK_HOSTS:
        raise ConfigError(f"ollama_url must point at this PC, not at {host}")
    numbers = (
        settings.highpass_hz,
        settings.highpass_ratio_threshold,
        settings.scan_interval_seconds,
        settings.ollama_num_ctx,
        settings.ollama_timeout_seconds,
    )
    if any(value <= 0 for value in numbers) or settings.stable_seconds < 0 or any(d < 0 for d in settings.retry_delays):
        raise ConfigError("numeric values are invalid")


def _convert(key: str, value: object, default: object) -> object:
    if isinstance(default, Path):
        if not isinstance(value, str):
            raise ConfigError(f"{key} must be a path")
        return Path(value)
    if isinstance(default, tuple):
        if not isinstance(value, list) or not all(type(item) is int for item in value):
            raise ConfigError(f"{key} must be a list of integers")
        return tuple(value)
    if isinstance(default, float) and type(value) is int:
        return float(value)
    if type(value) is not type(default):
        raise ConfigError(f"{key} must be of type {type(default).__name__}")
    return value


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    values: dict[str, object] = {}
    if path.exists():
        defaults = Settings()
        known = {field.name for field in fields(Settings)}
        for key, value in tomllib.loads(path.read_text(encoding="utf-8")).items():
            if key not in known:
                raise ConfigError(f"unknown setting: {key}")
            values[key] = _convert(key, value, getattr(defaults, key))
    settings = Settings(**values)
    validate(settings)
    return settings
