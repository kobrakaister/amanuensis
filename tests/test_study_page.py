import socket

import pytest

from lecture_study.config import DEFAULT_ROOT
from lecture_study.jobs import Job, JobState, Status
from lecture_study.page import (
    PAGE_HOST,
    PAGE_PORT,
    PageAddressError,
    RejectedExtension,
    StudyHandler,
    apply_hold_action,
    bind_page,
    choose_folders,
    apply_picked,
    chosen_recordings,
    read_product,
    remember_paths,
    render_page,
    serve_and_watch,
)


def test_page_binds_only_loopback_and_a_taken_port_skips_watch():
    assert (PAGE_HOST, PAGE_PORT) == ("127.0.0.1", 8765)
    with pytest.raises(PageAddressError):
        bind_page("0.0.0.0", PAGE_PORT)
    held = socket.socket()
    held.bind((PAGE_HOST, PAGE_PORT))
    watched = []
    try:
        assert serve_and_watch(lambda: watched.append(1)) == 1
    finally:
        held.close()
    assert watched == []


def test_rejected_paths_leave_the_config_unchanged(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('highpass_hz = 90\nffmpeg = "C:/keep/ffmpeg.exe"\n', encoding="utf-8")
    original = config.read_text(encoding="utf-8")
    cloud = tmp_path / "cloud"
    watch = cloud / "lezioni"
    library = cloud / "library"
    watch.mkdir(parents=True)
    library.mkdir()
    assert remember_paths(config, watch, library, roots=[cloud], drive_type=lambda path: 3) is False
    network = tmp_path / "net" / "lezioni"
    archive = tmp_path / "net" / "library"
    network.mkdir(parents=True)
    archive.mkdir()
    assert remember_paths(config, network, archive, roots=[], drive_type=lambda path: 4) is False
    inside = watch / "library"
    inside.mkdir()
    assert remember_paths(config, watch, inside, roots=[], drive_type=lambda path: 3) is False
    assert config.read_text(encoding="utf-8") == original


def test_accepted_paths_change_only_the_two_folders(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('highpass_hz = 90\nffmpeg = "C:/keep/ffmpeg.exe"\n', encoding="utf-8")
    watch = tmp_path / "lezioni"
    library = tmp_path / "library"
    watch.mkdir()
    library.mkdir()
    assert remember_paths(config, watch, library, roots=[], drive_type=lambda path: 3) is True
    text = config.read_text(encoding="utf-8")
    assert "highpass_hz = 90" in text
    assert 'ffmpeg = "C:/keep/ffmpeg.exe"' in text
    assert watch.as_posix() in text
    assert library.as_posix() in text
    assert Settings_default_when_unset()


def Settings_default_when_unset():
    from lecture_study.config import Settings

    settings = Settings()
    return settings.watch_dir == DEFAULT_ROOT / "lezioni" and settings.library_dir == DEFAULT_ROOT / "library"


def test_the_page_keeps_a_refused_pair_and_stores_an_accepted_one(tmp_path):
    audio = tmp_path / "audio"
    results = tmp_path / "risultati"
    audio.mkdir()
    results.mkdir()
    config = tmp_path / "config.toml"
    config.write_text(
        f'watch_dir = "{audio.as_posix()}"\nlibrary_dir = "{results.as_posix()}"\nhighpass_hz = 90\n',
        encoding="utf-8",
    )
    StudyHandler.watch = audio
    StudyHandler.library = results
    inside = audio / "dentro"
    inside.mkdir()
    notice = choose_folders(config, audio, inside)
    assert notice
    assert StudyHandler.watch == audio
    assert StudyHandler.library == results
    text = config.read_text(encoding="utf-8")
    assert "highpass_hz = 90" in text
    assert inside.as_posix() not in text
    new_audio = tmp_path / "nuova-audio"
    new_results = tmp_path / "nuova-risultati"
    new_audio.mkdir()
    new_results.mkdir()
    assert choose_folders(config, new_audio, new_results) == ""
    assert StudyHandler.watch == new_audio
    assert StudyHandler.library == new_results
    stored = config.read_text(encoding="utf-8")
    assert new_audio.as_posix() in stored
    assert new_results.as_posix() in stored
    assert "highpass_hz = 90" in stored
    html = render_page(new_results, ollama_up=True, watch=new_audio)
    assert "Scegli cartella audio" in html and "Scegli cartella risultati" in html
    assert "Cartella audio" in html and "Cartella risultati" in html
    assert new_audio.as_posix() in html and new_results.as_posix() in html
    picked = tmp_path / "scelta"
    picked.mkdir()
    StudyHandler.config = config
    StudyHandler.watch = new_audio
    StudyHandler.library = new_results
    nested = new_audio / "dentro"
    nested.mkdir()
    assert apply_picked("library", nested)
    assert StudyHandler.library == new_results
    assert apply_picked("library", None) == ""
    assert apply_picked("library", picked) == ""
    assert StudyHandler.library == picked
    shown = render_page(picked, ollama_up=True, watch=new_audio)
    assert "Risultati in uso" in shown
    assert picked.as_posix() in shown
    assert "Riprendi" not in shown


def test_paused_queue_lists_each_audio_file(tmp_path):
    audio = tmp_path / "audio"
    results = tmp_path / "out"
    audio.mkdir()
    results.mkdir()
    (audio / "lezione.m4a").write_bytes(b"a")
    hold = tmp_path / "hold.json"
    hold.write_text("{}\n", encoding="utf-8")
    paused = render_page(results, ollama_up=True, watch=audio, hold=hold)
    assert "lezione.m4a" in paused
    assert "in pausa" in paused
    assert "Elaborazione ferma" in paused
    assert "Riprendi" in paused
    queued = render_page(results, ollama_up=True, watch=audio)
    assert "in coda" in queued
    assert "Riprendi" not in queued


def test_folder_or_single_file(tmp_path):
    folder = tmp_path / "lezioni"
    folder.mkdir()
    first = folder / "a.m4a"
    second = folder / "b.m4a"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    now = 1_000.0
    for path in (first, second):
        path.touch()
        _age(path, now - 31)
    assert chosen_recordings(folder, None, now=now, stable_seconds=30) == [first, second]
    assert chosen_recordings(None, first, now=now, stable_seconds=30) == [first]
    _age(first, now)
    assert chosen_recordings(None, first, now=now, stable_seconds=30) == []
    foreign = folder / "note.txt"
    foreign.write_text("x", encoding="utf-8")
    with pytest.raises(RejectedExtension):
        chosen_recordings(None, foreign, now=now, stable_seconds=30)
    assert first.exists() and first.parent == folder


def test_page_lists_only_the_active_folder_and_existing_products(tmp_path):
    active = tmp_path / "library"
    previous = tmp_path / "old"
    _lecture(active, "alfa.m4a", status="running", stage="transcribe", products=["report.md", "transcript.md"])
    _lecture(previous, "vecchia.m4a", status="done", stage="questions", products=["report.md"])
    html = render_page(active, ollama_up=True)
    assert "alfa.m4a" in html
    assert "transcribe" in html and "running" in html
    assert "vecchia.m4a" not in html
    assert 'href="/files/' in html and "report.md" in html and "transcript.md" in html
    assert "notes.md" not in html
    assert "Ollama: risponde" in html
    assert 'name="watch"' in html and 'name="library"' in html
    assert "/list" in html
    quiet = render_page(active, ollama_up=False)
    assert "Ollama: non risponde" in quiet
    later = render_page(active, ollama_up=True)
    assert "transcribe" in later
    state = next((active).iterdir()) / "state.json"
    state.write_text(state.read_text(encoding="utf-8").replace("transcribe", "notes"), encoding="utf-8")
    assert "notes" in render_page(active, ollama_up=True)
    assert (previous / next(previous.iterdir()).name / "report.md").is_file()


def test_product_path_cannot_escape(tmp_path):
    library = tmp_path / "library"
    secret = tmp_path / "secret.txt"
    secret.write_text("segreto", encoding="utf-8")
    with pytest.raises(PermissionError):
        read_product(library, "..", "secret.txt")
    with pytest.raises(PermissionError):
        read_product(library, "a" * 64, "../secret.txt")


def test_page_stop_and_resume_use_the_hold(tmp_path):
    hold = tmp_path / "hold.json"
    job = Job(tmp_path / "library" / ("a" * 64))
    job.save_state(JobState(status=Status.STOPPED, stage="accept"))
    apply_hold_action("stop", hold, job)
    assert hold.is_file()
    apply_hold_action("resume", hold, job)
    assert not hold.exists()
    assert job.load_state().status == Status.RUNNING
    apply_hold_action("stop", hold, None)
    apply_hold_action("resume", hold, None)
    assert not hold.exists()
    other = Job(tmp_path / "library" / ("b" * 64))
    other.save_state(JobState(status=Status.STOPPED, stage="notes"))
    apply_hold_action("stop", hold, library=tmp_path / "library")
    apply_hold_action("resume", hold, library=tmp_path / "library")
    assert job.load_state().status == Status.RUNNING
    assert other.load_state().status == Status.RUNNING
    assert not hold.exists()


def _age(path, when):
    import os

    os.utime(path, (when, when))


def _lecture(library, name, *, status, stage, products):
    job = Job(library / ("b" * 64 if "vecchia" in name else "a" * 64))
    job.save_state(JobState(status=Status(status), stage=stage))
    job.write_source({"path": str(library.parent / name)})
    for product in products:
        (job.dir / product).write_text(product, encoding="utf-8")
