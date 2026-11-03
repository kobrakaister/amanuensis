from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from lecture_study.atomic import read_json, write_json_atomic


class Stage(StrEnum):
    ACCEPT = "accept"
    ANALYZE = "analyze"
    PREPARE = "prepare"
    TRANSCRIBE = "transcribe"
    NOTES = "notes"
    MINDMAP = "mindmap"
    QUESTIONS = "questions"


STAGES = tuple(Stage)


class Status(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    DONE = "done"
    STOPPED = "stopped"


FINAL_STATUSES = frozenset({Status.DONE, Status.FAILED, Status.NEEDS_REVIEW})

STAGE_FILES = {
    Stage.TRANSCRIBE: ("transcript.json", "transcript.md"),
    Stage.NOTES: ("notes.md",),
    Stage.MINDMAP: ("mindmap.md",),
    Stage.QUESTIONS: ("questions.md",),
}


@dataclass
class JobState:
    completed: list[str] = field(default_factory=list)
    status: str = Status.RUNNING
    stage: str | None = None
    message: str = ""
    events: list[str] = field(default_factory=list)


class Job:
    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.work_dir = directory / "work"
        self.state_path = directory / "state.json"
        self.source_path = directory / "source.json"
        self.prepared_wav = self.work_dir / "prepared.wav"

    def file(self, name: str) -> Path:
        return self.dir / name

    def read_source(self) -> dict[str, Any]:
        return read_json(self.source_path) if self.source_path.exists() else {}

    def write_source(self, source: dict[str, Any]) -> None:
        write_json_atomic(self.source_path, source)

    def has_evidence(self, stage: Stage) -> bool:
        if stage is Stage.ACCEPT:
            return self.source_path.exists()
        if stage is Stage.ANALYZE:
            return "analysis" in self.read_source()
        if stage is Stage.PREPARE:
            return self.prepared_wav.exists() or self.has_evidence(Stage.TRANSCRIBE)
        return all(self.file(name).exists() for name in STAGE_FILES[stage])

    def load_state(self) -> JobState:
        if self.state_path.exists():
            return JobState(**read_json(self.state_path))
        completed = []
        for stage in STAGES:
            if not self.has_evidence(stage):
                break
            completed.append(stage.value)
        return JobState(completed=completed)

    def save_state(self, state: JobState) -> None:
        write_json_atomic(self.state_path, asdict(state))
