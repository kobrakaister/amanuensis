# Starting

The program reads lecture audio on this PC, transcribes it, and writes notes, a mind map, and questions. The code stays in this repository. Downloaded programs and data stay in `~/mba-studio`, outside OneDrive. Deleting that folder removes the environment, the models, and the default library. The code stays in the repository.

You do not need Docker or an administrator account. GPU drivers, if any are installed, stay as they are. The script does not use the `uv` installer in the user profile, and it does not contact port 11434.

## What you need

- Windows or macOS.
- About 15 GB free on the profile disk, outside OneDrive. The first run downloads Whisper `large-v3`.
- `ffmpeg` and `ffprobe` on `PATH`. On macOS, install them separately. The macOS archives are not in the pin file.
- Ollama listening on `http://127.0.0.1:11435` with the model `qwen2.5:7b`. If an older Ollama is already on port 11434, leave it there.
- Python 3.12. `uv` installs it inside `~/mba-studio`. Do not create an environment in the repository.

An NVIDIA GPU speeds up transcription. Without CUDA, the first attempt uses the CPU. With CUDA, two out-of-memory errors move later attempts to the CPU.

## Folders

| Path | Contents |
|---|---|
| `~/mba-studio/bin` | `uv`, downloaded by the script |
| `~/mba-studio/.venv` | Python packages |
| `~/mba-studio/python` | interpreter installed by `uv` |
| `~/mba-studio/cache` | `uv` cache |
| `~/mba-studio/hf` | Whisper `large-v3` |
| `~/mba-studio/lezioni` | default audio folder, unless you choose another |
| `~/mba-studio/library` | default results |
| `~/mba-studio/config.toml` | created only when missing |
| `~/mba-studio/hold.json` | present while the queue is held |

If `config.toml` is missing, `up` creates it. When `~/mba-studio/bin` already contains `ffmpeg` and `ffprobe`, the file points at those binaries. Otherwise it uses the names `ffmpeg` and `ffprobe` from `PATH`. The Ollama address stays `http://127.0.0.1:11435`. If the file already exists, startup does not rewrite it.

## Setup

From the repository, on Windows:

```powershell
scripts\studio.cmd
```

On macOS:

```sh
sh scripts/studio.sh
```

The script downloads `uv` 0.11.16 into `~/mba-studio/bin` when the binary is missing or the checksum does not match. It sets `UV_PROJECT_ENVIRONMENT`, `UV_PYTHON_INSTALL_DIR`, and `UV_CACHE_DIR` inside `~/mba-studio`, then runs `lecture-study up`.

`up` opens `http://127.0.0.1:8765/` on this PC only. If that port is taken, it stops before reading any audio. If the browser does not open, the address stays in the terminal. The page answers while Whisper is still downloading. The browser opens when that download finishes.

On the page, choose the audio folder and the results folder, then press "Use these folders". Files are not copied. A folder inside OneDrive, a network drive, or a results folder inside the audio folder is rejected, and the previous paths stay. A file starts after 30 seconds with no change in size or modification time. The next check comes within about a minute.

The table lists each audio file with its stage and status. "Stop" holds the queue. The stage already started finishes, and later stages do not start. "Resume" appears when the queue is held, or on a lecture whose status is `stopped`. `failed`, `needs_review`, `waiting`, and `paused` do not get a "Resume" button.

## Other commands

From the repository root, with the studio environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run lecture-study once
uv run lecture-study watch
```

`once` processes stable files and exits. `watch` keeps running. On this PC the task `LectureStudyWatch` may already be running `watch`. Do not start a second `once` or `watch` on the same folder.

## Tests

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run pytest -q
```

If the page is already open, the test that binds port 8765 fails. Close `up` and start it again.
