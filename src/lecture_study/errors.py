class TransientError(Exception):
    pass


class GpuOutOfMemory(TransientError):
    pass


class RetriesExhausted(Exception):
    pass


class UnreadableAudio(Exception):
    pass


class RecordingMissing(Exception):
    pass


class InsufficientSpace(Exception):
    pass


class InvalidModelOutput(Exception):
    def __init__(self, message: str, partial: str) -> None:
        super().__init__(message)
        self.partial = partial
