import wave

import numpy as np
import pytest

from lecture_study.errors import GpuOutOfMemory, TransientError, UnreadableAudio
from lecture_study.transcribe import (
    Segment,
    Transcript,
    choose_language,
    classify_runtime_error,
    format_timestamp,
    read_wav_head,
    read_wav_mono,
    render_transcript,
)


@pytest.mark.parametrize(
    ("detected", "probability", "expected"),
    [("en", 0.95, "en"), ("it", 0.80, "it"), ("en", 0.79, "it"), ("fr", 0.99, "it")],
)
def test_choose_language(detected, probability, expected):
    assert choose_language(detected, probability) == expected


def test_format_timestamp():
    assert format_timestamp(3725.9) == "01:02:05"
    assert format_timestamp(0) == "00:00:00"


def test_render_transcript_lists_segments_with_times():
    transcript = Transcript("it", 0.97, "large-v3", "cuda", (Segment(0.0, 4.0, "Buongiorno."), Segment(65.0, 70.0, "Primo tema.")))
    assert render_transcript(transcript, "strategia") == "# strategia\n\n[00:00:00] Buongiorno.\n[00:01:05] Primo tema.\n"


def test_transcript_json_round_trip():
    transcript = Transcript("en", 0.91, "large-v3", "cpu", (Segment(1.5, 3.0, "Hello."),))
    assert Transcript.from_json(transcript.to_json()) == transcript


def test_out_of_memory_is_classified_as_gpu_out_of_memory():
    assert isinstance(classify_runtime_error(RuntimeError("CUDA failed with error out of memory")), GpuOutOfMemory)


def test_busy_gpu_is_transient_but_not_out_of_memory():
    error = classify_runtime_error(RuntimeError("CUDA failed with error device busy"))
    assert isinstance(error, TransientError) and not isinstance(error, GpuOutOfMemory)


def test_other_runtime_errors_are_left_alone():
    original = RuntimeError("bad model file")
    assert classify_runtime_error(original) is original


def test_read_wav_head_stops_at_available_audio(tmp_path):
    path = tmp_path / "short.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(np.zeros(32000, dtype="<i2").tobytes())
    samples = read_wav_head(path, 60)
    assert samples.dtype == np.float32
    assert samples.size == 32000
    assert read_wav_mono(path).size == 32000


def test_read_wav_mono_rejects_stereo(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(np.zeros(32000, dtype="<i2").tobytes())
    with pytest.raises(UnreadableAudio):
        read_wav_mono(path)
