from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Callable, TypeVar

from lecture_study import audio
from lecture_study.atomic import read_json, write_json_atomic, write_text_atomic
from lecture_study.config import Settings
from lecture_study.errors import (
    GpuOutOfMemory,
    InsufficientSpace,
    InvalidModelOutput,
    RecordingMissing,
    RetriesExhausted,
    TransientError,
    UnreadableAudio,
)
from lecture_study.hold import default_hold_path
from lecture_study.jobs import FINAL_STATUSES, STAGES, Job, JobState, Stage, Status
from lecture_study.llm import LanguageModel
from lecture_study.report import render_report
from lecture_study.retry import call_with_retries
from lecture_study.scanner import Recording
from lecture_study.study import StudyComposer
from lecture_study.transcribe import Transcriber, Transcript, cuda_is_available, render_transcript

log = logging.getLogger(__name__)
OUT_OF_MEMORY_BEFORE_CPU = 2
T = TypeVar("T")


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        transcriber: Transcriber,
        model: LanguageModel,
        probe: Callable[..., audio.ProbeResult] = audio.probe,
        analyze: Callable[..., audio.BandEnergy] = audio.analyze,
        prepare: Callable[..., audio.Prepared] = audio.prepare,
        free_bytes: Callable[[Path], int] = lambda path: shutil.disk_usage(path).free,
        sleep: Callable[[float], None] = time.sleep,
        cuda_available: Callable[[], bool] = cuda_is_available,
        hold_path: Path | None = None,
    ) -> None:
        self.settings = settings
        self._transcriber = transcriber
        self._model = model
        self._probe = probe
        self._analyze_audio = analyze
        self._prepare_audio = prepare
        self._free_bytes = free_bytes
        self._sleep = sleep
        self._cuda_available = cuda_available
        self._hold_path = default_hold_path() if hold_path is None else hold_path
        self._model_used = False
        self._handlers = {
            Stage.ACCEPT: self._accept,
            Stage.ANALYZE: self._analyze,
            Stage.PREPARE: self._prepare,
            Stage.TRANSCRIBE: self._transcribe,
            Stage.NOTES: self._notes,
            Stage.MINDMAP: self._mindmap,
            Stage.QUESTIONS: self._questions,
        }

    def process(self, recording: Recording, sha256: str) -> JobState:
        job = Job(self.settings.library_dir / sha256)
        state = job.load_state()
        if state.status in FINAL_STATUSES or state.status == Status.STOPPED:
            return state
        if self._hold_path.exists():
            return state
        self._remember_path(job, recording)
        self._model_used = False
        state.status, state.message = Status.RUNNING, ""
        try:
            for stage in STAGES:
                if stage in state.completed:
                    continue
                state.stage = stage
                self._handlers[stage](job, recording, sha256, state)
                job.file(f"{stage}.partial.md").unlink(missing_ok=True)
                state.completed.append(stage.value)
                job.save_state(state)
                if self._hold_path.exists():
                    state.status = Status.STOPPED
                    break
            else:
                state.status, state.stage = Status.DONE, None
                shutil.rmtree(job.work_dir, ignore_errors=True)
        except UnreadableAudio as exc:
            state.status, state.message = Status.FAILED, f"audio illeggibile: {exc}"
        except (RetriesExhausted, InsufficientSpace) as exc:
            state.status, state.message = Status.WAITING, str(exc)
        except RecordingMissing as exc:
            state.status, state.message = Status.PAUSED, str(exc)
        except InvalidModelOutput as exc:
            write_text_atomic(job.file(f"{state.stage}.partial.md"), exc.partial + "\n")
            state.status, state.message = Status.NEEDS_REVIEW, str(exc)
        except Exception as exc:
            log.exception("job %s: errore inatteso nella fase %s", sha256[:12], state.stage)
            state.status, state.message = Status.FAILED, f"errore inatteso: {type(exc).__name__}: {exc}"
        if self._model_used:
            self._model.release()
        job.save_state(state)
        write_text_atomic(job.file("report.md"), render_report(state, job.read_source()))
        log.info("job %s path=%s stage=%s status=%s", sha256[:12], recording.path, state.stage, state.status)
        return state

    def _remember_path(self, job: Job, recording: Recording) -> None:
        source = job.read_source()
        if source and source.get("path") != str(recording.path) and not Path(source["path"]).exists():
            source["path"] = str(recording.path)
            job.write_source(source)

    def _audio_call(self, recording: Recording, operation: Callable[[], T]) -> T:
        missing = RecordingMissing(f"registrazione non trovata: {recording.path}")
        if not recording.path.exists():
            raise missing
        try:
            return operation()
        except UnreadableAudio:
            if not recording.path.exists():
                raise missing from None
            raise

    def _on_retry(self, state: JobState, stage: Stage) -> Callable[[TransientError, int, int], None]:
        def record(error: TransientError, retry: int, delay: int) -> None:
            state.events.append(f"{stage}: {error}; ripetizione {retry} tra {delay} s")
            log.warning("fase %s: errore temporaneo, ripetizione %d tra %d s", stage, retry, delay)

        return record

    def _accept(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        info = self._audio_call(recording, lambda: self._probe(recording.path, ffprobe=self.settings.ffprobe))
        job.write_source(
            {
                "path": str(recording.path),
                "sha256": sha256,
                "size": recording.size,
                "duration_seconds": round(info.duration_seconds, 2),
                "format": info.format_name,
            }
        )

    def _analyze(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        energy = self._audio_call(recording, lambda: self._analyze_audio(recording.path, ffmpeg=self.settings.ffmpeg))
        source = job.read_source()
        source["analysis"] = {
            "low": energy.low,
            "voice": energy.voice,
            "ratio": round(energy.ratio, 4),
            "threshold": self.settings.highpass_ratio_threshold,
            "highpass_hz": self.settings.highpass_hz,
            "apply": audio.should_highpass(energy, self.settings.highpass_ratio_threshold),
        }
        job.write_source(source)

    def _prepare(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        source = job.read_source()
        required = audio.required_free_bytes(source["duration_seconds"])
        free = self._free_bytes(self.settings.library_dir)
        if free < required:
            raise InsufficientSpace(f"spazio insufficiente: servono {required // 2**20} MB, liberi {free // 2**20} MB")
        highpass_hz = self.settings.highpass_hz if source["analysis"]["apply"] else None
        prepared = self._audio_call(
            recording,
            lambda: self._prepare_audio(recording.path, job.work_dir, ffmpeg=self.settings.ffmpeg, highpass_hz=highpass_hz),
        )
        source["preparation"] = {"highpass_applied": prepared.highpass_applied, "note": prepared.note}
        job.write_source(source)

    def _transcribe(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        if not job.prepared_wav.exists():
            self._prepare(job, recording, sha256, state)
        out_of_memory = 0

        def attempt() -> Transcript:
            nonlocal out_of_memory
            device = "cpu" if not self._cuda_available() or out_of_memory >= OUT_OF_MEMORY_BEFORE_CPU else "cuda"
            try:
                return self._transcriber.transcribe(job.prepared_wav, device=device)
            except GpuOutOfMemory:
                out_of_memory += 1
                if out_of_memory == OUT_OF_MEMORY_BEFORE_CPU:
                    state.events.append("transcribe: memoria video esaurita due volte, si continua sulla CPU")
                raise

        transcript = call_with_retries(
            attempt,
            delays=self.settings.retry_delays,
            sleep=self._sleep,
            on_retry=self._on_retry(state, Stage.TRANSCRIBE),
        )
        write_json_atomic(job.file("transcript.json"), transcript.to_json())
        write_text_atomic(job.file("transcript.md"), render_transcript(transcript, recording.path.stem))
        source = job.read_source()
        source["transcription"] = {
            "language": transcript.language,
            "language_probability": transcript.language_probability,
            "model": transcript.model,
            "device": transcript.device,
        }
        job.write_source(source)
        shutil.rmtree(job.work_dir, ignore_errors=True)

    def _composer(self, state: JobState, stage: Stage) -> StudyComposer:
        self._model_used = True
        on_retry = self._on_retry(state, stage)
        return StudyComposer(
            self._model,
            call=lambda operation: call_with_retries(
                operation, delays=self.settings.retry_delays, sleep=self._sleep, on_retry=on_retry
            ),
        )

    def _transcript(self, job: Job) -> Transcript:
        return Transcript.from_json(read_json(job.file("transcript.json")))

    def _notes(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        transcript = self._transcript(job)
        notes = self._composer(state, Stage.NOTES).notes(transcript.segments, transcript.language)
        write_text_atomic(job.file("notes.md"), notes)

    def _mindmap(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        notes = job.file("notes.md").read_text(encoding="utf-8")
        mindmap = self._composer(state, Stage.MINDMAP).mindmap(notes, self._transcript(job).language)
        write_text_atomic(job.file("mindmap.md"), mindmap)

    def _questions(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        notes = job.file("notes.md").read_text(encoding="utf-8")
        questions = self._composer(state, Stage.QUESTIONS).questions(notes, self._transcript(job).language)
        write_text_atomic(job.file("questions.md"), questions)
