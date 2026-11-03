# Lecture study

Lecture study turns a lecture recording into a study pack on this PC. It transcribes the audio, then writes notes, a mind map, and review questions. The recording stays where it is. The text produced from it stays on this machine.

Each finished job is a directory named by the SHA-256 of the audio. It contains `transcript.md`, `transcript.json`, `notes.md`, `mindmap.md`, `questions.md`, and `report.md`, plus `source.json` and `state.json`. A later run skips a stage that already has its files.

If the lecture is detected as Italian, the notes, mind map, and questions are in Italian. An English lecture stays in English.

## Requirements

- Windows or macOS.
- About 15 GB free on the profile disk, outside OneDrive. The first run downloads Whisper `large-v3` into `~/mba-studio/hf`.
- `ffmpeg` and `ffprobe` on `PATH`. On macOS, install them yourself. The pin file has no macOS ffmpeg archive.
- Ollama already listening on `http://127.0.0.1:11435`, with the model `qwen2.5:7b`. If an older Ollama is on port 11434, leave it alone. This program does not install Ollama and does not use that port.
- Python 3.12, installed by `uv` inside `~/mba-studio`. Do not create a virtual environment in the repository.

An NVIDIA GPU speeds up transcription. Without CUDA, transcription uses the CPU. With CUDA, two out-of-memory errors move later attempts to the CPU.

You do not need Docker or an administrator account. GPU drivers stay as they are.

## Install and start

Clone this repository. From its root, on Windows:

```powershell
scripts\studio.cmd
```

On macOS:

```sh
sh scripts/studio.sh
```

The script downloads `uv` 0.11.16 into `~/mba-studio/bin` when that binary is missing or the checksum does not match. It keeps the Python environment, the interpreter, and the `uv` cache inside `~/mba-studio`, then runs `lecture-study up`.

`up` opens `http://127.0.0.1:8765/` on this PC only and keeps watching the audio folder. If port 8765 is already taken, it stops before reading audio. If the browser does not open, the address stays in the terminal. The page answers while Whisper is still downloading. The browser opens when that download finishes.

Deleting `~/mba-studio` removes the environment, the models, and the default library. The code stays in the repository.

## Choose the folders

The page asks for an audio folder and a results folder. If you have not chosen any, the defaults are `~/mba-studio/lezioni` and `~/mba-studio/library`. Press "Use these folders". The audio files are not copied.

You can point the audio field at one file. Only that file is processed, even when other audio sits next to it. The same limit is `lecture-study up --file <path>`.

These choices are rejected, and the previous paths stay:

- a folder inside OneDrive
- a network drive
- a results folder inside the audio folder

Programs and models stay in `~/mba-studio`. The page does not move them.

A file starts after 30 seconds with no change in size or modification time. The next check comes within about a minute.

## Stop and resume

"Stop" holds the queue. The stage already running finishes. Whisper and Ollama are not cut off in the middle of a call. Later stages of that file do not start, and neither do the other files. "Resume" continues from the first stage that was not saved.

"Resume" is shown when the queue is held, or on a row whose status is `stopped`. `failed`, `needs_review`, `waiting`, and `paused` do not get that button.

The table lists each audio file with its stage and status. Links to `report.md`, `transcript.md`, `notes.md`, `mindmap.md`, and `questions.md` appear once those files exist.

## Other commands

From the repository root, after the studio environment exists:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run lecture-study once
uv run lecture-study watch
```

`once` processes stable files and exits. `watch` keeps running. Do not start a second `once` or `watch` on a folder that is already being watched.

`up` accepts `--config` for a TOML file other than `~/mba-studio/config.toml`. If that file is missing, `up` creates it. If it already exists, `up` does not rewrite it. A new config points at `ffmpeg` and `ffprobe` in `~/mba-studio/bin` when those binaries are already there. Otherwise it uses the names `ffmpeg` and `ffprobe` from `PATH`. The Ollama address written into a new config is `http://127.0.0.1:11435`.

## Where the studio keeps data

| Path | Contents |
|---|---|
| `~/mba-studio/bin` | `uv`, downloaded by the script |
| `~/mba-studio/.venv` | Python packages |
| `~/mba-studio/python` | interpreter installed by `uv` |
| `~/mba-studio/cache` | `uv` cache |
| `~/mba-studio/hf` | Whisper `large-v3` |
| `~/mba-studio/lezioni` | default audio folder |
| `~/mba-studio/library` | default results |
| `~/mba-studio/config.toml` | created only when missing |
| `~/mba-studio/hold.json` | present while the queue is held |

## Tests

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run pytest -q
```

If the page is already open, the test that binds port 8765 fails. Close `up` and start it again.

Module layout is in `docs/codebase-knowledge/`.
