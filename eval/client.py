"""Client for the local transcription service.

There is no HTTP endpoint. Decoding follows `FasterWhisperTranscriber`
in `lecture_study.transcribe`: same model, same device, same language rule,
`beam_size=5`, and `vad_filter=True`. The model stays loaded for every call
in the process, so later samples do not pay for loading it again. `lang` is
the dataset language and is not forced on the decoder.
"""

from __future__ import annotations

from pathlib import Path

_model = None
_device: str | None = None


def _load():
    global _model, _device
    if _model is not None:
        return _model
    import ctranslate2

    from lecture_study.config import Settings
    from lecture_study.transcribe import add_nvidia_library_dirs

    add_nvidia_library_dirs()
    from faster_whisper import WhisperModel

    _device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    compute_type = "int8_float16" if _device == "cuda" else "int8"
    _model = WhisperModel(Settings().whisper_model, device=_device, compute_type=compute_type)
    return _model


def transcribe(wav_path: str, lang: str) -> str:
    if lang not in {"en", "it"}:
        raise ValueError(f"unsupported language: {lang}")
    from lecture_study.transcribe import (
        LANGUAGE_SAMPLE_SECONDS,
        choose_language,
        classify_runtime_error,
        read_wav_mono,
    )

    model = _load()
    audio = read_wav_mono(Path(wav_path))
    try:
        detected, probability, _ = model.detect_language(audio=audio[: 16000 * LANGUAGE_SAMPLE_SECONDS])
        language = choose_language(detected, probability)
        segments, _ = model.transcribe(audio, language=language, beam_size=5, vad_filter=True)
        texts = [segment.text.strip() for segment in segments if segment.text.strip()]
    except RuntimeError as exc:
        classified = classify_runtime_error(exc)
        if classified is exc:
            raise
        raise classified from exc
    return " ".join(texts).strip()
