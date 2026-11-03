import math
import shutil
import struct
import subprocess
import wave

import pytest

from lecture_study.config import AUDIO_EXTENSIONS

ACCEPTED = frozenset({
    ".wav", ".aiff", ".aif", ".caf",
    ".mp3",
    ".m4a", ".mp4", ".aac",
    ".3gp", ".3gpp", ".amr",
    ".ogg", ".opus", ".webm",
    ".flac",
})

CONTAINERS = [
    pytest.param(".wav", ["-c:a", "pcm_s16le"], id="wav"),
    pytest.param(".aiff", ["-c:a", "pcm_s16le", "-f", "aiff"], id="aiff"),
    pytest.param(".aif", ["-c:a", "pcm_s16le", "-f", "aiff"], id="aif"),
    pytest.param(".caf", ["-c:a", "pcm_s16le", "-f", "caf"], id="caf-pcm"),
    pytest.param(".caf", ["-c:a", "alac", "-f", "caf"], id="caf-alac"),
    pytest.param(".mp3", ["-c:a", "libmp3lame", "-q:a", "7"], id="mp3"),
    pytest.param(".m4a", ["-c:a", "aac"], id="m4a-aac"),
    pytest.param(".m4a", ["-c:a", "alac"], id="m4a-alac"),
    pytest.param(".mp4", ["-c:a", "aac"], id="mp4"),
    pytest.param(".aac", ["-c:a", "aac", "-f", "adts"], id="aac"),
    pytest.param(".3gp", ["-c:a", "libopencore_amrnb", "-ar", "8000", "-ac", "1", "-f", "3gp"], id="3gp"),
    pytest.param(".3gpp", ["-c:a", "libopencore_amrnb", "-ar", "8000", "-ac", "1", "-f", "3gp"], id="3gpp"),
    pytest.param(".amr", ["-c:a", "libopencore_amrnb", "-ar", "8000", "-ac", "1", "-f", "amr"], id="amr"),
    pytest.param(".ogg", ["-c:a", "libvorbis", "-q:a", "2"], id="ogg"),
    pytest.param(".opus", ["-c:a", "libopus", "-f", "ogg"], id="opus"),
    pytest.param(".webm", ["-c:a", "libopus", "-f", "webm"], id="webm"),
    pytest.param(".flac", ["-c:a", "flac"], id="flac"),
]


def test_accepted_extensions_match_phone_and_export_formats():
    assert AUDIO_EXTENSIONS == ACCEPTED


def write_tone(path):
    rate = 16000
    frames = int(rate * 0.4)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        pcm = bytearray()
        for index in range(frames):
            sample = int(8000 * math.sin(2 * math.pi * 440 * index / rate))
            pcm += struct.pack("<h", sample)
        handle.writeframes(pcm)


@pytest.mark.parametrize(("suffix", "encode_args"), CONTAINERS)
def test_ffmpeg_decodes_container_back_to_wav(tmp_path, suffix, encode_args):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.fail("ffmpeg must be on PATH")
    source = tmp_path / "source.wav"
    write_tone(source)
    encoded = tmp_path / f"sample{suffix}"
    decoded = tmp_path / "decoded.wav"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), *encode_args, str(encoded)],
        check=True,
    )
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(encoded), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(decoded)],
        check=True,
    )
    with wave.open(str(decoded)) as handle:
        assert (handle.getnchannels(), handle.getframerate(), handle.getsampwidth()) == (1, 16000, 2)
        assert handle.getnframes() > 0
