# Patterns

## Recurring abstractions

- `llm.LanguageModel` is the only model interface. `OllamaClient.complete` is the v1 implementation. A second backend would implement `complete` and `release`.
- `transcribe.Transcriber` is the transcription protocol. `FasterWhisperTranscriber` is the implementation used by `cli.build_pipeline`.
- `study.StudyComposer._generate` calls the model, strips a surrounding fence with `_strip_fence`, checks a predicate, and tries once more. The predicates are `notes_are_valid`, `mindmap_is_valid`, and `questions_are_valid`.
- `atomic.write_text_atomic` writes a temporary file, flushes, and `os.replace`s it into place. `atomic.write_json_atomic` uses it for JSON.

## State management

- One lecture is one directory: `jobs.Job` at `library/<sha256>/`.
- `jobs.JobState` in `state.json` holds `completed`, `status`, `stage`, `message`, and `events`.
- `jobs.STAGE_FILES` says which final files prove a stage. `Job.load_state` rebuilds `completed` from those files when `state.json` is missing, and stops at the first gap. `notes.partial.md` does not count as notes.
- `Pipeline.process` advances `completed` only after the stage handler returns. A failed write of the final file leaves the stage incomplete.

## Data access

- The recording is read in place. `scanner.sha256_file` hashes the bytes. Nothing in the pipeline moves or rewrites the source.
- `jobs.Job.read_source` and `write_source` use `source.json` for path, digest, duration, analysis, and transcription metadata.
- Prepared audio is `work/prepared.wav` inside the job directory. `Pipeline._transcribe` deletes the work directory after a successful transcript write.
- `scanner.HashIndex` caches digests in `library/index.json` by path, size, and mtime.

## Adding a typical feature

The design in `docs/superpowers/` decides the behavior. For a new stage, the existing shape is:

1. Add a `jobs.Stage` value and, if it has a final file, an entry in `STAGE_FILES`.
2. Add a handler on `Pipeline` and register it in `_handlers`.
3. Write the final file with `atomic.write_text_atomic` before the handler returns.
4. Add a pytest that fails when the file is missing or the status is wrong.
