import os
import time

from lecture_study.cli import main, scan_once
from lecture_study.config import Settings
from lecture_study.scanner import HashIndex


def make(path, age):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(path.name.encode())
    moment = time.time() - age
    os.utime(path, (moment, moment))
    return path


class RecordingPipeline:
    def __init__(self):
        self.seen = []

    def process(self, recording, sha256):
        self.seen.append((recording.path, sha256))


def test_scan_once_processes_stable_recordings_oldest_first(tmp_path):
    settings = Settings(watch_dir=tmp_path / "in", library_dir=tmp_path / "out")
    settings.library_dir.mkdir()
    older = make(settings.watch_dir / "a.m4a", age=600)
    newer = make(settings.watch_dir / "b.mp3", age=120)
    make(settings.watch_dir / "c.wav", age=1)
    pipeline = RecordingPipeline()
    assert scan_once(settings, pipeline, HashIndex(settings.library_dir / "index.json")) == 2
    assert [path for path, _ in pipeline.seen] == [older, newer]
    assert all(len(sha) == 64 for _, sha in pipeline.seen)
    assert (settings.library_dir / "index.json").exists()


def test_main_rejects_ollama_outside_this_pc(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(
        f'watch_dir = "{(tmp_path / "in").as_posix()}"\n'
        f'library_dir = "{(tmp_path / "out").as_posix()}"\n'
        'ollama_url = "http://10.0.0.5:11434"\n',
        encoding="utf-8",
    )
    assert main(["--config", str(config), "once"]) == 2
    assert "questo PC" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
