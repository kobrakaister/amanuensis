from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable

from lecture_study.config import DEFAULT_CONFIG, DEFAULT_ROOT, ConfigError, Settings, load_settings
from lecture_study.llm import OllamaClient
from lecture_study.page import (
    PAGE_HOST,
    PAGE_PORT,
    PageAddressError,
    PortTaken,
    StudyHandler,
    bind_page,
    chosen_recordings,
)
from lecture_study.pipeline import Pipeline
from lecture_study.scanner import HashIndex, Recording, find_stable_recordings
from lecture_study.studio import ChecksumMismatch, DownloadFailed, PortBusy, start_studio
from lecture_study.transcribe import FasterWhisperTranscriber

PAGE_URL = f"http://{PAGE_HOST}:{PAGE_PORT}/"

log = logging.getLogger("lecture_study")


def build_pipeline(settings: Settings) -> Pipeline:
    model = OllamaClient(
        settings.ollama_url,
        settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    return Pipeline(settings, transcriber=FasterWhisperTranscriber(settings.whisper_model), model=model)


def scan_once(settings: Settings, pipeline: Pipeline, index: HashIndex, *, now: Callable[[], float] = time.time) -> int:
    processed = 0
    for recording in find_stable_recordings(settings.watch_dir, stable_seconds=settings.stable_seconds, now=now()):
        try:
            sha256 = index.hash_of(recording)
        except OSError as exc:
            log.warning("impossibile leggere %s: %s", recording.path, exc)
            continue
        index.save()
        pipeline.process(recording, sha256)
        processed += 1
    return processed


def configure_logging(library_dir: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(library_dir / "lecture-study.log", encoding="utf-8"), logging.StreamHandler()],
    )


def identify_port(port: int) -> str:
    if port != 11435:
        raise RuntimeError(f"porta non prevista: {port}")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            connected = True
    except OSError:
        connected = False
    if not connected:
        return "free"
    try:
        with urllib.request.urlopen("http://127.0.0.1:11435/api/version", timeout=0.5) as response:
            if response.status == 200:
                return "ollama"
    except (OSError, urllib.error.URLError):
        return "other"
    return "other"


def spawn_ollama(args: list[str], env: dict[str, str]) -> subprocess.Popen:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.Popen(args, env=merged)


def run_up(
    *,
    studio: Path,
    config: Path,
    identify: Callable[[int], str],
    spawn: Callable[..., object],
    browser: Callable[[str], object],
    selected: Path | None = None,
    cycles: int | None = None,
    process: Callable[[Path], None] | None = None,
    now: Callable[[], float] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    list_models: Callable[[], list[str]] | None = None,
    pull_model: Callable[[str], None] | None = None,
    whisper_ready: Callable[[], bool] | None = None,
    fetch_whisper: Callable[[], None] | None = None,
) -> int:
    hold = studio / "hold.json"
    if config.exists():
        _publish_page(load_settings(config), hold, config)
    try:
        server = bind_page()
    except (OSError, PortTaken, PageAddressError):
        return 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    handle = None
    try:
        def open_page() -> None:
            try:
                opened = browser(PAGE_URL)
            except OSError:
                opened = False
            if opened is False:
                print(PAGE_URL)

        try:
            handle = start_studio(
                studio,
                identify=identify,
                spawn=spawn,
                open_page=open_page,
                config=config,
                list_models=list_models,
                pull_model=pull_model,
                whisper_ready=whisper_ready,
                fetch_whisper=fetch_whisper,
            )
        except (PortBusy, DownloadFailed, ChecksumMismatch, OSError) as exc:
            print(exc, file=sys.stderr)
            return 1
        settings = load_settings(config)
        _publish_page(settings, hold, config)
        settings.watch_dir.mkdir(parents=True, exist_ok=True)
        settings.library_dir.mkdir(parents=True, exist_ok=True)
        owned = process is None
        worker = process
        active = settings
        completed = 0
        while True:
            if owned:
                latest = load_settings(config)
                changed = (
                    latest.watch_dir.resolve() != active.watch_dir.resolve()
                    or latest.library_dir.resolve() != active.library_dir.resolve()
                )
                if changed or worker is None:
                    latest.watch_dir.mkdir(parents=True, exist_ok=True)
                    latest.library_dir.mkdir(parents=True, exist_ok=True)
                    active = latest
                    worker = _watch_process(active)
                    _publish_page(active, hold, config)
            stamp = time.time() if now is None else now()
            if selected is not None:
                paths = chosen_recordings(None, selected, now=stamp, stable_seconds=active.stable_seconds)
            else:
                paths = [
                    item.path
                    for item in find_stable_recordings(
                        active.watch_dir, stable_seconds=active.stable_seconds, now=stamp
                    )
                ]
            for path in paths:
                worker(path)
            if cycles is not None:
                completed += 1
                if completed >= cycles:
                    break
            sleep(active.scan_interval_seconds)
    finally:
        if handle is not None:
            handle.close()
        server.shutdown()
        server.server_close()
    return 0


def _publish_page(settings: Settings, hold: Path, config: Path | None = None) -> None:
    StudyHandler.library = settings.library_dir
    StudyHandler.watch = settings.watch_dir
    StudyHandler.hold = hold
    if config is not None:
        StudyHandler.config = config


def _watch_process(settings: Settings) -> Callable[[Path], None]:
    configure_logging(settings.library_dir)
    pipeline = build_pipeline(settings)
    index = HashIndex(settings.library_dir / "index.json")

    def process(path: Path) -> None:
        stat = path.stat()
        recording = Recording(path, stat.st_size, stat.st_mtime_ns)
        digest = index.hash_of(recording)
        index.save()
        pipeline.process(recording, digest)

    return process


def _list_models() -> list[str]:
    with urllib.request.urlopen("http://127.0.0.1:11435/api/tags", timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item.get("name", "") for item in payload.get("models", [])]


def _pull_model(studio: Path, name: str) -> None:
    binary = studio / "bin" / ("ollama.exe" if os.name == "nt" else "ollama")
    merged = os.environ.copy()
    merged["OLLAMA_HOST"] = "127.0.0.1:11435"
    merged["OLLAMA_MODELS"] = str(studio / "models")
    subprocess.run([str(binary), "pull", name], check=True, env=merged)


def _whisper_ready(studio: Path) -> bool:
    cache = studio / "hf" / "hub"
    if not cache.is_dir():
        return False
    return any(cache.glob("models--*large-v3*/snapshots/*/model.bin"))


def _fetch_whisper(studio: Path) -> None:
    os.environ["HF_HOME"] = str(studio / "hf")
    from faster_whisper import WhisperModel

    WhisperModel("large-v3", device="cpu", compute_type="int8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lecture-study")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--file", type=Path)
    parser.add_argument("command", choices=("once", "watch", "up"))
    args = parser.parse_args(argv)
    if args.command == "up":
        return run_up(
            studio=DEFAULT_ROOT,
            config=args.config,
            identify=identify_port,
            spawn=spawn_ollama,
            browser=webbrowser.open,
            selected=args.file,
            list_models=_list_models,
            pull_model=lambda name: _pull_model(DEFAULT_ROOT, name),
            whisper_ready=lambda: _whisper_ready(DEFAULT_ROOT),
            fetch_whisper=lambda: _fetch_whisper(DEFAULT_ROOT),
        )
    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"configurazione non valida: {exc}", file=sys.stderr)
        return 2
    settings.watch_dir.mkdir(parents=True, exist_ok=True)
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.library_dir)
    pipeline = build_pipeline(settings)
    index = HashIndex(settings.library_dir / "index.json")
    if args.command == "once":
        scan_once(settings, pipeline, index)
        return 0
    log.info("osservo %s", settings.watch_dir)
    try:
        while True:
            scan_once(settings, pipeline, index)
            time.sleep(settings.scan_interval_seconds)
    except KeyboardInterrupt:
        return 0
