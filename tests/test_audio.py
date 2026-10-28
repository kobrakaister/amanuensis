import subprocess

import numpy as np
import pytest

from lecture_study.audio import (
    BandEnergy,
    band_energy,
    prepare,
    prepare_command,
    required_free_bytes,
    should_highpass,
)
from lecture_study.errors import UnreadableAudio

RATE = 8000


def tone(frequency, amplitude, seconds=4):
    t = np.arange(RATE * seconds) / RATE
    return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)


def test_rumble_dominates_low_band():
    energy = band_energy(tone(50, 0.5) + tone(200, 0.2), RATE)
    assert energy.ratio == pytest.approx(6.25, rel=0.05)


def test_voice_band_only_has_low_ratio():
    assert band_energy(tone(200, 0.3), RATE).ratio < 0.01


def test_threshold_is_inclusive():
    assert should_highpass(BandEnergy(low=1.0, voice=1.0), 1.0)
    assert not should_highpass(BandEnergy(low=0.99, voice=1.0), 1.0)


def test_silence_has_zero_ratio():
    assert BandEnergy(low=0.0, voice=0.0).ratio == 0.0


def test_prepare_command_adds_filter_only_when_requested(tmp_path):
    target = tmp_path / "b.wav"
    with_filter = prepare_command(tmp_path / "a.m4a", target, ffmpeg="ffmpeg", highpass_hz=80)
    without = prepare_command(tmp_path / "a.m4a", target, ffmpeg="ffmpeg", highpass_hz=None)
    assert "highpass=f=80" in with_filter
    assert "-af" not in without
    assert without[-5:] == ["-c:a", "pcm_s16le", "-f", "wav", str(target)]
    start = without.index("-ac")
    assert without[start:start + 4] == ["-ac", "1", "-ar", "16000"]


def test_prepare_falls_back_to_unfiltered_audio(tmp_path):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if "-af" in command:
            return subprocess.CompletedProcess(command, 1, "", "No such filter: 'highpass'")
        (tmp_path / "work" / "prepared.tmp.wav").write_bytes(b"RIFF")
        return subprocess.CompletedProcess(command, 0, "", "")

    prepared = prepare(tmp_path / "a.m4a", tmp_path / "work", highpass_hz=80, run=run)
    assert prepared.path == tmp_path / "work" / "prepared.wav"
    assert prepared.path.exists()
    assert not prepared.highpass_applied
    assert "non applicato" in prepared.note
    assert len(commands) == 2


def test_prepare_raises_when_audio_cannot_be_decoded(tmp_path):
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "Invalid data found when processing input")

    with pytest.raises(UnreadableAudio, match="Invalid data"):
        prepare(tmp_path / "a.m4a", tmp_path / "work", highpass_hz=None, run=run)
    assert not (tmp_path / "work" / "prepared.tmp.wav").exists()


def test_required_free_bytes_is_twice_the_wav_size():
    assert required_free_bytes(3600) == 230_400_000
