from __future__ import annotations

import hashlib
import json
import os
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class ChecksumMismatch(Exception):
    pass


class DownloadFailed(Exception):
    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"{name}: {reason}")
        self.name = name


class PortBusy(Exception):
    pass


class StudioHandle:
    def __init__(self, proc: object | None) -> None:
        self.proc = proc

    def close(self) -> None:
        if self.proc is not None:
            self.proc.terminate()


@dataclass(frozen=True)
class Pin:
    name: str
    system: str
    version: str
    url: str
    sha256: str
    member: str
    archive: str
    format: str

    @property
    def binary_name(self) -> str:
        return Path(self.member).name


def load_pins(path: Path | None = None) -> tuple[Pin, ...]:
    source = Path(__file__).with_name("pins.json") if path is None else path
    data = json.loads(source.read_text(encoding="utf-8"))
    return tuple(Pin(**item) for item in data["tools"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_tool(pin: Pin, directory: Path, fetch: Callable[[str], bytes]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"{pin.archive}-{pin.system}.{pin.format}"
    partial = directory / f"{pin.archive}-{pin.system}.partial"
    if partial.exists():
        partial.unlink()
    if not archive.exists() or sha256_file(archive) != pin.sha256:
        try:
            payload = fetch(pin.url)
        except OSError as exc:
            raise DownloadFailed(pin.name, str(exc)) from exc
        partial.write_bytes(payload)
        if sha256_file(partial) != pin.sha256:
            partial.unlink()
            raise ChecksumMismatch(pin.name)
        partial.replace(archive)
    binary = directory / pin.binary_name
    if not binary.exists():
        _extract(archive, pin.member, binary, pin.format)
    return binary


def _extract(archive: Path, member: str, dest: Path, kind: str) -> None:
    if kind == "zip":
        with zipfile.ZipFile(archive) as bundle:
            chosen = _match(bundle.namelist(), member)
            dest.write_bytes(bundle.read(chosen))
        return
    if kind == "tgz":
        with tarfile.open(archive, "r:gz") as bundle:
            names = bundle.getnames()
            chosen = _match(names, member)
            extracted = bundle.extractfile(chosen)
            if extracted is None:
                raise ChecksumMismatch(member)
            dest.write_bytes(extracted.read())
        return
    raise ChecksumMismatch(kind)


OLLAMA_PORT = 11435
MODEL_NAME = "qwen2.5:7b"


def start_studio(
    studio: Path,
    *,
    identify: Callable[[int], str],
    spawn: Callable[..., object],
    open_page: Callable[[], None],
    kill: Callable[[object], None] | None = None,
    config: Path | None = None,
    pins: tuple[Pin, ...] | None = None,
    fetch: Callable[[str], bytes] | None = None,
    system: str | None = None,
    list_models: Callable[[], list[str]] | None = None,
    pull_model: Callable[[str], None] | None = None,
    whisper_ready: Callable[[], bool] | None = None,
    fetch_whisper: Callable[[], None] | None = None,
) -> StudioHandle:
    del kill
    studio.mkdir(parents=True, exist_ok=True)
    if pins:
        for pin in pins:
            if system is not None and pin.system != system:
                continue
            ensure_tool(pin, studio / "bin", fetch)
    config_path = studio / "config.toml" if config is None else config
    if not config_path.exists():
        _write_config(config_path, studio)
    kind = identify(OLLAMA_PORT)
    if kind == "other":
        raise PortBusy(f"la porta {OLLAMA_PORT} non è Ollama")
    proc = None
    if kind == "free":
        binary = "ollama.exe" if os.name == "nt" else "ollama"
        proc = spawn(
            [str(studio / "bin" / binary), "serve"],
            {"OLLAMA_HOST": f"127.0.0.1:{OLLAMA_PORT}", "OLLAMA_MODELS": str(studio / "models")},
        )
    if list_models is not None and MODEL_NAME not in list_models():
        pull_model(MODEL_NAME)
    if whisper_ready is not None and not whisper_ready():
        fetch_whisper()
    open_page()
    return StudioHandle(proc)


def _write_config(path: Path, studio: Path) -> None:
    ffmpeg_path = studio / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    ffprobe_path = studio / "bin" / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
    ffmpeg = ffmpeg_path.as_posix() if ffmpeg_path.is_file() else "ffmpeg"
    ffprobe = ffprobe_path.as_posix() if ffprobe_path.is_file() else "ffprobe"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'ffmpeg = "{ffmpeg}"\nffprobe = "{ffprobe}"\nollama_url = "http://127.0.0.1:11435"\n',
        encoding="utf-8",
    )


def _match(names: list[str], member: str) -> str:
    for name in names:
        if name == member or name.endswith("/" + member):
            return name
    raise ChecksumMismatch(member)
