# Workstreams

Living list of open work. Closed entries move to [the history](workstreams-history.md) in the
same turn they close.

Last updated: 2026-10-28

## Open

| Stream | Branch or worktree | State | Remaining work |
|---|---|---|---|
| Lecture study pipeline | `feat/lecture-study-pipeline` | Tasks 11–12 committed. Watch task `LectureStudyWatch` is running. Task 13 stopped at notes | A 10-minute Italian mTEDx concatenation (`mtedx-it-10min.wav`, SHA-256 `ddc2bdd3f86d0ce794a584192b38ef2d9232a23bd27ac707d8250ae0e5bfaa68`) transcribed on CUDA (`it` 0.98, about 3005 MiB). `qwen2.5:7b` notes have headings and no `[hh:mm:ss]`, so the job is `needs_review` and `notes.partial.md` only. Do not change the model or prompts until that text is reviewed. No 2–3 hour recording is available. The Ollama interruption test was not run. `eval/` is uncommitted and is not part of the pipeline. |

## Do not mix

Streams that must stay in separate branches or merge requests.
