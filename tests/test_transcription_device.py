import pytest

from lecture_study.errors import GpuOutOfMemory
from lecture_study.jobs import Status
from lecture_study.scanner import Recording
from test_pipeline import SHA, FakeTranscriber, job, make_pipeline


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "lezioni" / "strategia.m4a"
    path.parent.mkdir()
    path.write_bytes(b"audio")
    return Recording(path, 5, 1)


def test_missing_cuda_transcribes_on_cpu_without_retries(tmp_path, recording):
    sleeps = []
    transcriber = FakeTranscriber()
    state = make_pipeline(tmp_path, transcriber=transcriber, sleeps=sleeps, cuda_available=lambda: False).process(recording, SHA)
    assert state.status == Status.DONE
    assert transcriber.devices == ["cpu"]
    assert sleeps == []
    assert job(tmp_path).read_source()["transcription"]["device"] == "cpu"


def test_two_cuda_out_of_memory_errors_then_use_cpu(tmp_path, recording):
    sleeps = []
    transcriber = FakeTranscriber(failures=[GpuOutOfMemory("CUDA out of memory"), GpuOutOfMemory("CUDA out of memory")])
    state = make_pipeline(tmp_path, transcriber=transcriber, sleeps=sleeps, cuda_available=lambda: True).process(recording, SHA)
    assert state.status == Status.DONE
    assert transcriber.devices == ["cuda", "cuda", "cpu"]
    assert sleeps == [15, 30]
    assert job(tmp_path).read_source()["transcription"]["device"] == "cpu"
