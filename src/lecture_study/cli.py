from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Callable

from lecture_study.config import DEFAULT_CONFIG, ConfigError, Settings, load_settings
from lecture_study.llm import OllamaClient
from lecture_study.pipeline import Pipeline
from lecture_study.scanner import HashIndex, find_stable_recordings
from lecture_study.transcribe import FasterWhisperTranscriber

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lecture-study")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("command", choices=("once", "watch"))
    args = parser.parse_args(argv)
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
