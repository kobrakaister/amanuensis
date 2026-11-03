# Architecture

Local pipeline that turns one lecture recording into a study pack. Audio stays on this PC.
`lecture_study.cli:main` watches a folder; `lecture_study.pipeline:Pipeline.process` runs the stages.

## Main modules

```text
cli.main
  -> scanner.find_stable_recordings
  -> Pipeline.process
       accept -> analyze -> prepare -> transcribe -> notes -> mindmap -> questions
       llm.OllamaClient          transcribe.FasterWhisperTranscriber
       study.StudyComposer       report.render_report
       jobs.Job (library/<sha256>/)
```

- `lecture_study.cli:main` loads settings, creates the watch and library directories, and runs `once` or `watch`.
- `lecture_study.scanner:find_stable_recordings` lists accepted audio whose size and mtime have not changed.
- `lecture_study.pipeline:Pipeline` is the only stage runner. Handlers live in `_handlers`.
- `lecture_study.audio:prepare` writes a mono 16 kHz WAV. `lecture_study.transcribe:FasterWhisperTranscriber` reads that WAV.
- `lecture_study.study:StudyComposer` asks the language model for notes, a mind map, and questions.
- `lecture_study.jobs:Job` stores one lecture under `library/<sha256>/`.
- `lecture_study.report:render_report` writes `report.md` after every `process` return that saves state.

## Main execution flow

1. `cli.scan_once` asks `find_stable_recordings` for files in `Settings.watch_dir`.
2. `scanner.HashIndex.hash_of` returns the SHA-256 of the file bytes. That digest is the job identity.
3. `Pipeline.process` returns immediately when `JobState.status` is in `jobs.FINAL_STATUSES`.
4. Otherwise it sets status `running` and runs each `jobs.Stage` not already in `completed`.
5. Accept writes `source.json` and does not move the recording. Analyze stores band energy. Prepare writes `work/prepared.wav` when free space is at least `audio.required_free_bytes`. Transcribe writes `transcript.json` and `transcript.md`, then deletes the work directory.
6. Notes, mind map, and questions go through `StudyComposer` and `retry.call_with_retries`.
7. On success the status becomes `done`. `UnreadableAudio` becomes `failed`. `RetriesExhausted` and `InsufficientSpace` become `waiting`. `RecordingMissing` becomes `paused`. `InvalidModelOutput` writes `{stage}.partial.md` and becomes `needs_review`.
8. If a study stage ran, `OllamaClient.release` is called. `state.json` and `report.md` are written last.

## Top-level folders

- `src/lecture_study/`: the package.
- `tests/`: pytest suite.
- `scripts/`: `studio.cmd`, `studio.sh`, and `register-autostart.ps1`.
- `docs/codebase-knowledge/`: how the program is laid out and how to start it.
- `eval/`: a separate ASR word-error harness. It is not imported by `lecture_study`.

## Key dependencies and why

- `faster-whisper` in `pyproject.toml`: local transcription. `FasterWhisperTranscriber` uses model `Settings.whisper_model` (`large-v3`).
- `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` on Windows: CUDA libraries loaded by `transcribe.add_nvidia_library_dirs`.
- `numpy`: audio arrays passed to the model, because PyAV in this environment rejects `metadata_errors`. See `FasterWhisperTranscriber.transcribe`.
- ffmpeg and ffprobe are external programs named by `Settings.ffmpeg` and `Settings.ffprobe`. `audio.probe` and `audio.prepare` call them.
- Ollama is an external HTTP service. Only `llm.OllamaClient` is implemented behind `llm.LanguageModel`.
