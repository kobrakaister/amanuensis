from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lecture_study.atomic import read_json, write_json_atomic
from lecture_study.config import AUDIO_EXTENSIONS


@dataclass(frozen=True)
class Recording:
    path: Path
    size: int
    mtime_ns: int


def find_stable_recordings(watch_dir: Path, *, stable_seconds: int, now: float) -> list[Recording]:
    found = []
    for path in watch_dir.rglob("*"):
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        try:
            if not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        if now - stat.st_mtime >= stable_seconds:
            found.append(Recording(path, stat.st_size, stat.st_mtime_ns))
    return sorted(found, key=lambda recording: (recording.mtime_ns, str(recording.path)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class HashIndex:
    def __init__(self, path: Path, hasher: Callable[[Path], str] = sha256_file) -> None:
        self.path = path
        self._hasher = hasher
        self._entries: dict[str, dict] = read_json(path) if path.exists() else {}

    def hash_of(self, recording: Recording) -> str:
        key = str(recording.path)
        entry = self._entries.get(key)
        if entry and entry["size"] == recording.size and entry["mtime_ns"] == recording.mtime_ns:
            return entry["sha256"]
        digest = self._hasher(recording.path)
        self._entries[key] = {"size": recording.size, "mtime_ns": recording.mtime_ns, "sha256": digest}
        return digest

    def save(self) -> None:
        write_json_atomic(self.path, self._entries)
