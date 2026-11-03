import os
from pathlib import Path

from lecture_study.cli import main, run_up
from lecture_study.page import StudyHandler


ROOT = Path(__file__).resolve().parents[1]


class Proc:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True


def _config(tmp_path: Path, folder: Path) -> Path:
    library = tmp_path / "library"
    library.mkdir()
    config = tmp_path / "config.toml"
    config.write_text(
        f'watch_dir = "{folder.as_posix()}"\nlibrary_dir = "{library.as_posix()}"\nstable_seconds = 30\n',
        encoding="utf-8",
    )
    return config


def _age(path: Path, when: float) -> None:
    os.utime(path, (when, when))


def test_up_reuses_ollama_serves_the_page_and_watches_one_file(tmp_path, capsys):
    folder = tmp_path / "lezioni"
    folder.mkdir()
    chosen = folder / "a.m4a"
    sibling = folder / "b.m4a"
    chosen.write_bytes(b"a")
    sibling.write_bytes(b"b")
    now = 1_000.0
    _age(chosen, now - 40)
    _age(sibling, now - 40)
    seen = []
    spawned = []
    processed = []

    def identify(port):
        seen.append(port)
        return "ollama"

    def browser(url):
        raise OSError("browser assente")

    code = run_up(
        studio=tmp_path / "studio",
        config=_config(tmp_path, folder),
        identify=identify,
        spawn=lambda args, env: spawned.append((args, env)),
        browser=browser,
        selected=chosen,
        cycles=1,
        process=processed.append,
        now=lambda: now,
        sleep=lambda seconds: None,
    )
    assert code == 0
    assert seen == [11435]
    assert spawned == []
    assert processed == [chosen]
    assert StudyHandler.library == tmp_path / "library"
    assert StudyHandler.hold == tmp_path / "studio" / "hold.json"
    assert "http://127.0.0.1:8765/" in capsys.readouterr().out


def test_up_starts_ollama_and_watches_the_folder(tmp_path):
    folder = tmp_path / "lezioni"
    folder.mkdir()
    first = folder / "a.m4a"
    second = folder / "b.m4a"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    now = 1_000.0
    _age(first, now - 40)
    _age(second, now - 40)
    proc = Proc()
    processed = []

    def spawn(args, env):
        proc.args = args
        proc.env = env
        return proc

    code = run_up(
        studio=tmp_path / "studio",
        config=_config(tmp_path, folder),
        identify=lambda port: "free",
        spawn=spawn,
        browser=lambda url: None,
        cycles=1,
        process=processed.append,
        now=lambda: now,
        sleep=lambda seconds: None,
    )
    assert code == 0
    assert proc.env["OLLAMA_HOST"] == "127.0.0.1:11435"
    assert proc.terminated
    assert processed == [first, second]


def test_once_and_watch_stay_available(tmp_path, monkeypatch):
    folder = tmp_path / "lezioni"
    folder.mkdir()
    config = _config(tmp_path, folder)
    assert main(["once", "--config", str(config)]) == 0
    monkeypatch.setattr("lecture_study.cli.time.sleep", lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert main(["watch", "--config", str(config)]) == 0
    captured = {}

    def fake_run_up(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("lecture_study.cli.run_up", fake_run_up)
    chosen = folder / "a.m4a"
    chosen.write_bytes(b"a")
    assert main(["up", "--config", str(config), "--file", str(chosen)]) == 0
    assert captured["selected"] == chosen
    assert captured["config"] == config


def test_launchers_use_the_studio_bin_and_not_the_profile_installer():
    for name in ("studio.cmd", "studio.sh"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "mba-studio" in text
        assert "bin" in text
        assert "UV_PROJECT_ENVIRONMENT" in text
        assert "UV_PYTHON_INSTALL_DIR" in text
        assert "UV_CACHE_DIR" in text
        assert "lecture-study up" in text
        assert "astral.sh/uv/install" not in text
