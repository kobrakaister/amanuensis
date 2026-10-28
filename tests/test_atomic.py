import os

import pytest

from lecture_study.atomic import read_json, write_json_atomic, write_text_atomic


def test_write_text_atomic_replaces_content_and_leaves_no_temp_file(tmp_path):
    target = tmp_path / "notes.md"
    write_text_atomic(target, "uno")
    write_text_atomic(target, "due")
    assert target.read_text(encoding="utf-8") == "due"
    assert list(tmp_path.iterdir()) == [target]


def test_failed_rename_keeps_previous_content(tmp_path, monkeypatch):
    target = tmp_path / "notes.md"
    write_text_atomic(target, "uno")

    def failing_replace(source, destination):
        raise OSError("disco pieno")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        write_text_atomic(target, "due")
    assert target.read_text(encoding="utf-8") == "uno"


def test_json_round_trip_keeps_accents(tmp_path):
    target = tmp_path / "sub" / "source.json"
    write_json_atomic(target, {"titolo": "attività"})
    assert read_json(target) == {"titolo": "attività"}
    assert "attività" in target.read_text(encoding="utf-8")
