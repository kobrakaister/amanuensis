from lecture_study.jobs import JobState, Status
from lecture_study.report import render_report


def test_report_lists_measures_decisions_and_events():
    state = JobState(
        completed=["accept", "analyze", "prepare", "transcribe"],
        status=Status.WAITING,
        stage="notes",
        message="Ollama non raggiungibile",
        events=["notes: Ollama non raggiungibile; ripetizione 1 tra 15 s"],
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
        "- Stato: waiting",
        "- Fase: notes",
        "- Durata: 01:30:00",
        "- Rapporto: 6.250 (soglia 1.0)",
        "- Decisione: applicare il passa-alto a 80 Hz",
        "- Applicato: sì",
        "- Lingua: it (probabilità 0.93)",
        "- Dispositivo: cuda",
        "- notes: Ollama non raggiungibile; ripetizione 1 tra 15 s",
    ):
        assert expected in report


def test_low_ratio_explains_what_the_filter_does_not_do():
    source = {"analysis": {"low": 0.01, "voice": 1.0, "ratio": 0.01, "threshold": 1.0, "highpass_hz": 80, "apply": False}}
    report = render_report(JobState(), source)
    assert "- Decisione: nessun passa-alto" in report
    assert "non riduce il rumore a banda larga" in report


def test_report_for_new_job():
    report = render_report(JobState(status=Status.PAUSED, stage="accept", message="registrazione non trovata"), {})
    assert "- Non ancora analizzato" in report
    assert "- Non ancora trascritto" in report
    assert "- Nessuno" in report
