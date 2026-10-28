import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

from lecture_study.transcribe import FasterWhisperTranscriber


def main() -> int:
    model_name = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "tone.wav"
        samples = np.arange(16000 * 5) / 16000
        pcm = (0.2 * np.sin(2 * np.pi * 220 * samples) * 32767).astype("<i2")
        with wave.open(str(wav), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(pcm.tobytes())
        started = time.perf_counter()
        transcript = FasterWhisperTranscriber(model_name).transcribe(wav, device="cuda")
        print(f"device={transcript.device} language={transcript.language} seconds={time.perf_counter() - started:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
