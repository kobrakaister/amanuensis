from typing import Callable, TypeVar

from lecture_study.errors import RetriesExhausted, TransientError

T = TypeVar("T")
OnRetry = Callable[[TransientError, int, int], None]


def call_with_retries(
    operation: Callable[[], T],
    *,
    delays: tuple[int, ...],
    sleep: Callable[[float], None],
    on_retry: OnRetry | None = None,
) -> T:
    for retry, delay in enumerate(delays, start=1):
        try:
            return operation()
        except TransientError as exc:
            if on_retry is not None:
                on_retry(exc, retry, delay)
            sleep(delay)
    try:
        return operation()
    except TransientError as exc:
        raise RetriesExhausted(str(exc)) from exc
