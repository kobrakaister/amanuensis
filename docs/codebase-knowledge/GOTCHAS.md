# Gotchas

## Critical invariants

- The library and the watch folder must be outside OneDrive and off a remote drive. `config.check_local_dir` enforces this. `config.validate` also rejects a library inside the watch folder, and an Ollama URL whose host is not in `config.LOOPBACK_HOSTS`.
- Identity is the content hash. Replacing `state.json` does not re-transcribe a lecture that already has `transcript.json` and `transcript.md`, because `Job.load_state` rebuilds completed stages from `jobs.STAGE_FILES`.
- `jobs.FINAL_STATUSES` includes `needs_review`. `Pipeline.process` will not retry that job until `state.json` is removed.
- `study.notes_are_valid` requires both a `## ` heading and a `[hh:mm:ss]` timestamp. Headings alone are rejected.
- After two `GpuOutOfMemory` errors, `Pipeline._transcribe` uses CPU. The threshold is `pipeline.OUT_OF_MEMORY_BEFORE_CPU`.
- A file is eligible only after `Settings.stable_seconds` (30) with unchanged size and mtime. `cli.main` scans every `Settings.scan_interval_seconds` (60).

## Looks wrong but is intentional

- `FasterWhisperTranscriber.transcribe` loads `WhisperModel` on every call. The eval client caches a model; the production class does not.
- `audio.should_highpass` is true only when energy(20–80 Hz) / energy(80–300 Hz) is at least `Settings.highpass_ratio_threshold` (1.0). A quiet low band does not enable a general denoiser.
- `prepare` falls back to an unfiltered WAV if the high-pass ffmpeg command fails. The source file is still not modified.
- Language detection uses the first `transcribe.LANGUAGE_SAMPLE_SECONDS` (60). `transcribe.choose_language` keeps `it` or `en` only when the probability is at least `MIN_LANGUAGE_PROBABILITY` (0.80); otherwise the language is `FALLBACK_LANGUAGE` (`it`).
- Tests for `OllamaClient` use `http://127.0.0.1:11434/`, which is not the live server. The live default is `Settings.ollama_url` (`http://127.0.0.1:11435`).

## Common traps

- Do not run `lecture-study once` while the scheduled task `LectureStudyWatch` is running. Both load `large-v3` onto the same GPU.
- Port 11434 is an older Ollama process. Leave it alone. The pipeline talks to 11435.
- `config.AUDIO_EXTENSIONS` is the allowlist. ffmpeg decodes; the work file is always mono 16 kHz PCM. This ffmpeg cannot mux AAC into CAF. PCM and ALAC CAF are accepted.
- `read_wav_mono` rejects anything that is not mono 16 kHz 16-bit PCM. Passing a phone recording straight to the transcriber raises `UnreadableAudio`.
- On 2026-10-28 a 10-minute Italian mTEDx concatenation (`library/ddc2bdd3f86d0ce794a584192b38ef2d9232a23bd27ac707d8250ae0e5bfaa68`) reached `needs_review` at notes. `notes.partial.md` has `## ` headings and no `[hh:mm:ss]` times. `prompts.PROMPTS["it"]["notes"]` already asks for those times. Do not change the prompt or the model until that result has been reviewed.
- `eval/` dependencies are not in `pyproject.toml`. Installing them into the project venv is a separate action.

## Files to leave alone without context

- `docs/superpowers/specs/2026-10-27-lecture-study-pipeline-design.md` and `docs/superpowers/plans/2026-10-27-lecture-study-pipeline.md` are the product decisions.
- `scripts/register-autostart.ps1` registers a logon task. It is already registered for this user.
- Do not read or commit `.ollama` keys. None live in this repository; the models directory is under the user profile.
