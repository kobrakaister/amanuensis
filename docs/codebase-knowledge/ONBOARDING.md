# Onboarding

## Stack

- Python `>=3.12` (`pyproject.toml`). `.python-version` is `3.12`. The virtualenv is `C:\Users\Mathia.Scucchiari\mba-studio\.venv` (Python 3.12.9).
- Package `lecture-study` 0.1.0. Console script `lecture-study` points at `lecture_study.cli:main`.
- Dependencies: `faster-whisper`, `numpy`, and on Windows `nvidia-cublas-cu12` and `nvidia-cudnn-cu12`. Dev: `pytest`.
- External programs: ffmpeg, ffprobe, and Ollama. They are not Python packages.

## Repository layout

- `src/lecture_study/`: pipeline, audio, transcription, Ollama client, study composer, report, CLI.
- `tests/`: pytest.
- `scripts/register-autostart.ps1`: Windows task `LectureStudyWatch`.
- `docs/superpowers/`: design and plan.
- `eval/`: optional ASR harness, separate requirements, not part of the runtime install.

## Prerequisites

- The virtualenv above, with `UV_PROJECT_ENVIRONMENT` set to it.
- ffmpeg and ffprobe on `PATH`.
- Ollama listening on `http://127.0.0.1:11435` with model `qwen2.5:7b`. Do not stop the older server on port 11434.
- An NVIDIA GPU for the default device. `FasterWhisperTranscriber` can run on CPU after two out-of-memory errors.
- Watch folder `~\mba-studio\lezioni` and library `~\mba-studio\library`. Both are outside this OneDrive repository. There is no `config.toml` requirement: `config.load_settings` uses `Settings` defaults when the file is missing.

## Quick start

From the repository root, in PowerShell:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
uv run lecture-study watch
```

`lecture-study once` processes the stable files and exits. A recording is ignored until its size and mtime have stayed still for 30 seconds.

The logon task `LectureStudyWatch` already runs `uv run --project` this repository with `lecture-study watch`. Do not start a second `once` while that task is running.

## Running the tests

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run pytest -q
```
