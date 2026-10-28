import pytest

from lecture_study.errors import RetriesExhausted, TransientError
from lecture_study.retry import call_with_retries

DELAYS = (15, 30, 60, 120, 240)


def test_first_success_does_not_wait():
    sleeps = []
    assert call_with_retries(lambda: "ok", delays=DELAYS, sleep=sleeps.append) == "ok"
    assert sleeps == []


def test_five_retries_with_configured_waits_then_gives_up():
    calls = []
    sleeps = []

    def always_busy():
        calls.append(1)
        raise TransientError("GPU occupata")

    with pytest.raises(RetriesExhausted, match="GPU occupata"):
        call_with_retries(always_busy, delays=DELAYS, sleep=sleeps.append)
    assert len(calls) == 6
    assert sleeps == [15, 30, 60, 120, 240]


def test_recovers_after_one_transient_failure():
    outcomes = [TransientError("timeout"), "ok"]
    events = []

    def flaky():
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    result = call_with_retries(
        flaky,
        delays=DELAYS,
        sleep=lambda seconds: None,
        on_retry=lambda error, retry, delay: events.append((str(error), retry, delay)),
    )
    assert result == "ok"
    assert events == [("timeout", 1, 15)]


def test_other_errors_are_not_retried():
    sleeps = []

    def broken():
        raise ValueError("bug")

    with pytest.raises(ValueError):
        call_with_retries(broken, delays=DELAYS, sleep=sleeps.append)
    assert sleeps == []
