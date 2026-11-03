from __future__ import annotations

from pathlib import Path

from lecture_study.config import DEFAULT_ROOT
from lecture_study.jobs import Job, Status


def default_hold_path() -> Path:
    return DEFAULT_ROOT / "hold.json"


def resume(hold: Path, job: Job) -> None:
    hold.unlink(missing_ok=True)
    if not job.state_path.exists():
        return
    state = job.load_state()
    if state.status != Status.STOPPED:
        return
    state.status = Status.RUNNING
    state.message = ""
    job.save_state(state)
