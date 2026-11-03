import pytest

from lecture_study.audio import ProbeResult
from lecture_study.hold import resume
from lecture_study.jobs import JobState, Status
from lecture_study.scanner import Recording
from test_pipeline import SHA, job, make_pipeline

OTHER = "b" * 64


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "lezioni" / "strategia.m4a"
    path.parent.mkdir()
    path.write_bytes(b"audio")
    return Recording(path, 5, 1)


def test_stop_during_accept_holds_the_queue_until_resume(tmp_path, recording):
    hold = tmp_path / "hold.json"
    other = tmp_path / "lezioni" / "altra.m4a"
    other.write_bytes(b"altro")
    other_recording = Recording(other, 5, 2)

    def probe(path, *, ffprobe):
        hold.write_text("{}\n", encoding="utf-8")
        return ProbeResult(9.0, "mov,mp4,m4a")

    state = make_pipeline(tmp_path, probe=probe, hold_path=hold).process(recording, SHA)
    current = job(tmp_path)
    assert state.status == Status.STOPPED
    assert state.completed == ["accept"]
    assert current.file("source.json").exists()
    assert not current.file("transcript.md").exists()
    assert not (tmp_path / "library" / OTHER).exists()
    make_pipeline(tmp_path, hold_path=hold).process(other_recording, OTHER)
    assert not (tmp_path / "library" / OTHER).exists()

    assert make_pipeline(tmp_path, hold_path=hold).process(recording, SHA).status == Status.STOPPED
    assert job(tmp_path).load_state().completed == ["accept"]

    resume(hold, current)
    assert not hold.exists()
    assert make_pipeline(tmp_path, hold_path=hold).process(recording, SHA).status == Status.DONE
    assert "analyze" in job(tmp_path).load_state().completed
    assert make_pipeline(tmp_path, hold_path=hold).process(other_recording, OTHER).status == Status.DONE


def test_idle_hold_blocks_a_restart_until_resume(tmp_path, recording):
    hold = tmp_path / "hold.json"
    hold.write_text("{}\n", encoding="utf-8")
    make_pipeline(tmp_path, hold_path=hold).process(recording, SHA)
    assert not job(tmp_path).state_path.exists()
    make_pipeline(tmp_path, hold_path=hold).process(recording, SHA)
    assert not job(tmp_path).state_path.exists()
    resume(hold, job(tmp_path))
    assert not hold.exists()
    assert make_pipeline(tmp_path, hold_path=hold).process(recording, SHA).status == Status.DONE


@pytest.mark.parametrize("status", [Status.FAILED, Status.NEEDS_REVIEW, Status.WAITING, Status.PAUSED])
def test_resume_leaves_other_statuses_unchanged(tmp_path, recording, status):
    current = job(tmp_path)
    current.dir.mkdir(parents=True)
    current.save_state(JobState(completed=["accept"], status=status, message="resta"))
    hold = tmp_path / "hold.json"
    hold.write_text("{}\n", encoding="utf-8")
    resume(hold, current)
    assert current.load_state().status == status
    assert current.load_state().message == "resta"
