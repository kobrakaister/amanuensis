# Conventions

## Naming

- Package and modules are English: `lecture_study.pipeline`, `lecture_study.study`.
- The page, reports, logs, and errors are English. `prompts.PROMPTS` still has `it` and `en`, so notes follow the lecture language.
- Stages and statuses are lowercase strings on `jobs.Stage` and `jobs.Status` (`needs_review`, `waiting`).
- Settings fields in `config.Settings` match the TOML keys. `config.load_settings` rejects unknown keys.

## Error handling

- Expected failures are types in `lecture_study.errors`: `TransientError`, `GpuOutOfMemory`, `RetriesExhausted`, `UnreadableAudio`, `RecordingMissing`, `InsufficientSpace`, `InvalidModelOutput`.
- `retry.call_with_retries` retries only `TransientError`. Other exceptions propagate. Delays come from `Settings.retry_delays`.
- `pipeline.Pipeline.process` maps those types to a status. A bare `Exception` becomes `failed` with `unexpected error` and does not advance the stage.
- `config.ConfigError` is raised by `config.validate` and printed by `cli.main` with exit code 2, before directories are created.
- `InvalidModelOutput.partial` is the text that was rejected. The pipeline stores it as `{stage}.partial.md`.

## Logging

- `cli.configure_logging` writes INFO lines to `library/lecture-study.log` and to stderr. Format is `asctime level name message`.
- `cli.main` logs `watching {watch_dir}` when the command is `watch`.
- `Pipeline.process` logs `job {sha256[:12]} path=... stage=... status=...` on the logger `lecture_study.pipeline`.
- `cli.scan_once` logs a warning and skips the file when hashing raises `OSError`.

## Testing

- pytest, configured in `pyproject.toml` with `testpaths = ["tests"]`.
- Tests call the functions directly. HTTP and ffmpeg are faked except `tests` that round-trip containers through the local ffmpeg.
- Run with the project virtualenv: `uv run pytest -q` from the repository root. The environment variable `UV_PROJECT_ENVIRONMENT` must point at `~\mba-studio\.venv`.

## Commits and merge requests

History on `feat/lecture-study-pipeline` uses conventional commits (`feat:`, `docs:`). The remote is `https://github.com/kobrakaister/amanuensis.git`. Do not push unless asked.
