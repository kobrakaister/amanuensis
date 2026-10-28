from __future__ import annotations

import importlib.util
import os
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np

from lecture_study.errors import GpuOutOfMemory, TransientError, UnreadableAudio

SUPPORTED_LANGUAGES = ("it", "en")
FALLBACK_LANGUAGE = "it"
MIN_LANGUAGE_PROBABILITY = 0.80
LANGUAGE_SAMPLE_SECONDS = 60


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcript:
    language: str
    language_probability: float
    model: str
    device: str
    segments: tuple[Segment, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "model": self.model,
            "device": self.device,
            "segments": [asdict(segment) for segment in self.segments],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Transcript:
        return cls(
            language=data["language"],
            language_probability=float(data["language_probability"]),
            model=data["model"],
            device=data["device"],
            segments=tuple(Segment(**segment) for segment in data["segments"]),
        )


class Transcriber(Protocol):
    def transcribe(self, wav: Path, *, device: str) -> Transcript: ...


def choose_language(detected: str, probability: float) -> str:
    if detected in SUPPORTED_LANGUAGES and probability >= MIN_LANGUAGE_PROBABILITY:
        return detected
    return FALLBACK_LANGUAGE


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def render_segments(segments: Sequence[Segment]) -> str:
    return "\n".join(f"[{format_timestamp(segment.start)}] {segment.text}" for segment in segments)


def render_transcript(transcript: Transcript, title: str) -> str:
    return f"# {title}\n\n{render_segments(transcript.segments)}\n"


def read_wav_head(path: Path, seconds: int) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        frames = handle.readframes(handle.getframerate() * seconds)
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def read_wav_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if (channels, width, rate) != (1, 2, 16000):
        raise UnreadableAudio("il WAV di lavoro deve essere mono, 16 kHz, 16 bit")
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def classify_runtime_error(exc: RuntimeError) -> Exception:
    message = str(exc)
    if "out of memory" in message.lower():
        return GpuOutOfMemory(message)
    if "cuda" in message.lower():
        return TransientError(message)
    return exc


def add_nvidia_library_dirs() -> None:
    for package in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(package)
        except ModuleNotFoundError:
            continue
        for location in (spec.submodule_search_locations or []) if spec else []:
            bin_dir = Path(location) / "bin"
            if bin_dir.is_dir():
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


class FasterWhisperTranscriber:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def transcribe(self, wav: Path, *, device: str) -> Transcript:
        add_nvidia_library_dirs()
        from faster_whisper import WhisperModel

        compute_type = "int8_float16" if device == "cuda" else "int8"
        try:
            model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
            audio = read_wav_mono(wav)
            detected, probability, _ = model.detect_language(audio=audio[: 16000 * LANGUAGE_SAMPLE_SECONDS])
            language = choose_language(detected, probability)
            segments, _ = model.transcribe(audio, language=language, beam_size=5, vad_filter=True)
            collected = tuple(
                Segment(round(segment.start, 2), round(segment.end, 2), segment.text.strip())
                for segment in segments
                if segment.text.strip()
            )
        except RuntimeError as exc:
            classified = classify_runtime_error(exc)
            if classified is exc:
                raise
            raise classified from exc
        return Transcript(language, round(probability, 3), self.model_name, device, collected)
