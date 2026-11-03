import pytest

from lecture_study import pipeline as pipeline_module
from lecture_study.audio import BandEnergy, Prepared, ProbeResult
from lecture_study.config import Settings
from lecture_study.errors import GpuOutOfMemory, TransientError, UnreadableAudio
from lecture_study.jobs import Job, Status
from lecture_study.pipeline import Pipeline
from lecture_study.scanner import Recording
from lecture_study.transcribe import Segment, Transcript

SHA = "a" * 64
NOTES = "## Tema\n- Punto [00:00:00]"
MINDMAP = "# Lezione\n## Tema\n- Punto"
QUESTIONS = "\n\n".join(f"### {i}. Domanda {i}?\nRisposta attesa: r.\nRiferimento: [00:00:0{i}]" for i in range(1, 6))


class FakeTranscriber:
    def __init__(self, failures=()):
        self.failures = list(failures)
        self.devices = []

    def transcribe(self, wav, *, device):
        self.devices.append(device)
        assert wav.exists()
        if self.failures:
            raise self.failures.pop(0)
        segments = (Segment(0.0, 5.0, "Oggi parliamo di strategia."), Segment(5.0, 9.0, "Primo tema."))
        return Transcript("it", 0.97, "large-v3", device, segments)


class FakeModel:
    def __init__(self, replies=None, failures=0):
        self.replies = replies
        self.failures = failures
        self.calls = 0
        self.released = 0

    def complete(self, system, prompt):
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise TransientError("Ollama is unreachable")
        if self.replies is not None:
            return self.replies.pop(0)
        if "Trascrizione:" in prompt:
            return NOTES
        if "mappa mentale" in prompt:
            return MINDMAP
        return QUESTIONS

    def release(self):
        self.released += 1


class CountingProbe:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def __call__(self, path, *, ffprobe):
        self.calls += 1
        if self.error:
            raise self.error
        return ProbeResult(9.0, "mov,mp4,m4a")


def fake_prepare(source, work_dir, *, ffmpeg, highpass_hz):
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "prepared.wav"
    target.write_bytes(b"RIFF")
    return Prepared(target, highpass_hz is not None, "")


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "lezioni" / "strategia.m4a"
    path.parent.mkdir()
    path.write_bytes(b"audio")
    return Recording(path, 5, 1)


def make_pipeline(tmp_path, *, transcriber=None, model=None, probe=None, free=10**12, sleeps=None, cuda_available=None, hold_path=None):
    settings = Settings(watch_dir=tmp_path / "lezioni", library_dir=tmp_path / "library")
    return Pipeline(
        settings,
        transcriber=transcriber or FakeTranscriber(),
        model=model or FakeModel(),
        probe=probe or CountingProbe(),
        analyze=lambda path, *, ffmpeg: BandEnergy(low=2.0, voice=1.0),
        prepare=fake_prepare,
        free_bytes=lambda path: free,
        sleep=sleeps.append if sleeps is not None else (lambda seconds: None),
        cuda_available=cuda_available if cuda_available is not None else (lambda: True),
        hold_path=hold_path or (tmp_path / "hold.json"),
    )


def job(tmp_path):
    return Job(tmp_path / "library" / SHA)


def test_happy_path_produces_every_file_and_cleans_work_dir(tmp_path, recording):
    model = FakeModel()
    state = make_pipeline(tmp_path, model=model).process(recording, SHA)
    current = job(tmp_path)
    assert state.status == Status.DONE
    for name in ("source.json", "state.json", "transcript.json", "transcript.md", "notes.md", "mindmap.md", "questions.md", "report.md"):
        assert current.file(name).exists(), name
    assert not current.work_dir.exists()
    source = current.read_source()
    assert source["analysis"]["apply"] is True
    assert source["preparation"]["highpass_applied"] is True
    assert source["transcription"]["language"] == "it"
    assert "[00:00:00] Oggi parliamo di strategia." in current.file("transcript.md").read_text(encoding="utf-8")
    assert "- Status: done" in current.file("report.md").read_text(encoding="utf-8")
    assert model.released == 1
    assert recording.path.read_bytes() == b"audio"


def test_second_run_on_same_content_does_nothing(tmp_path, recording):
    make_pipeline(tmp_path).process(recording, SHA)
    transcriber, model = FakeTranscriber(), FakeModel()
    assert make_pipeline(tmp_path, transcriber=transcriber, model=model).process(recording, SHA).status == Status.DONE
    assert transcriber.devices == []
    assert model.calls == 0


def test_interruption_during_notes_keeps_transcript_and_resumes_from_notes(tmp_path, recording):
    sleeps = []
    state = make_pipeline(tmp_path, model=FakeModel(failures=6), sleeps=sleeps).process(recording, SHA)
    current = job(tmp_path)
    assert state.status == Status.WAITING
    assert state.stage == "notes"
    assert sleeps == [15, 30, 60, 120, 240]
    assert current.file("transcript.md").exists()
    assert not current.file("notes.md").exists()

    transcriber = FakeTranscriber()
    assert make_pipeline(tmp_path, transcriber=transcriber).process(recording, SHA).status == Status.DONE
    assert transcriber.devices == []
    assert current.file("questions.md").exists()


def test_two_gpu_out_of_memory_errors_switch_transcription_to_cpu(tmp_path, recording):
    sleeps = []
    out_of_memory = [GpuOutOfMemory("CUDA out of memory"), GpuOutOfMemory("CUDA out of memory")]
    transcriber = FakeTranscriber(failures=out_of_memory)
    state = make_pipeline(tmp_path, transcriber=transcriber, sleeps=sleeps).process(recording, SHA)
    assert state.status == Status.DONE
    assert transcriber.devices == ["cuda", "cuda", "cpu"]
    assert sleeps == [15, 30]
    assert job(tmp_path).read_source()["transcription"]["device"] == "cpu"
    assert any("CPU" in event for event in state.events)


def test_unreadable_audio_fails_and_is_not_retried(tmp_path, recording):
    probe = CountingProbe(error=UnreadableAudio("Invalid data found"))
    assert make_pipeline(tmp_path, probe=probe).process(recording, SHA).status == Status.FAILED
    assert make_pipeline(tmp_path, probe=probe).process(recording, SHA).status == Status.FAILED
    assert probe.calls == 1


def test_invalid_notes_need_review_and_resume_after_state_reset(tmp_path, recording):
    state = make_pipeline(tmp_path, model=FakeModel(replies=["niente", "ancora niente", "ancora niente"])).process(recording, SHA)
    current = job(tmp_path)
    assert state.status == Status.NEEDS_REVIEW
    assert current.file("notes.partial.md").read_text(encoding="utf-8") == "ancora niente\n"
    assert not current.file("notes.md").exists()

    model = FakeModel()
    assert make_pipeline(tmp_path, model=model).process(recording, SHA).status == Status.NEEDS_REVIEW
    assert model.calls == 0

    current.state_path.unlink()
    transcriber = FakeTranscriber()
    assert make_pipeline(tmp_path, transcriber=transcriber).process(recording, SHA).status == Status.DONE
    assert transcriber.devices == []
    assert not current.file("notes.partial.md").exists()


def test_missing_recording_pauses_and_resumes_from_new_path(tmp_path, recording):
    moved = tmp_path / "lezioni" / "corso" / "strategia.m4a"
    moved.parent.mkdir()
    recording.path.replace(moved)
    state = make_pipeline(tmp_path).process(recording, SHA)
    assert state.status == Status.PAUSED
    assert state.stage == "accept"

    assert make_pipeline(tmp_path).process(Recording(moved, 5, 1), SHA).status == Status.DONE
    assert job(tmp_path).read_source()["path"] == str(moved)


def test_insufficient_space_waits_before_preparation(tmp_path, recording):
    state = make_pipeline(tmp_path, free=0).process(recording, SHA)
    assert state.status == Status.WAITING
    assert state.stage == "prepare"
    assert "not enough disk space" in state.message


def test_state_does_not_advance_when_final_file_is_not_written(tmp_path, recording, monkeypatch):
    real_write = pipeline_module.write_text_atomic

    def failing_write(path, text):
        if path.name == "notes.md":
            raise OSError("disco pieno")
        real_write(path, text)

    monkeypatch.setattr(pipeline_module, "write_text_atomic", failing_write)
    state = make_pipeline(tmp_path).process(recording, SHA)
    assert state.status == Status.FAILED
    assert "OSError" in state.message
    assert job(tmp_path).load_state().completed[-1] == "transcribe"
    assert not job(tmp_path).file("notes.md").exists()
