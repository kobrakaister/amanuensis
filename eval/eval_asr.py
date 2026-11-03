"""Measure WER and CER of the transcription service on streaming AMI and mTEDx."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from datasets import Audio, load_dataset

from client import transcribe

TARGET_RATE = 16000
LONGFORM_SECONDS = 300.0
GAP_SECONDS = 0.3
DATASETS = {
    "en": {
        "name": "edinburghcstr/ami",
        "config": "sdm",
        "split": "test",
        "text": "text",
        "group": "meeting_id",
        "id": "audio_id",
    },
    "it": {
        "name": "deepdml/mtedx",
        "config": "it",
        "split": "test",
        "text": "transcript",
        "group": "talk_id",
        "id": "id",
    },
}

_NONVERBAL = re.compile(r"\[[^\]]*\]")
_NOT_WORD = re.compile(r"[^\w']+", re.UNICODE)
_EDGE_APOSTROPHE = re.compile(r"(?<!\w)'|'(?!\w)")
_SPACE = re.compile(r"\s+")


@dataclass
class Sample:
    sample_id: str
    audio: np.ndarray
    reference: str


def normalize(text: str, lang: str) -> str:
    cleaned = text.lower()
    if lang == "en":
        cleaned = _NONVERBAL.sub(" ", cleaned)
    cleaned = _NOT_WORD.sub(" ", cleaned)
    cleaned = _EDGE_APOSTROPHE.sub(" ", cleaned)
    return _SPACE.sub(" ", cleaned).strip()


def decode_audio(payload: dict) -> np.ndarray:
    import librosa

    raw = payload.get("bytes")
    source = io.BytesIO(raw) if raw else payload["path"]
    data, rate = sf.read(source, dtype="float32", always_2d=True)
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    if rate != TARGET_RATE:
        mono = librosa.resample(mono, orig_sr=rate, target_sr=TARGET_RATE)
    return np.asarray(mono, dtype=np.float32)


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def iter_samples(lang: str, n_samples: int, mode: str):
    spec = DATASETS[lang]
    dataset = load_dataset(spec["name"], spec["config"], split=spec["split"], streaming=True)
    dataset = dataset.cast_column("audio", Audio(decode=False))
    silence = np.zeros(int(GAP_SECONDS * TARGET_RATE), dtype=np.float32)
    pieces: list[np.ndarray] = []
    texts: list[str] = []
    duration = 0.0
    group = None
    chunk = 0
    produced = 0

    def emit() -> Sample:
        return Sample(f"{group}-{chunk}", np.concatenate(pieces), " ".join(texts))

    for example in dataset:
        if produced >= n_samples:
            break
        try:
            audio = decode_audio(example["audio"])
        except Exception as exc:
            print(f"audio cannot be decoded: {exc}", file=sys.stderr)
            continue
        text = str(example[spec["text"]] or "")
        if mode == "segment":
            yield Sample(str(example[spec["id"]]), audio, text)
            produced += 1
            continue
        gid = str(example[spec["group"]])
        extra = GAP_SECONDS if pieces else 0.0
        segment_seconds = len(audio) / TARGET_RATE
        if pieces and (gid != group or duration + extra + segment_seconds > LONGFORM_SECONDS):
            yield emit()
            produced += 1
            pieces, texts, duration = [], [], 0.0
            chunk = chunk + 1 if gid == group else 0
            if produced >= n_samples:
                break
        if pieces:
            pieces.append(silence)
            duration += GAP_SECONDS
        pieces.append(audio)
        texts.append(text)
        duration += segment_seconds
        group = gid
    if mode == "longform" and pieces and produced < n_samples:
        yield emit()


def score(reference: str, hypothesis: str) -> tuple[float, float, dict[str, int], dict[str, int]]:
    import jiwer

    words = jiwer.process_words(reference, hypothesis)
    characters = jiwer.process_characters(reference, hypothesis)
    word_counts = {
        "hits": words.hits,
        "substitutions": words.substitutions,
        "deletions": words.deletions,
        "insertions": words.insertions,
    }
    char_counts = {
        "hits": characters.hits,
        "substitutions": characters.substitutions,
        "deletions": characters.deletions,
        "insertions": characters.insertions,
    }
    return words.wer, characters.cer, word_counts, char_counts


def _rate(counts: dict[str, int]) -> float | None:
    total = counts["hits"] + counts["substitutions"] + counts["deletions"]
    if total == 0:
        return None
    return (counts["substitutions"] + counts["deletions"] + counts["insertions"]) / total


def _add(total: dict[str, int], part: dict[str, int]) -> None:
    for key in total:
        total[key] += part[key]


def write_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, TARGET_RATE, subtype="PCM_16")


def run(lang: str, n_samples: int, mode: str, out_dir: Path) -> None:
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    word_totals = {"hits": 0, "substitutions": 0, "deletions": 0, "insertions": 0}
    char_totals = {"hits": 0, "substitutions": 0, "deletions": 0, "insertions": 0}
    factors = []
    for sample in iter_samples(lang, n_samples, mode):
        wav_path = audio_dir / f"{_safe_id(sample.sample_id)}.wav"
        write_wav(wav_path, sample.audio)
        duration = len(sample.audio) / TARGET_RATE
        reference = normalize(sample.reference, lang)
        started = time.perf_counter()
        try:
            hypothesis = normalize(transcribe(str(wav_path), lang), lang)
            elapsed = time.perf_counter() - started
            wer, cer, words, characters = score(reference, hypothesis)
            _add(word_totals, words)
            _add(char_totals, characters)
            if duration > 0:
                factors.append(elapsed / duration)
            row = {
                "id": sample.sample_id,
                "language": lang,
                "duration": f"{duration:.3f}",
                "reference": reference,
                "hypothesis": hypothesis,
                "wer": f"{wer:.6f}",
                "cer": f"{cer:.6f}",
                "service_response_seconds": f"{elapsed:.3f}",
            }
            print(f"{sample.sample_id} duration={duration:.1f}s wer={wer:.3f} cer={cer:.3f} t={elapsed:.1f}s")
        except Exception as exc:
            elapsed = time.perf_counter() - started
            row = {
                "id": sample.sample_id,
                "language": lang,
                "duration": f"{duration:.3f}",
                "reference": reference,
                "hypothesis": f"ERROR: {exc}",
                "wer": "",
                "cer": "",
                "service_response_seconds": f"{elapsed:.3f}",
            }
            print(f"{sample.sample_id} ERROR: {exc}", file=sys.stderr)
            traceback.print_exc()
        rows.append(row)

    fieldnames = [
        "id",
        "language",
        "duration",
        "reference",
        "hypothesis",
        "wer",
        "cer",
        "service_response_seconds",
    ]
    with (out_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    scored = [row for row in rows if row["wer"]]
    worst = sorted(scored, key=lambda row: float(row["wer"]), reverse=True)[:5]
    summary = {
        "dataset": DATASETS[lang]["name"],
        "config": DATASETS[lang]["config"],
        "split": DATASETS[lang]["split"],
        "language": lang,
        "mode": mode,
        "samples": len(rows),
        "errors": len(rows) - len(scored),
        "wer": _rate(word_totals),
        "cer": _rate(char_totals),
        "reference_words": word_totals["hits"] + word_totals["substitutions"] + word_totals["deletions"],
        "real_time_factor_mean": (sum(factors) / len(factors)) if factors else None,
        "worst": [
            {
                "id": row["id"],
                "wer": float(row["wer"]),
                "cer": float(row["cer"]),
                "duration": float(row["duration"]),
                "reference": row["reference"],
                "hypothesis": row["hypothesis"],
            }
            for row in worst
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("wer", "cer", "errors", "real_time_factor_mean")}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure WER for the local transcription service.")
    parser.add_argument("--lang", required=True, choices=("en", "it"))
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument("--mode", choices=("segment", "longform"), default="segment")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.n_samples < 1:
        parser.error("--n-samples deve essere almeno 1")
    return args


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    run(args.lang, args.n_samples, args.mode, args.out_dir)


if __name__ == "__main__":
    main()
