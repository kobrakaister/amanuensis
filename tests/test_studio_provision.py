import hashlib
import io
import zipfile

import pytest

from lecture_study.studio import (
    ChecksumMismatch,
    DownloadFailed,
    Pin,
    PortBusy,
    StudioHandle,
    ensure_tool,
    load_pins,
    start_studio,
)


def pin_for(payload: bytes, **overrides) -> Pin:
    values = {
        "name": "uv",
        "system": "windows-x64",
        "version": "1",
        "url": "https://example.test/uv.zip",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "member": "uv.exe",
        "archive": "uv",
        "format": "zip",
    }
    values.update(overrides)
    return Pin(**values)


def zip_bytes(member: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(member, content)
    return buffer.getvalue()


def test_matching_archive_is_not_downloaded_again(tmp_path):
    payload = zip_bytes("uv.exe", b"uv-bin")
    pin = pin_for(payload)
    calls = []

    def fetch(url):
        calls.append(url)
        return payload

    first = ensure_tool(pin, tmp_path, fetch)
    assert first.read_bytes() == b"uv-bin"
    assert calls == [pin.url]
    assert ensure_tool(pin, tmp_path, fetch) == first
    assert calls == [pin.url]


def test_checksum_mismatch_is_downloaded_again_and_not_extracted(tmp_path):
    good = zip_bytes("uv.exe", b"uv-bin")
    pin = pin_for(good)
    (tmp_path / "uv-windows-x64.zip").write_bytes(b"stale")
    calls = []

    def fetch(url):
        calls.append(url)
        return b"not-the-archive"

    with pytest.raises(ChecksumMismatch):
        ensure_tool(pin, tmp_path, fetch)
    assert calls == [pin.url]
    assert not (tmp_path / "uv-windows-x64.partial").exists()
    assert not (tmp_path / "uv.exe").exists()


def test_partial_download_is_discarded(tmp_path):
    payload = zip_bytes("uv.exe", b"uv-bin")
    pin = pin_for(payload)
    partial = tmp_path / "uv-windows-x64.partial"
    partial.write_bytes(b"half")

    def fetch(url):
        assert not partial.exists()
        raise OSError("rete assente")

    with pytest.raises(Exception, match="uv"):
        ensure_tool(pin, tmp_path, fetch)
    assert not partial.exists()


def test_shipped_pins_for_uv_ollama_and_windows_ffmpeg():
    pins = load_pins()
    expected = {
        ("uv", "windows-x64"),
        ("uv", "mac-arm64"),
        ("uv", "mac-x64"),
        ("ollama", "windows-x64"),
        ("ollama", "mac-arm64"),
        ("ollama", "mac-x64"),
        ("ffmpeg", "windows-x64"),
        ("ffprobe", "windows-x64"),
    }
    found = {(pin.name, pin.system) for pin in pins}
    assert expected <= found
    for pin in pins:
        assert len(pin.sha256) == 64
        int(pin.sha256, 16)
        assert pin.url.startswith("https://")
        assert pin.version
        assert pin.member


class Proc:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True


def test_free_port_starts_ollama_and_up_stops_that_child(tmp_path):
    seen = []
    proc = Proc()

    def identify(port):
        seen.append(port)
        return "free"

    def spawn(args, env):
        proc.args = args
        proc.env = env
        return proc

    handle = start_studio(tmp_path, identify=identify, spawn=spawn, open_page=lambda: seen.append("page"))
    assert seen == [11435, "page"]
    assert proc.env["OLLAMA_HOST"] == "127.0.0.1:11435"
    assert 11434 not in seen
    handle.close()
    assert proc.terminated
    text = (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert 'ollama_url = "http://127.0.0.1:11435"' in text
    assert "ffmpeg" in text and "ffprobe" in text


def test_existing_ollama_is_reused_and_not_killed(tmp_path):
    spawned = []
    handle = start_studio(tmp_path, identify=lambda port: "ollama", spawn=lambda args, env: spawned.append(args), open_page=lambda: None)
    handle.close()
    assert spawned == []


def test_other_listener_stops_up_and_is_not_killed(tmp_path):
    killed = []
    opened = []
    with pytest.raises(PortBusy):
        start_studio(
            tmp_path,
            identify=lambda port: "other",
            spawn=lambda args, env: killed.append("spawn"),
            kill=killed.append,
            open_page=lambda: opened.append("page"),
        )
    assert killed == []
    assert opened == []


def test_existing_config_is_unchanged(tmp_path):
    config = tmp_path / "config.toml"
    original = 'ffmpeg = "C:/keep/ffmpeg.exe"\nhighpass_hz = 90\n'
    config.write_text(original, encoding="utf-8")
    start_studio(tmp_path, identify=lambda port: "ollama", spawn=lambda args, env: None, open_page=lambda: None, config=config)
    assert config.read_text(encoding="utf-8") == original


def test_blocked_binary_stops_once_without_the_page(tmp_path):
    calls = []
    opened = []

    def spawn(args, env):
        calls.append(args)
        raise OSError("bloccato dal sistema")

    with pytest.raises(OSError, match="bloccato"):
        start_studio(tmp_path, identify=lambda port: "free", spawn=spawn, open_page=lambda: opened.append("page"))
    assert len(calls) == 1
    assert opened == []


def test_failed_download_names_the_piece_and_skips_the_page(tmp_path):
    opened = []
    pin = pin_for(b"unused", name="ffmpeg")

    def fetch(url):
        raise OSError("rete assente")

    with pytest.raises(DownloadFailed, match="ffmpeg"):
        start_studio(tmp_path, identify=lambda port: "free", spawn=lambda args, env: None, open_page=lambda: opened.append("page"), pins=(pin,), fetch=fetch, system="windows-x64")
    assert opened == []


def test_models_are_ready_before_the_page(tmp_path):
    order = []
    start_studio(
        tmp_path,
        identify=lambda port: "ollama",
        spawn=lambda args, env: None,
        open_page=lambda: order.append("page"),
        list_models=lambda: [],
        pull_model=lambda name: order.append(name),
        whisper_ready=lambda: False,
        fetch_whisper=lambda: order.append("whisper"),
    )
    assert order == ["qwen2.5:7b", "whisper", "page"]
