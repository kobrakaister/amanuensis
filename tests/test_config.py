from pathlib import Path

import pytest

from lecture_study.config import DRIVE_REMOTE, ConfigError, Settings, load_settings, validate, windows_drive_type

DRIVE_FIXED = 3


def local(path):
    return DRIVE_FIXED


def test_valid_local_settings(tmp_path):
    validate(Settings(watch_dir=tmp_path / "lezioni", library_dir=tmp_path / "library"), roots=[], drive_type=local)


def test_rejects_directory_inside_onedrive(tmp_path):
    onedrive = (tmp_path / "OneDrive - Vertiv Co").resolve()
    settings = Settings(watch_dir=onedrive / "lezioni", library_dir=tmp_path / "library")
    with pytest.raises(ConfigError, match="OneDrive"):
        validate(settings, roots=[onedrive], drive_type=local)


def test_rejects_network_drive(tmp_path):
    settings = Settings(watch_dir=tmp_path / "lezioni", library_dir=tmp_path / "library")
    with pytest.raises(ConfigError, match="network drive"):
        validate(settings, roots=[], drive_type=lambda path: DRIVE_REMOTE)


def test_unc_path_is_a_network_drive():
    assert windows_drive_type(Path(r"\\server\share\lezioni")) == DRIVE_REMOTE


def test_rejects_library_inside_watch_dir(tmp_path):
    settings = Settings(watch_dir=tmp_path, library_dir=tmp_path / "library")
    with pytest.raises(ConfigError, match="inside the watch folder"):
        validate(settings, roots=[], drive_type=local)


def test_rejects_ollama_outside_this_pc(tmp_path):
    settings = Settings(watch_dir=tmp_path / "in", library_dir=tmp_path / "out", ollama_url="http://192.168.1.10:11434")
    with pytest.raises(ConfigError, match="this PC"):
        validate(settings, roots=[], drive_type=local)


def test_rejects_non_positive_numbers(tmp_path):
    settings = Settings(watch_dir=tmp_path / "in", library_dir=tmp_path / "out", highpass_hz=0)
    with pytest.raises(ConfigError, match="numeric"):
        validate(settings, roots=[], drive_type=local)


def test_load_settings_reads_toml(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'watch_dir = "{(tmp_path / "in").as_posix()}"\n'
        f'library_dir = "{(tmp_path / "out").as_posix()}"\n'
        "highpass_hz = 100\n"
        "highpass_ratio_threshold = 2\n",
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.watch_dir == tmp_path / "in"
    assert settings.highpass_hz == 100
    assert settings.highpass_ratio_threshold == 2.0


def test_load_settings_rejects_unknown_key(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('colour = "blue"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown setting"):
        load_settings(config)


def test_load_settings_rejects_wrong_type(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('highpass_hz = "ottanta"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="highpass_hz"):
        load_settings(config)
