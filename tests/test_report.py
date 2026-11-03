from lecture_study.jobs import JobState, Status
from lecture_study.report import render_report


def test_report_lists_measures_decisions_and_events():
    state = JobState(
        completed=["accept", "analyze", "prepare", "transcribe"],
        status=Status.WAITING,
        stage="notes",
        message="Ollama is unreachable",
        events=["notes: Ollama is unreachable; retry 1 in 15 s"],
    )
    source = {
        "path": "C:/lezioni/strategia.m4a",
        "sha256": "a" * 64,
        "duration_seconds": 5400.0,
        "format": "mov,mp4,m4a",
        "analysis": {"low": 2.0, "voice": 0.32, "ratio": 6.25, "threshold": 1.0, "highpass_hz": 80, "apply": True},
        "preparation": {"highpass_applied": True, "note": ""},
        "transcription": {"language": "it", "language_probability": 0.93, "model": "large-v3", "device": "cuda"},
    }
    report = render_report(state, source)
    for expected in (
        "- Status: waiting",
        "- Stage: notes",
        "- Duration: 01:30:00",
        "- Ratio: 6.250 (threshold 1.0)",
        "- Decision: apply high-pass at 80 Hz",
        "- Applied: yes",
        "- Language: it (probability 0.93)",
        "- Device: cuda",
        "- notes: Ollama is unreachable; retry 1 in 15 s",
    ):
        assert expected in report


def test_low_ratio_explains_what_the_filter_does_not_do():
    source = {"analysis": {"low": 0.01, "voice": 1.0, "ratio": 0.01, "threshold": 1.0, "highpass_hz": 80, "apply": False}}
    report = render_report(JobState(), source)
    assert "- Decision: no high-pass" in report
    assert "does not reduce broadband noise" in report


def test_report_for_new_job():
    report = render_report(JobState(status=Status.PAUSED, stage="accept", message="recording not found"), {})
    assert "- Not analyzed yet" in report
    assert "- Not transcribed yet" in report
    assert "- None" in report
