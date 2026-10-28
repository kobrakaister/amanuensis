from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from lecture_study.errors import UnreadableAudio

ANALYSIS_RATE = 8000
WAV_BYTES_PER_SECOND = 32000


def _last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


@dataclass(frozen=True)
class ProbeResult:
    duration_seconds: float
    format_name: str


def probe(path: Path, *, ffprobe: str = "ffprobe") -> ProbeResult:
    process = subprocess.run(
        [
            ffprobe, "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type:format=duration,format_name",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if process.returncode != 0:
        raise UnreadableAudio(_last_line(process.stderr) or f"ffprobe exit {process.returncode}")
    data = json.loads(process.stdout or "{}")
    if not data.get("streams"):
        raise UnreadableAudio("nessuna traccia audio")
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise UnreadableAudio("durata non disponibile") from None
    if duration <= 0:
        raise UnreadableAudio("durata nulla")
    return ProbeResult(duration, data["format"].get("format_name", ""))


@dataclass(frozen=True)
class BandEnergy:
    low: float
    voice: float

    @property
    def ratio(self) -> float:
        return self.low / self.voice if self.voice > 0 else 0.0


def band_energy(samples: np.ndarray, rate: int) -> BandEnergy:
    spectrum = np.abs(np.fft.rfft(samples)) ** 2
    frequencies = np.fft.rfftfreq(samples.size, 1 / rate)
    low = spectrum[(frequencies >= 20) & (frequencies < 80)].sum()
    voice = spectrum[(frequencies >= 80) & (frequencies < 300)].sum()
    return BandEnergy(float(low), float(voice))


def analyze(path: Path, *, ffmpeg: str = "ffmpeg", block_seconds: int = 10) -> BandEnergy:
    command = [ffmpeg, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(ANALYSIS_RATE), "-f", "f32le", "-"]
    low = voice = 0.0
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        while chunk := process.stdout.read(ANALYSIS_RATE * block_seconds * 4):
            samples = np.frombuffer(chunk[: len(chunk) - len(chunk) % 4], dtype=np.float32)
            if samples.size:
                energy = band_energy(samples, ANALYSIS_RATE)
                low += energy.low
                voice += energy.voice
        stderr = process.stderr.read().decode("utf-8", "replace")
    if process.returncode != 0:
        raise UnreadableAudio(_last_line(stderr) or f"ffmpeg exit {process.returncode}")
    return BandEnergy(low, voice)


def should_highpass(energy: BandEnergy, threshold: float) -> bool:
    return energy.ratio >= threshold


@dataclass(frozen=True)
class Prepared:
    path: Path
    highpass_applied: bool
    note: str


def prepare_command(source: Path, target: Path, *, ffmpeg: str, highpass_hz: int | None) -> list[str]:
    command = [ffmpeg, "-v", "error", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000"]
    if highpass_hz is not None:
        command += ["-af", f"highpass=f={highpass_hz}"]
    return command + ["-c:a", "pcm_s16le", "-f", "wav", str(target)]


def prepare(
    source: Path,
    work_dir: Path,
    *,
    ffmpeg: str = "ffmpeg",
    highpass_hz: int | None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Prepared:
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "prepared.wav"
    partial = work_dir / "prepared.tmp.wav"
    note = ""
    attempts = [highpass_hz, None] if highpass_hz is not None else [None]
    for hz in attempts:
        process = run(
            prepare_command(source, partial, ffmpeg=ffmpeg, highpass_hz=hz),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if process.returncode == 0:
            os.replace(partial, target)
            return Prepared(target, hz is not None, note)
        note = f"filtro passa-alto non applicato: {_last_line(process.stderr) or process.returncode}"
    partial.unlink(missing_ok=True)
    raise UnreadableAudio(_last_line(process.stderr) or f"ffmpeg exit {process.returncode}")


def required_free_bytes(duration_seconds: float) -> int:
    return int(2 * WAV_BYTES_PER_SECOND * duration_seconds)
