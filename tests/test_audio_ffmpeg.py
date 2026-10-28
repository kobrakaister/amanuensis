import shutil
import wave

import numpy as np
import pytest

from lecture_study.audio import analyze, prepare, probe, should_highpass
from lecture_study.errors import UnreadableAudio

RATE = 44100


@pytest.fixture(scope="module")
def tools():
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not (ffmpeg and ffprobe):
        pytest.fail("ffmpeg e ffprobe devono essere nel PATH (Task 0)")
    return ffmpeg, ffprobe


def tone(frequency, amplitude, seconds=5):
    t = np.arange(RATE * seconds) / RATE
    return amplitude * np.sin(2 * np.pi * frequency * t)


def write_wav(path, signal):
    pcm = (np.clip(signal, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())


def test_rumble_triggers_highpass_and_produces_16k_mono_wav(tmp_path, tools):
    ffmpeg, ffprobe = tools
    source = tmp_path / "lezione.wav"
    write_wav(source, tone(50, 0.5) + tone(200, 0.2))

    assert probe(source, ffprobe=ffprobe).duration_seconds == pytest.approx(5, abs=0.1)
    energy = analyze(source, ffmpeg=ffmpeg)
    assert should_highpass(energy, 1.0)

    prepared = prepare(source, tmp_path / "work", ffmpeg=ffmpeg, highpass_hz=80)
    assert prepared.highpass_applied
    with wave.open(str(prepared.path)) as handle:
        assert (handle.getnchannels(), handle.getframerate(), handle.getsampwidth()) == (1, 16000, 2)
    assert analyze(prepared.path, ffmpeg=ffmpeg).ratio < energy.ratio
    assert source.read_bytes()[:4] == b"RIFF"


def test_voice_band_only_does_not_trigger_highpass(tmp_path, tools):
    ffmpeg, _ = tools
    source = tmp_path / "voce.wav"
    write_wav(source, tone(200, 0.3))
    assert not should_highpass(analyze(source, ffmpeg=ffmpeg), 1.0)


def test_non_audio_file_is_unreadable(tmp_path, tools):
    _, ffprobe = tools
    broken = tmp_path / "rotto.m4a"
    broken.write_bytes(b"non sono audio")
    with pytest.raises(UnreadableAudio):
        probe(broken, ffprobe=ffprobe)
