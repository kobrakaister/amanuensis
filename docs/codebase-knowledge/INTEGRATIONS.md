# Integrations

## External services

- ffmpeg and ffprobe. `audio.probe` runs ffprobe and reads JSON. `audio.analyze` pipes 8 kHz f32le from ffmpeg. `audio.prepare_command` builds the ffmpeg command that writes mono 16 kHz PCM s16le, with an optional `highpass` filter.
- Ollama HTTP on loopback. `llm.OllamaClient.complete` POSTs `/api/chat` with `stream` false, `options.num_ctx` from `Settings.ollama_num_ctx`, and temperature 0.2. Timeout is `Settings.ollama_timeout_seconds`. Status 404 or 500 and above, and connection or timeout errors, become `TransientError`. Status 400 propagates. `OllamaClient.release` POSTs `/api/generate` with `keep_alive` 0.
- faster-whisper downloads `Systran/faster-whisper-large-v3` into the Hugging Face hub cache on first use. `transcribe.add_nvidia_library_dirs` adds the `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` `bin` directories before the model loads. Compute type is `int8_float16` on CUDA and `int8` on CPU.
- No database, queue, or cloud transcription client exists in `src/lecture_study/`.

## Contracts and schemas

- `source.json`: path, sha256, size, duration, format, `analysis` (low, voice, ratio, threshold, highpass_hz, apply), `preparation`, `transcription` (language, language_probability, model, device). Written by the pipeline handlers and read by `report.render_report`.
- `state.json`: `jobs.JobState` fields `completed`, `status`, `stage`, `message`, `events`.
- `transcript.md`: a title and lines `[hh:mm:ss] text` from `transcribe.render_transcript`. `transcript.json` stores the segment list.
- Study files, when accepted: `notes.md`, `mindmap.md`, `questions.md`. A rejected generation is `{stage}.partial.md`.
- `library/index.json`: `scanner.HashIndex` cache.
- `eval/eval_asr.py` writes `results.csv` and `summary.json` for WER and CER. It is not a pipeline output.

## Environment variables

The application reads these:

- `OneDrive`, `OneDriveCommercial`, `OneDriveConsumer`: `config.onedrive_roots` uses whichever are set, to reject those directories.
- No Hugging Face token is read. Downloads work unauthenticated until the hub rate-limits them.

These are process setup, not read by `lecture_study`:

- `UV_PROJECT_ENVIRONMENT`: must be `~\mba-studio\.venv` so `uv run` uses Python 3.12.9.
- `OLLAMA_HOST`: the live server was started as `127.0.0.1:11435`. The code default is `Settings.ollama_url`, which matches that host and port.
- `HF_HUB_DISABLE_SYMLINKS_WARNING`: silences the Windows symlink warning. It does not change results.
