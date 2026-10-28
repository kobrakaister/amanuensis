from lecture_study.jobs import Job, JobState, Status


def test_new_job_has_no_completed_stages(tmp_path):
    assert Job(tmp_path / "abc").load_state() == JobState()


def test_state_round_trip(tmp_path):
    job = Job(tmp_path)
    state = JobState(completed=["accept"], status=Status.WAITING, stage="analyze", message="m", events=["e"])
    job.save_state(state)
    assert job.load_state() == state


def write(job, *names):
    for name in names:
        job.file(name).write_text("x", encoding="utf-8")


def test_missing_state_is_rebuilt_from_final_files(tmp_path):
    job = Job(tmp_path)
    job.write_source({"sha256": "x", "analysis": {"ratio": 0.2}})
    write(job, "transcript.json", "transcript.md", "notes.md")
    assert job.load_state().completed == ["accept", "analyze", "prepare", "transcribe", "notes"]


def test_rebuild_stops_at_first_missing_stage(tmp_path):
    job = Job(tmp_path)
    job.write_source({"sha256": "x"})
    write(job, "notes.md")
    assert job.load_state().completed == ["accept"]


def test_prepared_wav_proves_preparation(tmp_path):
    job = Job(tmp_path)
    job.write_source({"sha256": "x", "analysis": {}})
    job.work_dir.mkdir()
    job.prepared_wav.write_bytes(b"RIFF")
    assert job.load_state().completed == ["accept", "analyze", "prepare"]


def test_partial_output_is_not_a_completed_stage(tmp_path):
    job = Job(tmp_path)
    job.write_source({"sha256": "x", "analysis": {}})
    write(job, "transcript.json", "transcript.md", "notes.partial.md")
    assert job.load_state().completed[-1] == "transcribe"
