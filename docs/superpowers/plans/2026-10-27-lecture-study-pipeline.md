# Lecture Study Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un servizio locale che osserva una cartella di registrazioni e, per ogni lezione, produce trascrizione con tempi, appunti, mappa mentale, domande di ripasso e report, senza inviare audio o testo fuori dal PC.

**Architecture:** Un pacchetto Python (`src/lecture_study/`) con un modulo per responsabilità: scanner, archivio lavori, audio (ffprobe/ffmpeg), trascrizione (faster-whisper), modello linguistico (Ollama su loopback), composizione dello studio, report ed esecutore delle fasi. Ogni fase scrive il proprio file in modo atomico e solo dopo avanza `state.json`; Whisper e Ollama stanno dietro interfacce sostituibili nei test.

**Tech Stack:** Python 3.12, uv, numpy, faster-whisper (CTranslate2, CUDA 12, cuDNN 9), ffmpeg/ffprobe, Ollama con `qwen2.5:7b`, pytest.

Specifica: `docs/superpowers/specs/2026-10-27-lecture-study-pipeline-design.md`.

## Global Constraints

- L'audio e il testo delle lezioni non escono dal PC. `ollama_url` deve avere host `127.0.0.1`, `localhost` o `::1`.
- Cartella osservata predefinita: `C:\Users\Mathia.Scucchiari\mba-studio\lezioni` (`Path.home() / "mba-studio" / "lezioni"`).
- Archivio predefinito: `C:\Users\Mathia.Scucchiari\mba-studio\library` (`Path.home() / "mba-studio" / "library"`).
- All'avvio vengono rifiutati cartella osservata o archivio dentro OneDrive o su un disco di rete; l'archivio non può stare dentro la cartella osservata.
- La registrazione non viene mai spostata né modificata. L'identità della lezione è lo SHA-256 del contenuto.
- Formati accettati, anche nelle sottocartelle e senza distinzione di maiuscole: `.wav`, `.aiff`, `.aif`, `.caf`, `.mp3`, `.m4a`, `.mp4`, `.aac`, `.3gp`, `.3gpp`, `.amr`, `.ogg`, `.opus`, `.webm`, `.flac`. ffmpeg decodifica il contenitore; il WAV di lavoro è sempre mono a 16 kHz. Un contenitore accettato ma illeggibile resta `failed`.
- Un file è stabile quando la sua data di modifica ha almeno 30 secondi. Una lezione alla volta, dalla più vecchia.
- Passa-alto `highpass=f=80` solo se energia(20–80 Hz) / energia(80–300 Hz) >= 1.0.
- WAV di lavoro: mono, 16 kHz, PCM 16 bit, in `work\`, rimosso dopo la trascrizione riuscita. Spazio richiesto: `2 * 32000 * durata_in_secondi` byte.
- Lingua: rilevata sul primo minuto; `it` o `en` con probabilità >= 0.80, altrimenti `it`.
- Blocchi per gli appunti: al massimo 720 secondi, con 30 secondi ripetuti dal blocco precedente.
- Errori temporanei: la chiamata viene ripetuta fino a 5 volte, con attese 15, 30, 60, 120, 240 secondi, poi stato `waiting`. Dopo 2 esaurimenti della memoria video la trascrizione usa la CPU.
- Risposta del modello non valida: un solo nuovo tentativo, poi `needs_review` con `<fase>.partial.md`.
- `failed` e `needs_review` non vengono ritentati in automatico; eliminare `state.json` ricostruisce lo stato dai file finali.
- I log contengono percorso, hash, fase ed esito, mai il testo della lezione.
- L'ambiente virtuale sta fuori da OneDrive: `UV_PROJECT_ENVIRONMENT=C:\Users\Mathia.Scucchiari\mba-studio\.venv`.
- Ogni nuova dipendenza è verificata per CVE, supporto e licenza prima di essere aggiunta.
- Fuori scope: separazione dei parlanti, pagina web, Docker, cloud, domande interattive su più lezioni, denoise a banda larga.

## File Structure

| File | Responsabilità |
|---|---|
| `.gitignore` | Esclude ambiente, cache e qualsiasi file audio |
| `pyproject.toml` | Pacchetto, dipendenze, comando `lecture-study`, pytest |
| `docs/dependencies.md` | Registro delle dipendenze verificate |
| `src/lecture_study/__init__.py` | Versione del pacchetto |
| `src/lecture_study/errors.py` | Eccezioni condivise fra i moduli |
| `src/lecture_study/config.py` | `Settings`, lettura TOML, controllo dei percorsi e dell'URL |
| `src/lecture_study/atomic.py` | Scrittura atomica di testo e JSON |
| `src/lecture_study/retry.py` | Ripetizione delle chiamate con errori temporanei |
| `src/lecture_study/jobs.py` | Fasi, stati, `state.json`, ricostruzione dai file finali |
| `src/lecture_study/scanner.py` | Ricerca dei file stabili, SHA-256, indice degli hash |
| `src/lecture_study/audio.py` | ffprobe, analisi delle bande, preparazione del WAV |
| `src/lecture_study/transcribe.py` | Segmenti, scelta della lingua, faster-whisper |
| `src/lecture_study/llm.py` | Interfaccia del modello e client Ollama |
| `src/lecture_study/prompts.py` | Istruzioni in italiano e in inglese |
| `src/lecture_study/study.py` | Blocchi, validazione, appunti, mappa e domande |
| `src/lecture_study/report.py` | `report.md` |
| `src/lecture_study/pipeline.py` | Esecuzione delle fasi ed esiti |
| `src/lecture_study/cli.py` | Comandi `once` e `watch` |
| `scripts/gpu_check.py` | Prova di faster-whisper sulla GPU di questo PC |
| `scripts/register-autostart.ps1` | Avvio di `watch` all'accesso a Windows |
| `tests/test_*.py` | Un file di test per modulo |

---

### Task 0: Repository e strumenti di sistema

**Files:**
- Create: `.gitignore`
- Modify: `docs/workstreams.md`

**Interfaces:**
- Consumes: niente.
- Produces: repository Git su `main` e branch `feat/lecture-study-pipeline`; `ffmpeg`, `ffprobe`, `ollama` nel PATH; modello `qwen2.5:7b` scaricato; variabile `UV_PROJECT_ENVIRONMENT`.

- [x] **Step 1: Inizializza il repository**

Run (PowerShell, dalla radice del repository):

```powershell
git init -b main
```

Expected: `Initialized empty Git repository in .../MBA/.git/`

- [x] **Step 2: Crea `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
build/
*.wav
*.mp3
*.m4a
*.mp4
*.aac
*.flac
*.ogg
```

- [x] **Step 3: Sposta l'ambiente virtuale fuori da OneDrive**

```powershell
[Environment]::SetEnvironmentVariable('UV_PROJECT_ENVIRONMENT', "$env:USERPROFILE\mba-studio\.venv", 'User')
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
```

Run: `[Environment]::GetEnvironmentVariable('UV_PROJECT_ENVIRONMENT', 'User')`
Expected: `C:\Users\Mathia.Scucchiari\mba-studio\.venv`

- [x] **Step 4: Installa ffmpeg e Ollama**

```powershell
winget install --id Gyan.FFmpeg --exact --scope user
winget install --id Ollama.Ollama --exact --scope user
```

Riavvia Cursor perché il nuovo PATH sia visibile, poi:

Run: `ffmpeg -version; ffprobe -version; ollama --version`
Expected: tre righe di versione, nessun `not recognized`.

- [x] **Step 5: Verifica CVE delle due installazioni**

Il 2026-10-27 l'utente ha accettato di proseguire con FFmpeg 9.0.2 (CVE-2026-107696, CVE-2026-107678, CVE-2026-107677, CVE-2026-107676) e Ollama 0.40.11 (CVE-2026-7020). Non esiste una versione corretta installabile per questi advisory. L'uso resta locale.

Confronta la versione di `ollama --version` con <https://github.com/ollama/ollama/security/advisories> e la versione di `ffmpeg -version` con <https://ffmpeg.org/security.html>.
Expected: nessun advisory non corretto per le versioni installate. Se ce n'è uno, **STOP** e riporta all'utente versione e advisory.

- [x] **Step 6: Verifica che Ollama ascolti solo su questo PC**

La porta 11434 risponde come Ollama 0.24.0 e non accetta un secondo server. Ollama 0.40.11 ascolta su `127.0.0.1:11435` (`OLLAMA_HOST` dell'utente). Il valore predefinito di `ollama_url` è quindi `http://127.0.0.1:11435`.

Run:

```powershell
[Environment]::GetEnvironmentVariable('OLLAMA_HOST', 'User')
Get-NetTCPConnection -LocalPort 11434 -State Listen | Select-Object -ExpandProperty LocalAddress
```

Expected: la prima riga è vuota; la seconda è `127.0.0.1`. Se compare `0.0.0.0` o `::`, **STOP**: Ollama sarebbe raggiungibile dalla rete.

- [x] **Step 7: Scarica il modello linguistico**

Run: `ollama pull qwen2.5:7b`
Expected: termina con `success`. Poi `ollama list` mostra `qwen2.5:7b`.

- [x] **Step 8: Commit iniziale e branch di lavoro**

```powershell
git add -A
git commit -m "chore: initialise repository with kit and lecture pipeline design"
git switch -c feat/lecture-study-pipeline
```

- [x] **Step 9: Aggiorna `docs/workstreams.md`**

Sostituisci la riga dello stream con:

```markdown
| Lecture study pipeline | `feat/lecture-study-pipeline` | Implementation in progress | Execute `docs/superpowers/plans/2026-10-27-lecture-study-pipeline.md` from Task 1 |
```

```powershell
git add docs/workstreams.md
git commit -m "docs: track lecture study pipeline branch"
```

---

### Task 1: Scheletro del pacchetto e verifica delle dipendenze

**Files:**
- Create: `pyproject.toml`, `src/lecture_study/__init__.py`, `src/lecture_study/errors.py`, `tests/test_smoke.py`, `docs/dependencies.md`

**Interfaces:**
- Consumes: Task 0 (uv, `UV_PROJECT_ENVIRONMENT`).
- Produces: eccezioni `TransientError`, `GpuOutOfMemory(TransientError)`, `RetriesExhausted`, `UnreadableAudio`, `RecordingMissing`, `InsufficientSpace`, `InvalidModelOutput(message: str, partial: str)` con attributo `.partial`.

- [x] **Step 1: Scrivi il test che fallisce**

`tests/test_smoke.py`:

```python
import lecture_study
from lecture_study.errors import GpuOutOfMemory, InvalidModelOutput, TransientError


def test_package_version():
    assert lecture_study.__version__ == "0.1.0"


def test_gpu_out_of_memory_is_transient():
    assert issubclass(GpuOutOfMemory, TransientError)


def test_invalid_model_output_keeps_partial_text():
    error = InvalidModelOutput("risposta non valida per notes", "## parziale")
    assert str(error) == "risposta non valida per notes"
    assert error.partial == "## parziale"
```

- [x] **Step 2: Scrivi `pyproject.toml`**

```toml
[project]
name = "lecture-study"
version = "0.1.0"
description = "Pipeline locale che trasforma registrazioni di lezioni in materiale di studio"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
lecture-study = "lecture_study.cli:main"

[dependency-groups]
dev = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [x] **Step 3: Aggiungi le dipendenze**

```powershell
uv add numpy faster-whisper "nvidia-cublas-cu12; sys_platform == 'win32'" "nvidia-cudnn-cu12>=9,<10; sys_platform == 'win32'"
uv add --dev pytest
```

Expected: `uv.lock` creato; nessun errore di risoluzione.

- [x] **Step 4: Verifica CVE sull'insieme risolto**

```powershell
uv export --format requirements-txt --no-hashes --no-emit-project --output-file build/requirements.txt
uvx pip-audit --requirement build/requirements.txt --no-deps --disable-pip
```

Expected: `No known vulnerabilities found`. Se pip-audit elenca una vulnerabilità senza versione corretta, **STOP** e riporta pacchetto, versione e identificativo all'utente.

- [x] **Step 5: Raccogli licenze e versioni dirette**

```powershell
uv run --with pip-licenses pip-licenses --format=markdown --with-urls
uv tree --depth 1
```

Expected: licenze leggibili per ogni pacchetto. `nvidia-cublas-cu12` e `nvidia-cudnn-cu12` hanno licenza proprietaria NVIDIA: uso locale, nessuna redistribuzione.

- [x] **Step 6: Scrivi il registro `docs/dependencies.md`**

Usa le versioni stampate da `uv tree --depth 1` e le licenze dello step 5:

```markdown
# Dipendenze

Verificate con `pip-audit` il 2026-10-27. Nessuna viene redistribuita: il progetto gira solo su questo PC.

| Componente | Versione | Uso | Licenza | Fonte | Supporto | SBOM del fornitore |
|---|---|---|---|---|---|---|
| numpy | <versione da uv tree> | analisi delle bande audio | BSD-3-Clause | PyPI | rilasci attivi | non pubblicata |
| faster-whisper | <versione da uv tree> | trascrizione | MIT | PyPI, SYSTRAN | rilasci attivi | non pubblicata |
| nvidia-cublas-cu12 | <versione da uv tree> | GPU per CTranslate2 | NVIDIA proprietaria | PyPI, NVIDIA | CUDA 12 supportato | non pubblicata |
| nvidia-cudnn-cu12 | <versione da uv tree> | GPU per CTranslate2 | NVIDIA proprietaria | PyPI, NVIDIA | cuDNN 9 supportato | non pubblicata |
| pytest | <versione da uv tree> | test, solo sviluppo | MIT | PyPI | rilasci attivi | non pubblicata |
| ffmpeg | <versione da ffmpeg -version> | decodifica e filtro | LGPL/GPL | winget Gyan.FFmpeg | rilasci attivi | non pubblicata |
| Ollama | <versione da ollama --version> | modello linguistico locale | MIT | winget Ollama.Ollama | rilasci attivi | non pubblicata |
```

Sostituisci ogni `<versione ...>` con il valore reale prima del commit; il file non deve contenere segnaposto. Conferma con l'utente che questo registro è il formato voluto al posto di uno SBOM CycloneDX.

- [x] **Step 7: Scrivi il codice minimo**

`src/lecture_study/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/lecture_study/errors.py`:

```python
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
```

- [x] **Step 8: Esegui i test**

Run: `uv run pytest -q`
Expected: `3 passed`

- [x] **Step 9: Commit**

```powershell
git add pyproject.toml uv.lock src tests docs/dependencies.md
git commit -m "chore: add package skeleton and vetted dependencies"
```

---

### Task 2: Modulo di trascrizione e prova della GPU

**Files:**
- Create: `src/lecture_study/transcribe.py`, `tests/test_transcribe.py`, `scripts/gpu_check.py`

**Interfaces:**
- Consumes: `GpuOutOfMemory`, `TransientError` da `errors.py`.
- Produces:
  - `Segment(start: float, end: float, text: str)`
  - `Transcript(language: str, language_probability: float, model: str, device: str, segments: tuple[Segment, ...])`, con `to_json() -> dict` e `Transcript.from_json(data: dict) -> Transcript`
  - `Transcriber` (Protocol): `transcribe(wav: Path, *, device: str) -> Transcript`
  - `choose_language(detected: str, probability: float) -> str`
  - `format_timestamp(seconds: float) -> str` (`hh:mm:ss`)
  - `render_segments(segments: Sequence[Segment]) -> str`
  - `render_transcript(transcript: Transcript, title: str) -> str`
  - `read_wav_head(path: Path, seconds: int) -> np.ndarray`
  - `classify_runtime_error(exc: RuntimeError) -> Exception`
  - `FasterWhisperTranscriber(model_name: str)`

- [x] **Step 1: Scrivi i test che falliscono**

`tests/test_transcribe.py`:

```python
import wave

import numpy as np
import pytest

from lecture_study.errors import GpuOutOfMemory, TransientError
from lecture_study.transcribe import (
    Segment,
    Transcript,
    choose_language,
    classify_runtime_error,
    format_timestamp,
    read_wav_head,
    render_transcript,
)


@pytest.mark.parametrize(
    ("detected", "probability", "expected"),
    [("en", 0.95, "en"), ("it", 0.80, "it"), ("en", 0.79, "it"), ("fr", 0.99, "it")],
)
def test_choose_language(detected, probability, expected):
    assert choose_language(detected, probability) == expected


def test_format_timestamp():
    assert format_timestamp(3725.9) == "01:02:05"
    assert format_timestamp(0) == "00:00:00"


def test_render_transcript_lists_segments_with_times():
    transcript = Transcript("it", 0.97, "large-v3", "cuda", (Segment(0.0, 4.0, "Buongiorno."), Segment(65.0, 70.0, "Primo tema.")))
    assert render_transcript(transcript, "strategia") == "# strategia\n\n[00:00:00] Buongiorno.\n[00:01:05] Primo tema.\n"


def test_transcript_json_round_trip():
    transcript = Transcript("en", 0.91, "large-v3", "cpu", (Segment(1.5, 3.0, "Hello."),))
    assert Transcript.from_json(transcript.to_json()) == transcript


def test_out_of_memory_is_classified_as_gpu_out_of_memory():
    assert isinstance(classify_runtime_error(RuntimeError("CUDA failed with error out of memory")), GpuOutOfMemory)


def test_busy_gpu_is_transient_but_not_out_of_memory():
    error = classify_runtime_error(RuntimeError("CUDA failed with error device busy"))
    assert isinstance(error, TransientError) and not isinstance(error, GpuOutOfMemory)


def test_other_runtime_errors_are_left_alone():
    original = RuntimeError("bad model file")
    assert classify_runtime_error(original) is original


def test_read_wav_head_stops_at_available_audio(tmp_path):
    path = tmp_path / "short.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(np.zeros(32000, dtype="<i2").tobytes())
    samples = read_wav_head(path, 60)
    assert samples.dtype == np.float32
    assert samples.size == 32000
```

- [x] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_transcribe.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.transcribe'`

- [x] **Step 3: Scrivi `src/lecture_study/transcribe.py`**

```python
from __future__ import annotations

import importlib.util
import os
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np

from lecture_study.errors import GpuOutOfMemory, TransientError

SUPPORTED_LANGUAGES = ("it", "en")
FALLBACK_LANGUAGE = "it"
MIN_LANGUAGE_PROBABILITY = 0.80
LANGUAGE_SAMPLE_SECONDS = 60


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcript:
    language: str
    language_probability: float
    model: str
    device: str
    segments: tuple[Segment, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "model": self.model,
            "device": self.device,
            "segments": [asdict(segment) for segment in self.segments],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Transcript:
        return cls(
            language=data["language"],
            language_probability=float(data["language_probability"]),
            model=data["model"],
            device=data["device"],
            segments=tuple(Segment(**segment) for segment in data["segments"]),
        )


class Transcriber(Protocol):
    def transcribe(self, wav: Path, *, device: str) -> Transcript: ...


def choose_language(detected: str, probability: float) -> str:
    if detected in SUPPORTED_LANGUAGES and probability >= MIN_LANGUAGE_PROBABILITY:
        return detected
    return FALLBACK_LANGUAGE


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def render_segments(segments: Sequence[Segment]) -> str:
    return "\n".join(f"[{format_timestamp(segment.start)}] {segment.text}" for segment in segments)


def render_transcript(transcript: Transcript, title: str) -> str:
    return f"# {title}\n\n{render_segments(transcript.segments)}\n"


def read_wav_head(path: Path, seconds: int) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        frames = handle.readframes(handle.getframerate() * seconds)
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def classify_runtime_error(exc: RuntimeError) -> Exception:
    message = str(exc)
    if "out of memory" in message.lower():
        return GpuOutOfMemory(message)
    if "cuda" in message.lower():
        return TransientError(message)
    return exc


def add_nvidia_library_dirs() -> None:
    for package in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(package)
        except ModuleNotFoundError:
            continue
        for location in (spec.submodule_search_locations or []) if spec else []:
            bin_dir = Path(location) / "bin"
            if bin_dir.is_dir():
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


class FasterWhisperTranscriber:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def transcribe(self, wav: Path, *, device: str) -> Transcript:
        add_nvidia_library_dirs()
        from faster_whisper import WhisperModel

        compute_type = "int8_float16" if device == "cuda" else "int8"
        try:
            model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
            detected, probability, _ = model.detect_language(audio=read_wav_head(wav, LANGUAGE_SAMPLE_SECONDS))
            language = choose_language(detected, probability)
            segments, _ = model.transcribe(str(wav), language=language, beam_size=5, vad_filter=True)
            collected = tuple(
                Segment(round(segment.start, 2), round(segment.end, 2), segment.text.strip())
                for segment in segments
                if segment.text.strip()
            )
        except RuntimeError as exc:
            classified = classify_runtime_error(exc)
            if classified is exc:
                raise
            raise classified from exc
        return Transcript(language, round(probability, 3), self.model_name, device, collected)
```

- [x] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_transcribe.py -q`
Expected: `11 passed`

- [x] **Step 5: Scrivi `scripts/gpu_check.py`**

```python
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
```

- [x] **Step 6: Prova la GPU di questo PC**

Run: `uv run python scripts/gpu_check.py`
Expected: la prima esecuzione scarica il modello (circa 3 GB, solo il modello, nessun audio inviato) e termina con `device=cuda language=... seconds=...`.

Se compare un errore su `cudnn`, `cublas`, `CUDA` o un'architettura GPU non supportata (la RTX PRO 2000 è Blackwell), **STOP**. Riporta l'errore e chiedi all'utente se procedere con la sola CPU, con il modello `turbo` o con un'altra strada. Non continuare con i task successivi finché la scelta non è presa.

- [x] **Step 7: Commit**

```powershell
git add src/lecture_study/transcribe.py tests/test_transcribe.py scripts/gpu_check.py
git commit -m "feat: add faster-whisper transcription module and GPU check"
```

La prova GPU del 2026-10-28 ha stampato `device=cuda language=it seconds=8.7`. PyAV 19 non accetta `metadata_errors`, quindi la trascrizione riceve l'audio già letto in memoria.

---

### Task 3: Configurazione e scrittura atomica

**Files:**
- Create: `src/lecture_study/config.py`, `src/lecture_study/atomic.py`, `tests/test_config.py`, `tests/test_atomic.py`

**Interfaces:**
- Consumes: niente.
- Produces:
  - `Settings` (dataclass frozen) con i campi `watch_dir`, `library_dir`, `ffmpeg`, `ffprobe`, `highpass_hz`, `highpass_ratio_threshold`, `stable_seconds`, `scan_interval_seconds`, `whisper_model`, `ollama_url`, `ollama_model`, `ollama_num_ctx`, `ollama_timeout_seconds`, `retry_delays`
  - `ConfigError(ValueError)`, `AUDIO_EXTENSIONS`, `DEFAULT_CONFIG`, `DRIVE_REMOTE`
  - `validate(settings, *, roots: list[Path] | None = None, drive_type=windows_drive_type) -> None`
  - `load_settings(path: Path = DEFAULT_CONFIG) -> Settings`
  - `windows_drive_type(path: Path) -> int`
  - `write_text_atomic(path: Path, text: str) -> None`, `write_json_atomic(path: Path, data) -> None`, `read_json(path: Path)`

- [x] **Step 1: Scrivi i test che falliscono**

`tests/test_atomic.py`:

```python
import os

import pytest

from lecture_study.atomic import read_json, write_json_atomic, write_text_atomic


def test_write_text_atomic_replaces_content_and_leaves_no_temp_file(tmp_path):
    target = tmp_path / "notes.md"
    write_text_atomic(target, "uno")
    write_text_atomic(target, "due")
    assert target.read_text(encoding="utf-8") == "due"
    assert list(tmp_path.iterdir()) == [target]


def test_failed_rename_keeps_previous_content(tmp_path, monkeypatch):
    target = tmp_path / "notes.md"
    write_text_atomic(target, "uno")

    def failing_replace(source, destination):
        raise OSError("disco pieno")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        write_text_atomic(target, "due")
    assert target.read_text(encoding="utf-8") == "uno"


def test_json_round_trip_keeps_accents(tmp_path):
    target = tmp_path / "sub" / "source.json"
    write_json_atomic(target, {"titolo": "attività"})
    assert read_json(target) == {"titolo": "attività"}
    assert "attività" in target.read_text(encoding="utf-8")
```

`tests/test_config.py`:

```python
from pathlib import Path

import pytest

from lecture_study.config import DRIVE_REMOTE, ConfigError, Settings, load_settings, validate, windows_drive_type

DRIVE_FIXED = 3


def local(path):
    return DRIVE_FIXED


def test_valid_local_settings(tmp_path):
    validate(Settings(watch_dir=tmp_path / "lezioni", library_dir=tmp_path / "library"), roots=[], drive_type=local)


def test_rejects_directory_inside_onedrive(tmp_path):
    onedrive = (tmp_path / "OneDrive - Vertiv Co").resolve()
    settings = Settings(watch_dir=onedrive / "lezioni", library_dir=tmp_path / "library")
    with pytest.raises(ConfigError, match="OneDrive"):
        validate(settings, roots=[onedrive], drive_type=local)


def test_rejects_network_drive(tmp_path):
    settings = Settings(watch_dir=tmp_path / "lezioni", library_dir=tmp_path / "library")
    with pytest.raises(ConfigError, match="rete"):
        validate(settings, roots=[], drive_type=lambda path: DRIVE_REMOTE)


def test_unc_path_is_a_network_drive():
    assert windows_drive_type(Path(r"\\server\share\lezioni")) == DRIVE_REMOTE


def test_rejects_library_inside_watch_dir(tmp_path):
    settings = Settings(watch_dir=tmp_path, library_dir=tmp_path / "library")
    with pytest.raises(ConfigError, match="dentro la cartella osservata"):
        validate(settings, roots=[], drive_type=local)


def test_rejects_ollama_outside_this_pc(tmp_path):
    settings = Settings(watch_dir=tmp_path / "in", library_dir=tmp_path / "out", ollama_url="http://192.168.1.10:11434")
    with pytest.raises(ConfigError, match="questo PC"):
        validate(settings, roots=[], drive_type=local)


def test_rejects_non_positive_numbers(tmp_path):
    settings = Settings(watch_dir=tmp_path / "in", library_dir=tmp_path / "out", highpass_hz=0)
    with pytest.raises(ConfigError, match="numerici"):
        validate(settings, roots=[], drive_type=local)


def test_load_settings_reads_toml(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'watch_dir = "{(tmp_path / "in").as_posix()}"\n'
        f'library_dir = "{(tmp_path / "out").as_posix()}"\n'
        "highpass_hz = 100\n"
        "highpass_ratio_threshold = 2\n",
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.watch_dir == tmp_path / "in"
    assert settings.highpass_hz == 100
    assert settings.highpass_ratio_threshold == 2.0


def test_load_settings_rejects_unknown_key(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('colour = "blue"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="sconosciuta"):
        load_settings(config)


def test_load_settings_rejects_wrong_type(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('highpass_hz = "ottanta"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="highpass_hz"):
        load_settings(config)
```

- [x] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_atomic.py tests/test_config.py -q`
Expected: FAIL con `ModuleNotFoundError` per `lecture_study.atomic` e `lecture_study.config`.

- [x] **Step 3: Scrivi `src/lecture_study/atomic.py`**

```python
import json
import os
from pathlib import Path
from typing import Any


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json_atomic(path: Path, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
```

- [x] **Step 4: Scrivi `src/lecture_study/config.py`**

```python
from __future__ import annotations

import ctypes
import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

DEFAULT_ROOT = Path.home() / "mba-studio"
DEFAULT_CONFIG = DEFAULT_ROOT / "config.toml"
AUDIO_EXTENSIONS = frozenset({
    ".wav", ".aiff", ".aif", ".caf",
    ".mp3",
    ".m4a", ".mp4", ".aac",
    ".3gp", ".3gpp", ".amr",
    ".ogg", ".opus", ".webm",
    ".flac",
})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DRIVE_REMOTE = 4


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    watch_dir: Path = DEFAULT_ROOT / "lezioni"
    library_dir: Path = DEFAULT_ROOT / "library"
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    highpass_hz: int = 80
    highpass_ratio_threshold: float = 1.0
    stable_seconds: int = 30
    scan_interval_seconds: int = 60
    whisper_model: str = "large-v3"
    ollama_url: str = "http://127.0.0.1:11435"
    ollama_model: str = "qwen2.5:7b"
    ollama_num_ctx: int = 16384
    ollama_timeout_seconds: int = 600
    retry_delays: tuple[int, ...] = (15, 30, 60, 120, 240)


def onedrive_roots() -> list[Path]:
    names = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")
    return [Path(os.environ[name]).resolve() for name in names if os.environ.get(name)]


def windows_drive_type(path: Path) -> int:
    anchor = path.anchor
    if anchor.startswith("\\\\"):
        return DRIVE_REMOTE
    return ctypes.windll.kernel32.GetDriveTypeW(anchor)


def check_local_dir(path: Path, *, roots: list[Path], drive_type: Callable[[Path], int]) -> None:
    resolved = path.resolve()
    for root in roots:
        if resolved == root or root in resolved.parents:
            raise ConfigError(f"{path} è dentro OneDrive ({root})")
    if drive_type(resolved) == DRIVE_REMOTE:
        raise ConfigError(f"{path} è su un disco di rete")


def validate(
    settings: Settings,
    *,
    roots: list[Path] | None = None,
    drive_type: Callable[[Path], int] = windows_drive_type,
) -> None:
    roots = onedrive_roots() if roots is None else roots
    for path in (settings.watch_dir, settings.library_dir):
        check_local_dir(path, roots=roots, drive_type=drive_type)
    watch = settings.watch_dir.resolve()
    library = settings.library_dir.resolve()
    if library == watch or watch in library.parents:
        raise ConfigError("l'archivio non può stare dentro la cartella osservata")
    host = urlparse(settings.ollama_url).hostname
    if host not in LOOPBACK_HOSTS:
        raise ConfigError(f"ollama_url deve puntare a questo PC, non a {host}")
    numbers = (
        settings.highpass_hz,
        settings.highpass_ratio_threshold,
        settings.scan_interval_seconds,
        settings.ollama_num_ctx,
        settings.ollama_timeout_seconds,
    )
    if any(value <= 0 for value in numbers) or settings.stable_seconds < 0 or any(d < 0 for d in settings.retry_delays):
        raise ConfigError("valori numerici non validi")


def _convert(key: str, value: object, default: object) -> object:
    if isinstance(default, Path):
        if not isinstance(value, str):
            raise ConfigError(f"{key} deve essere un percorso")
        return Path(value)
    if isinstance(default, tuple):
        if not isinstance(value, list) or not all(type(item) is int for item in value):
            raise ConfigError(f"{key} deve essere una lista di interi")
        return tuple(value)
    if isinstance(default, float) and type(value) is int:
        return float(value)
    if type(value) is not type(default):
        raise ConfigError(f"{key} deve essere di tipo {type(default).__name__}")
    return value


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    values: dict[str, object] = {}
    if path.exists():
        defaults = Settings()
        known = {field.name for field in fields(Settings)}
        for key, value in tomllib.loads(path.read_text(encoding="utf-8")).items():
            if key not in known:
                raise ConfigError(f"impostazione sconosciuta: {key}")
            values[key] = _convert(key, value, getattr(defaults, key))
    settings = Settings(**values)
    validate(settings)
    return settings
```

- [x] **Step 5: Verifica che passino**

Run: `uv run pytest tests/test_atomic.py tests/test_config.py -q`
Expected: `13 passed`

- [x] **Step 6: Commit**

```powershell
git add src/lecture_study/atomic.py src/lecture_study/config.py tests/test_atomic.py tests/test_config.py
git commit -m "feat: add local-only settings and atomic file writes"
```

---

### Task 4: Ripetizione delle chiamate

**Files:**
- Create: `src/lecture_study/retry.py`, `tests/test_retry.py`

**Interfaces:**
- Consumes: `TransientError`, `RetriesExhausted`.
- Produces: `call_with_retries(operation: Callable[[], T], *, delays: tuple[int, ...], sleep: Callable[[float], None], on_retry: Callable[[TransientError, int, int], None] | None = None) -> T`. Esegue l'operazione, poi la ripete una volta per ogni attesa in `delays`; `on_retry(errore, numero_ripetizione, attesa)` viene chiamato prima di ogni attesa.

- [x] **Step 1: Scrivi i test che falliscono**

`tests/test_retry.py`:

```python
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
```

- [x] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_retry.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.retry'`

- [x] **Step 3: Scrivi `src/lecture_study/retry.py`**

```python
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
```

- [x] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_retry.py -q`
Expected: `4 passed`

- [x] **Step 5: Commit**

```powershell
git add src/lecture_study/retry.py tests/test_retry.py
git commit -m "feat: retry transient failures with fixed waits"
```

---

### Task 5: Archivio dei lavori

**Files:**
- Create: `src/lecture_study/jobs.py`, `tests/test_jobs.py`

**Interfaces:**
- Consumes: `read_json`, `write_json_atomic`.
- Produces:
  - `Stage` (StrEnum): `accept`, `analyze`, `prepare`, `transcribe`, `notes`, `mindmap`, `questions`; `STAGES = tuple(Stage)`
  - `Status` (StrEnum): `running`, `waiting`, `paused`, `needs_review`, `failed`, `done`; `FINAL_STATUSES = {done, failed, needs_review}`
  - `JobState(completed: list[str], status: str, stage: str | None, message: str, events: list[str])`
  - `Job(directory: Path)` con `dir`, `work_dir`, `state_path`, `source_path`, `prepared_wav`, `file(name) -> Path`, `read_source() -> dict`, `write_source(dict)`, `has_evidence(stage) -> bool`, `load_state() -> JobState`, `save_state(JobState)`

- [x] **Step 1: Scrivi i test che falliscono**

`tests/test_jobs.py`:

```python
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
```

- [x] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_jobs.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.jobs'`

- [x] **Step 3: Scrivi `src/lecture_study/jobs.py`**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from lecture_study.atomic import read_json, write_json_atomic


class Stage(StrEnum):
    ACCEPT = "accept"
    ANALYZE = "analyze"
    PREPARE = "prepare"
    TRANSCRIBE = "transcribe"
    NOTES = "notes"
    MINDMAP = "mindmap"
    QUESTIONS = "questions"


STAGES = tuple(Stage)


class Status(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    DONE = "done"


FINAL_STATUSES = frozenset({Status.DONE, Status.FAILED, Status.NEEDS_REVIEW})

STAGE_FILES = {
    Stage.TRANSCRIBE: ("transcript.json", "transcript.md"),
    Stage.NOTES: ("notes.md",),
    Stage.MINDMAP: ("mindmap.md",),
    Stage.QUESTIONS: ("questions.md",),
}


@dataclass
class JobState:
    completed: list[str] = field(default_factory=list)
    status: str = Status.RUNNING
    stage: str | None = None
    message: str = ""
    events: list[str] = field(default_factory=list)


class Job:
    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.work_dir = directory / "work"
        self.state_path = directory / "state.json"
        self.source_path = directory / "source.json"
        self.prepared_wav = self.work_dir / "prepared.wav"

    def file(self, name: str) -> Path:
        return self.dir / name

    def read_source(self) -> dict[str, Any]:
        return read_json(self.source_path) if self.source_path.exists() else {}

    def write_source(self, source: dict[str, Any]) -> None:
        write_json_atomic(self.source_path, source)

    def has_evidence(self, stage: Stage) -> bool:
        if stage is Stage.ACCEPT:
            return self.source_path.exists()
        if stage is Stage.ANALYZE:
            return "analysis" in self.read_source()
        if stage is Stage.PREPARE:
            return self.prepared_wav.exists() or self.has_evidence(Stage.TRANSCRIBE)
        return all(self.file(name).exists() for name in STAGE_FILES[stage])

    def load_state(self) -> JobState:
        if self.state_path.exists():
            return JobState(**read_json(self.state_path))
        completed = []
        for stage in STAGES:
            if not self.has_evidence(stage):
                break
            completed.append(stage.value)
        return JobState(completed=completed)

    def save_state(self, state: JobState) -> None:
        write_json_atomic(self.state_path, asdict(state))
```

- [x] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_jobs.py -q`
Expected: `6 passed`

- [x] **Step 5: Commit**

```powershell
git add src/lecture_study/jobs.py tests/test_jobs.py
git commit -m "feat: persist job state and rebuild it from final files"
```

---

### Task 6: Scanner e indice degli hash

**Files:**
- Create: `src/lecture_study/scanner.py`, `tests/test_scanner.py`

**Interfaces:**
- Consumes: `AUDIO_EXTENSIONS`, `read_json`, `write_json_atomic`.
- Produces:
  - `Recording(path: Path, size: int, mtime_ns: int)` (frozen)
  - `find_stable_recordings(watch_dir: Path, *, stable_seconds: int, now: float) -> list[Recording]`, ordinata dalla più vecchia
  - `sha256_file(path: Path) -> str`
  - `HashIndex(path: Path, hasher=sha256_file)` con `hash_of(recording) -> str` e `save() -> None`

- [x] **Step 1: Scrivi i test che falliscono**

`tests/test_scanner.py`:

```python
import os
import time

from lecture_study.scanner import HashIndex, find_stable_recordings, sha256_file


def make(path, content=b"audio", age=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    moment = time.time() - age
    os.utime(path, (moment, moment))
    return path


def test_finds_stable_audio_in_subfolders_oldest_first(tmp_path):
    older = make(tmp_path / "corso" / "a.M4A", age=600)
    newer = make(tmp_path / "b.mp3", age=120)
    make(tmp_path / "note.txt")
    make(tmp_path / "in-copia.wav", age=5)
    found = find_stable_recordings(tmp_path, stable_seconds=30, now=time.time())
    assert [recording.path for recording in found] == [older, newer]


def test_sha256_of_known_content(tmp_path):
    path = make(tmp_path / "a.wav", b"abc")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_index_reuses_digest_until_file_changes(tmp_path):
    path = make(tmp_path / "a.wav", b"uno")
    calls = []

    def hasher(target):
        calls.append(target)
        return sha256_file(target)

    recording = find_stable_recordings(tmp_path, stable_seconds=0, now=time.time())[0]
    index = HashIndex(tmp_path / "index.json", hasher=hasher)
    first = index.hash_of(recording)
    index.save()

    reloaded = HashIndex(tmp_path / "index.json", hasher=hasher)
    assert reloaded.hash_of(recording) == first
    assert len(calls) == 1

    make(path, b"due", age=30)
    changed = find_stable_recordings(tmp_path, stable_seconds=0, now=time.time())[0]
    assert reloaded.hash_of(changed) != first
    assert len(calls) == 2
```

- [x] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_scanner.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.scanner'`

- [x] **Step 3: Scrivi `src/lecture_study/scanner.py`**

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lecture_study.atomic import read_json, write_json_atomic
from lecture_study.config import AUDIO_EXTENSIONS


@dataclass(frozen=True)
class Recording:
    path: Path
    size: int
    mtime_ns: int


def find_stable_recordings(watch_dir: Path, *, stable_seconds: int, now: float) -> list[Recording]:
    found = []
    for path in watch_dir.rglob("*"):
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        try:
            if not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        if now - stat.st_mtime >= stable_seconds:
            found.append(Recording(path, stat.st_size, stat.st_mtime_ns))
    return sorted(found, key=lambda recording: (recording.mtime_ns, str(recording.path)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class HashIndex:
    def __init__(self, path: Path, hasher: Callable[[Path], str] = sha256_file) -> None:
        self.path = path
        self._hasher = hasher
        self._entries: dict[str, dict] = read_json(path) if path.exists() else {}

    def hash_of(self, recording: Recording) -> str:
        key = str(recording.path)
        entry = self._entries.get(key)
        if entry and entry["size"] == recording.size and entry["mtime_ns"] == recording.mtime_ns:
            return entry["sha256"]
        digest = self._hasher(recording.path)
        self._entries[key] = {"size": recording.size, "mtime_ns": recording.mtime_ns, "sha256": digest}
        return digest

    def save(self) -> None:
        write_json_atomic(self.path, self._entries)
```

- [x] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_scanner.py -q`
Expected: `3 passed`

- [x] **Step 5: Commit**

```powershell
git add src/lecture_study/scanner.py tests/test_scanner.py
git commit -m "feat: find stable recordings and cache their hashes"
```

---

### Task 7: Audio — lettura, analisi delle bande e preparazione

**Files:**
- Create: `src/lecture_study/audio.py`, `tests/test_audio.py`, `tests/test_audio_ffmpeg.py`

**Interfaces:**
- Consumes: `UnreadableAudio`. L'ingresso è un file con una delle estensioni accettate; ffmpeg ne decodifica il contenitore.
- Produces:
  - `ProbeResult(duration_seconds: float, format_name: str)`; `probe(path: Path, *, ffprobe: str = "ffprobe") -> ProbeResult`
  - `BandEnergy(low: float, voice: float)` con proprietà `ratio`; `band_energy(samples, rate) -> BandEnergy`; `analyze(path: Path, *, ffmpeg: str = "ffmpeg", block_seconds: int = 10) -> BandEnergy`
  - `should_highpass(energy: BandEnergy, threshold: float) -> bool`
  - `Prepared(path: Path, highpass_applied: bool, note: str)`; `prepare_command(...)`; `prepare(source: Path, work_dir: Path, *, ffmpeg: str = "ffmpeg", highpass_hz: int | None, run=subprocess.run) -> Prepared`
  - `required_free_bytes(duration_seconds: float) -> int`

- [ ] **Step 1: Scrivi i test unitari che falliscono**

`tests/test_audio.py`:

```python
import subprocess

import numpy as np
import pytest

from lecture_study.audio import (
    BandEnergy,
    band_energy,
    prepare,
    prepare_command,
    required_free_bytes,
    should_highpass,
)
from lecture_study.errors import UnreadableAudio

RATE = 8000


def tone(frequency, amplitude, seconds=4):
    t = np.arange(RATE * seconds) / RATE
    return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)


def test_rumble_dominates_low_band():
    energy = band_energy(tone(50, 0.5) + tone(200, 0.2), RATE)
    assert energy.ratio == pytest.approx(6.25, rel=0.05)


def test_voice_band_only_has_low_ratio():
    assert band_energy(tone(200, 0.3), RATE).ratio < 0.01


def test_threshold_is_inclusive():
    assert should_highpass(BandEnergy(low=1.0, voice=1.0), 1.0)
    assert not should_highpass(BandEnergy(low=0.99, voice=1.0), 1.0)


def test_silence_has_zero_ratio():
    assert BandEnergy(low=0.0, voice=0.0).ratio == 0.0


def test_prepare_command_adds_filter_only_when_requested(tmp_path):
    target = tmp_path / "b.wav"
    with_filter = prepare_command(tmp_path / "a.m4a", target, ffmpeg="ffmpeg", highpass_hz=80)
    without = prepare_command(tmp_path / "a.m4a", target, ffmpeg="ffmpeg", highpass_hz=None)
    assert "highpass=f=80" in with_filter
    assert "-af" not in without
    assert without[-5:] == ["-c:a", "pcm_s16le", "-f", "wav", str(target)]
    start = without.index("-ac")
    assert without[start:start + 4] == ["-ac", "1", "-ar", "16000"]


def test_prepare_falls_back_to_unfiltered_audio(tmp_path):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if "-af" in command:
            return subprocess.CompletedProcess(command, 1, "", "No such filter: 'highpass'")
        (tmp_path / "work" / "prepared.tmp.wav").write_bytes(b"RIFF")
        return subprocess.CompletedProcess(command, 0, "", "")

    prepared = prepare(tmp_path / "a.m4a", tmp_path / "work", highpass_hz=80, run=run)
    assert prepared.path == tmp_path / "work" / "prepared.wav"
    assert prepared.path.exists()
    assert not prepared.highpass_applied
    assert "non applicato" in prepared.note
    assert len(commands) == 2


def test_prepare_raises_when_audio_cannot_be_decoded(tmp_path):
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "Invalid data found when processing input")

    with pytest.raises(UnreadableAudio, match="Invalid data"):
        prepare(tmp_path / "a.m4a", tmp_path / "work", highpass_hz=None, run=run)
    assert not (tmp_path / "work" / "prepared.tmp.wav").exists()


def test_required_free_bytes_is_twice_the_wav_size():
    assert required_free_bytes(3600) == 230_400_000
```

- [ ] **Step 2: Scrivi il test con ffmpeg reale**

`tests/test_audio_ffmpeg.py`:

```python
import shutil
import wave

import numpy as np
import pytest

from lecture_study.audio import analyze, prepare, probe, should_highpass
from lecture_study.errors import UnreadableAudio

RATE = 44100


@pytest.fixture(scope="module")
def tools():
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not (ffmpeg and ffprobe):
        pytest.fail("ffmpeg e ffprobe devono essere nel PATH (Task 0)")
    return ffmpeg, ffprobe


def tone(frequency, amplitude, seconds=5):
    t = np.arange(RATE * seconds) / RATE
    return amplitude * np.sin(2 * np.pi * frequency * t)


def write_wav(path, signal):
    pcm = (np.clip(signal, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())


def test_rumble_triggers_highpass_and_produces_16k_mono_wav(tmp_path, tools):
    ffmpeg, ffprobe = tools
    source = tmp_path / "lezione.wav"
    write_wav(source, tone(50, 0.5) + tone(200, 0.2))

    assert probe(source, ffprobe=ffprobe).duration_seconds == pytest.approx(5, abs=0.1)
    energy = analyze(source, ffmpeg=ffmpeg)
    assert should_highpass(energy, 1.0)

    prepared = prepare(source, tmp_path / "work", ffmpeg=ffmpeg, highpass_hz=80)
    assert prepared.highpass_applied
    with wave.open(str(prepared.path)) as handle:
        assert (handle.getnchannels(), handle.getframerate(), handle.getsampwidth()) == (1, 16000, 2)
    assert analyze(prepared.path, ffmpeg=ffmpeg).ratio < energy.ratio
    assert source.read_bytes()[:4] == b"RIFF"


def test_voice_band_only_does_not_trigger_highpass(tmp_path, tools):
    ffmpeg, _ = tools
    source = tmp_path / "voce.wav"
    write_wav(source, tone(200, 0.3))
    assert not should_highpass(analyze(source, ffmpeg=ffmpeg), 1.0)


def test_non_audio_file_is_unreadable(tmp_path, tools):
    _, ffprobe = tools
    broken = tmp_path / "rotto.m4a"
    broken.write_bytes(b"non sono audio")
    with pytest.raises(UnreadableAudio):
        probe(broken, ffprobe=ffprobe)
```

- [ ] **Step 3: Verifica che falliscano**

Run: `uv run pytest tests/test_audio.py tests/test_audio_ffmpeg.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.audio'`

- [ ] **Step 4: Scrivi `src/lecture_study/audio.py`**

```python
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from lecture_study.errors import UnreadableAudio

ANALYSIS_RATE = 8000
WAV_BYTES_PER_SECOND = 32000


def _last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


@dataclass(frozen=True)
class ProbeResult:
    duration_seconds: float
    format_name: str


def probe(path: Path, *, ffprobe: str = "ffprobe") -> ProbeResult:
    process = subprocess.run(
        [
            ffprobe, "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type:format=duration,format_name",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if process.returncode != 0:
        raise UnreadableAudio(_last_line(process.stderr) or f"ffprobe exit {process.returncode}")
    data = json.loads(process.stdout or "{}")
    if not data.get("streams"):
        raise UnreadableAudio("nessuna traccia audio")
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise UnreadableAudio("durata non disponibile") from None
    if duration <= 0:
        raise UnreadableAudio("durata nulla")
    return ProbeResult(duration, data["format"].get("format_name", ""))


@dataclass(frozen=True)
class BandEnergy:
    low: float
    voice: float

    @property
    def ratio(self) -> float:
        return self.low / self.voice if self.voice > 0 else 0.0


def band_energy(samples: np.ndarray, rate: int) -> BandEnergy:
    spectrum = np.abs(np.fft.rfft(samples)) ** 2
    frequencies = np.fft.rfftfreq(samples.size, 1 / rate)
    low = spectrum[(frequencies >= 20) & (frequencies < 80)].sum()
    voice = spectrum[(frequencies >= 80) & (frequencies < 300)].sum()
    return BandEnergy(float(low), float(voice))


def analyze(path: Path, *, ffmpeg: str = "ffmpeg", block_seconds: int = 10) -> BandEnergy:
    command = [ffmpeg, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(ANALYSIS_RATE), "-f", "f32le", "-"]
    low = voice = 0.0
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        while chunk := process.stdout.read(ANALYSIS_RATE * block_seconds * 4):
            samples = np.frombuffer(chunk[: len(chunk) - len(chunk) % 4], dtype=np.float32)
            if samples.size:
                energy = band_energy(samples, ANALYSIS_RATE)
                low += energy.low
                voice += energy.voice
        stderr = process.stderr.read().decode("utf-8", "replace")
    if process.returncode != 0:
        raise UnreadableAudio(_last_line(stderr) or f"ffmpeg exit {process.returncode}")
    return BandEnergy(low, voice)


def should_highpass(energy: BandEnergy, threshold: float) -> bool:
    return energy.ratio >= threshold


@dataclass(frozen=True)
class Prepared:
    path: Path
    highpass_applied: bool
    note: str


def prepare_command(source: Path, target: Path, *, ffmpeg: str, highpass_hz: int | None) -> list[str]:
    command = [ffmpeg, "-v", "error", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000"]
    if highpass_hz is not None:
        command += ["-af", f"highpass=f={highpass_hz}"]
    return command + ["-c:a", "pcm_s16le", "-f", "wav", str(target)]


def prepare(
    source: Path,
    work_dir: Path,
    *,
    ffmpeg: str = "ffmpeg",
    highpass_hz: int | None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Prepared:
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "prepared.wav"
    partial = work_dir / "prepared.tmp.wav"
    note = ""
    attempts = [highpass_hz, None] if highpass_hz is not None else [None]
    for hz in attempts:
        process = run(
            prepare_command(source, partial, ffmpeg=ffmpeg, highpass_hz=hz),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if process.returncode == 0:
            os.replace(partial, target)
            return Prepared(target, hz is not None, note)
        note = f"filtro passa-alto non applicato: {_last_line(process.stderr) or process.returncode}"
    partial.unlink(missing_ok=True)
    raise UnreadableAudio(_last_line(process.stderr) or f"ffmpeg exit {process.returncode}")


def required_free_bytes(duration_seconds: float) -> int:
    return int(2 * WAV_BYTES_PER_SECOND * duration_seconds)
```

- [ ] **Step 5: Verifica che passino**

Run: `uv run pytest tests/test_audio.py tests/test_audio_ffmpeg.py -q`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/lecture_study/audio.py tests/test_audio.py tests/test_audio_ffmpeg.py
git commit -m "feat: analyse low-frequency noise and prepare 16 kHz audio"
```

---

### Task 8: Client Ollama

**Files:**
- Create: `src/lecture_study/llm.py`, `tests/test_llm.py`

**Interfaces:**
- Consumes: `TransientError`.
- Produces:
  - `LanguageModel` (Protocol): `complete(system: str, prompt: str) -> str`, `release() -> None`
  - `OllamaClient(base_url: str, model: str, *, num_ctx: int, timeout_seconds: int, urlopen=urllib.request.urlopen)`

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_llm.py`:

```python
import json
import urllib.error

import pytest

from lecture_study.errors import TransientError
from lecture_study.llm import OllamaClient


class FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def client(urlopen):
    return OllamaClient("http://127.0.0.1:11434/", "qwen2.5:7b", num_ctx=16384, timeout_seconds=600, urlopen=urlopen)


def test_complete_sends_non_streaming_chat_with_context_size():
    sent = []

    def urlopen(request, timeout):
        sent.append((request, timeout))
        return FakeResponse({"message": {"role": "assistant", "content": "## Tema"}})

    assert client(urlopen).complete("sistema", "testo") == "## Tema"
    request, timeout = sent[0]
    body = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 600
    assert body["model"] == "qwen2.5:7b"
    assert body["stream"] is False
    assert body["options"]["num_ctx"] == 16384
    assert body["messages"] == [{"role": "system", "content": "sistema"}, {"role": "user", "content": "testo"}]


def test_unreachable_server_is_transient():
    def urlopen(request, timeout):
        raise urllib.error.URLError(ConnectionRefusedError())

    with pytest.raises(TransientError, match="non raggiungibile"):
        client(urlopen).complete("s", "p")


def test_timeout_is_transient():
    def urlopen(request, timeout):
        raise TimeoutError("timed out")

    with pytest.raises(TransientError):
        client(urlopen).complete("s", "p")


def test_missing_model_is_transient():
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)

    with pytest.raises(TransientError, match="404"):
        client(urlopen).complete("s", "p")


def test_bad_request_is_not_retried():
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 400, "bad request", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        client(urlopen).complete("s", "p")


def test_release_unloads_model_and_ignores_unreachable_server():
    sent = []

    def urlopen(request, timeout):
        sent.append(request)
        return FakeResponse({"done": True})

    client(urlopen).release()
    assert sent[0].full_url == "http://127.0.0.1:11434/api/generate"
    assert json.loads(sent[0].data) == {"model": "qwen2.5:7b", "keep_alive": 0}

    def down(request, timeout):
        raise urllib.error.URLError(ConnectionRefusedError())

    client(down).release()
```

- [ ] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_llm.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.llm'`

- [ ] **Step 3: Scrivi `src/lecture_study/llm.py`**

```python
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol

from lecture_study.errors import TransientError


class LanguageModel(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...

    def release(self) -> None: ...


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        num_ctx: int,
        timeout_seconds: int,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._num_ctx = num_ctx
        self._timeout = timeout_seconds
        self._urlopen = urlopen

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self._base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404 or exc.code >= 500:
                raise TransientError(f"Ollama ha risposto {exc.code} per il modello {self.model}") from exc
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TransientError(f"Ollama non raggiungibile: {exc}") from exc

    def complete(self, system: str, prompt: str) -> str:
        data = self._post(
            "/api/chat",
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_ctx": self._num_ctx, "temperature": 0.2},
            },
        )
        return data.get("message", {}).get("content", "")

    def release(self) -> None:
        try:
            self._post("/api/generate", {"model": self.model, "keep_alive": 0})
        except TransientError:
            pass
```

- [ ] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_llm.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/lecture_study/llm.py tests/test_llm.py
git commit -m "feat: add loopback Ollama client"
```

---

### Task 9: Composizione dello studio

**Files:**
- Create: `src/lecture_study/prompts.py`, `src/lecture_study/study.py`, `tests/test_study.py`

**Interfaces:**
- Consumes: `LanguageModel`, `Segment`, `render_segments`, `InvalidModelOutput`.
- Produces:
  - `PROMPTS: dict[str, dict[str, str]]` con chiavi `it` ed `en` e voci `system`, `notes`, `mindmap`, `questions`, `notes_title`, `questions_title`
  - `make_blocks(segments, *, max_seconds=720, overlap_seconds=30) -> list[list[Segment]]`
  - `notes_are_valid`, `mindmap_is_valid`, `questions_are_valid` (`str -> bool`)
  - `StudyComposer(model: LanguageModel, call=lambda operation: operation())` con `notes(segments, language) -> str`, `mindmap(notes, language) -> str`, `questions(notes, language) -> str`

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_study.py`:

```python
import pytest

from lecture_study.errors import InvalidModelOutput
from lecture_study.study import StudyComposer, make_blocks
from lecture_study.transcribe import Segment

QUESTIONS = "\n\n".join(
    f"### {i}. Domanda {i}?\nRisposta attesa: risposta.\nRiferimento: [00:0{i}:00]" for i in range(1, 6)
)


class ScriptedModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.systems = []
        self.prompts = []

    def complete(self, system, prompt):
        self.systems.append(system)
        self.prompts.append(prompt)
        return self.replies.pop(0)

    def release(self):
        pass


def segments(count, length=10.0):
    return [Segment(i * length, (i + 1) * length, f"frase {i}") for i in range(count)]


def test_blocks_last_at_most_twelve_minutes_and_overlap_thirty_seconds():
    blocks = make_blocks(segments(180))
    assert len(blocks) == 3
    assert all(block[-1].end - block[0].start <= 720 for block in blocks)
    assert blocks[1][0].start == 690
    assert {s.start for block in blocks for s in block} == {s.start for s in segments(180)}


def test_notes_join_block_notes_under_one_title():
    model = ScriptedModel(["## Domanda e offerta\n- Prezzo di equilibrio [00:00:10]"])
    notes = StudyComposer(model).notes(segments(3), "it")
    assert notes.startswith("# Appunti\n\n## Domanda e offerta")
    assert "[00:00:00] frase 0" in model.prompts[0]
    assert "italiano" in model.systems[0]


def test_invalid_reply_is_retried_once_then_reported_with_partial():
    model = ScriptedModel(["testo senza struttura", "ancora niente"])
    with pytest.raises(InvalidModelOutput) as caught:
        StudyComposer(model).notes(segments(3), "it")
    assert caught.value.partial == "ancora niente"
    assert len(model.prompts) == 2


def test_second_attempt_can_recover():
    model = ScriptedModel(["niente", "## Tema\n- punto [00:00:10]"])
    assert "## Tema" in StudyComposer(model).notes(segments(3), "it")


def test_mindmap_and_questions_are_validated():
    composer = StudyComposer(ScriptedModel(["# Lezione\n## Tema\n- dettaglio", QUESTIONS]))
    assert composer.mindmap("## Tema", "it") == "# Lezione\n## Tema\n- dettaglio\n"
    assert composer.questions("## Tema", "it").startswith("# Domande di ripasso\n\n### 1.")


def test_too_few_questions_need_review():
    composer = StudyComposer(ScriptedModel(["### 1. Una? [00:00:01]", "### 1. Una? [00:00:01]"]))
    with pytest.raises(InvalidModelOutput):
        composer.questions("## Tema", "it")


def test_fenced_reply_is_unwrapped():
    composer = StudyComposer(ScriptedModel(["```markdown\n# Lezione\n## Tema\n```"]))
    assert composer.mindmap("## Tema", "it") == "# Lezione\n## Tema\n"


def test_english_lecture_uses_english_prompts():
    model = ScriptedModel(["## Topic\n- point [00:00:10]"])
    notes = StudyComposer(model).notes(segments(1), "en")
    assert notes.startswith("# Notes\n\n## Topic")
    assert "Transcript:" in model.prompts[0]


def test_call_wrapper_is_used_for_every_model_call():
    calls = []

    def call(operation):
        calls.append(1)
        return operation()

    StudyComposer(ScriptedModel(["## Tema\n- punto [00:00:10]"]), call=call).notes(segments(3), "it")
    assert calls == [1]
```

- [ ] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_study.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.study'`

- [ ] **Step 3: Scrivi `src/lecture_study/prompts.py`**

```python
PROMPTS = {
    "it": {
        "system": (
            "Sei un assistente di studio universitario. Scrivi solo in italiano, in Markdown. "
            "Usa soltanto il contenuto della lezione fornita e non aggiungere informazioni esterne."
        ),
        "notes": (
            "Questa è una parte della trascrizione di una lezione. Ogni riga inizia con il tempo [hh:mm:ss].\n"
            "Scrivi appunti di studio organizzati per argomento. Per ogni argomento usa un titolo che inizia con '## ' "
            "e sotto un elenco puntato con definizioni, concetti, esempi e collegamenti. "
            "Termina ogni punto con il tempo di riferimento nel formato [hh:mm:ss]. "
            "Non scrivere introduzioni né conclusioni.\n\nTrascrizione:\n{text}"
        ),
        "mindmap": (
            "Costruisci la mappa mentale della lezione a partire da questi appunti. "
            "Rispondi solo con una gerarchia Markdown: una prima riga '# ' con il titolo della lezione, "
            "'## ' per i temi principali, '### ' per i sottotemi ed elenchi puntati per i dettagli. "
            "Non superare quattro livelli e non aggiungere testo fuori dalla gerarchia.\n\nAppunti:\n{text}"
        ),
        "questions": (
            "Scrivi da 10 a 20 domande di ripasso basate su questi appunti, dalle definizioni ai collegamenti "
            "fra concetti. Per ogni domanda usa esattamente questo formato:\n\n"
            "### 1. <domanda>\nRisposta attesa: <risposta in due o tre frasi>\nRiferimento: [hh:mm:ss]\n\n"
            "Appunti:\n{text}"
        ),
        "notes_title": "# Appunti",
        "questions_title": "# Domande di ripasso",
    },
    "en": {
        "system": (
            "You are a university study assistant. Write only in English, in Markdown. "
            "Use only the content of the lecture provided and do not add outside information."
        ),
        "notes": (
            "This is part of a lecture transcript. Each line starts with the time [hh:mm:ss].\n"
            "Write study notes organised by topic. For each topic use a heading starting with '## ' "
            "followed by a bulleted list of definitions, concepts, examples and connections. "
            "End each bullet with its reference time in the format [hh:mm:ss]. "
            "Do not write an introduction or a conclusion.\n\nTranscript:\n{text}"
        ),
        "mindmap": (
            "Build the mind map of the lecture from these notes. "
            "Reply only with a Markdown hierarchy: a first line '# ' with the lecture title, "
            "'## ' for the main themes, '### ' for subthemes and bulleted lists for details. "
            "Use at most four levels and add no text outside the hierarchy.\n\nNotes:\n{text}"
        ),
        "questions": (
            "Write 10 to 20 review questions based on these notes, from definitions to connections between "
            "concepts. For each question use exactly this format:\n\n"
            "### 1. <question>\nExpected answer: <answer in two or three sentences>\nReference: [hh:mm:ss]\n\n"
            "Notes:\n{text}"
        ),
        "notes_title": "# Notes",
        "questions_title": "# Review questions",
    },
}
```

- [ ] **Step 4: Scrivi `src/lecture_study/study.py`**

```python
from __future__ import annotations

import re
from typing import Callable, Sequence

from lecture_study.errors import InvalidModelOutput
from lecture_study.llm import LanguageModel
from lecture_study.prompts import PROMPTS
from lecture_study.transcribe import Segment, render_segments

BLOCK_SECONDS = 720
OVERLAP_SECONDS = 30
MIN_QUESTIONS = 5
TIMESTAMP = re.compile(r"\[\d{2}:\d{2}:\d{2}\]")
TOPIC_HEADING = re.compile(r"^## \S", re.MULTILINE)
QUESTION_HEADING = re.compile(r"^### \d+\.", re.MULTILINE)

Call = Callable[[Callable[[], str]], str]


def make_blocks(
    segments: Sequence[Segment],
    *,
    max_seconds: float = BLOCK_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
) -> list[list[Segment]]:
    blocks: list[list[Segment]] = []
    current: list[Segment] = []
    for segment in segments:
        if current and segment.end - current[0].start > max_seconds:
            blocks.append(current)
            cutoff = current[-1].end - overlap_seconds
            current = [previous for previous in current if previous.start >= cutoff]
        current.append(segment)
    if current:
        blocks.append(current)
    return blocks


def notes_are_valid(text: str) -> bool:
    return bool(TOPIC_HEADING.search(text) and TIMESTAMP.search(text))


def mindmap_is_valid(text: str) -> bool:
    return text.startswith("# ") and bool(TOPIC_HEADING.search(text))


def questions_are_valid(text: str) -> bool:
    return len(QUESTION_HEADING.findall(text)) >= MIN_QUESTIONS and bool(TIMESTAMP.search(text))


def _strip_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        lines = lines[1:-1]
    return "\n".join(lines).strip()


class StudyComposer:
    def __init__(self, model: LanguageModel, call: Call = lambda operation: operation()) -> None:
        self._model = model
        self._call = call

    def _generate(self, language: str, kind: str, text: str, is_valid: Callable[[str], bool]) -> str:
        prompts = PROMPTS[language]
        prompt = prompts[kind].format(text=text)
        output = ""
        for _ in range(2):
            output = _strip_fence(self._call(lambda: self._model.complete(prompts["system"], prompt)))
            if is_valid(output):
                return output
        raise InvalidModelOutput(f"risposta non valida per {kind}", output)

    def notes(self, segments: Sequence[Segment], language: str) -> str:
        parts: list[str] = []
        for block in make_blocks(segments):
            try:
                parts.append(self._generate(language, "notes", render_segments(block), notes_are_valid))
            except InvalidModelOutput as exc:
                raise InvalidModelOutput(str(exc), "\n\n".join([*parts, exc.partial])) from exc
        return f"{PROMPTS[language]['notes_title']}\n\n" + "\n\n".join(parts) + "\n"

    def mindmap(self, notes: str, language: str) -> str:
        return self._generate(language, "mindmap", notes, mindmap_is_valid) + "\n"

    def questions(self, notes: str, language: str) -> str:
        body = self._generate(language, "questions", notes, questions_are_valid)
        return f"{PROMPTS[language]['questions_title']}\n\n{body}\n"
```

- [ ] **Step 5: Verifica che passino**

Run: `uv run pytest tests/test_study.py -q`
Expected: `9 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/lecture_study/prompts.py src/lecture_study/study.py tests/test_study.py
git commit -m "feat: compose notes, mind map and review questions"
```

---

### Task 10: Report

**Files:**
- Create: `src/lecture_study/report.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `JobState`, `Status`, `format_timestamp`.
- Produces: `render_report(state: JobState, source: dict) -> str`. Legge da `source` le chiavi `path`, `sha256`, `duration_seconds`, `format`, `analysis{low, voice, ratio, threshold, highpass_hz, apply}`, `preparation{highpass_applied, note}`, `transcription{language, language_probability, model, device}`.

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_report.py`:

```python
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
```

- [ ] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_report.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.report'`

- [ ] **Step 3: Scrivi `src/lecture_study/report.py`**

```python
from __future__ import annotations

from typing import Any

from lecture_study.jobs import JobState
from lecture_study.transcribe import format_timestamp


def _audio_lines(source: dict[str, Any]) -> list[str]:
    analysis = source.get("analysis")
    if not analysis:
        return ["- Non ancora analizzato"]
    decision = f"applicare il passa-alto a {analysis['highpass_hz']} Hz" if analysis["apply"] else "nessun passa-alto"
    lines = [
        f"- Energia 20–80 Hz: {analysis['low']:.4g}",
        f"- Energia 80–300 Hz: {analysis['voice']:.4g}",
        f"- Rapporto: {analysis['ratio']:.3f} (soglia {analysis['threshold']})",
        f"- Decisione: {decision}",
    ]
    if not analysis["apply"]:
        lines.append("- Il rumore sotto 80 Hz è basso; il passa-alto non riduce il rumore a banda larga")
    preparation = source.get("preparation")
    if preparation:
        lines.append(f"- Applicato: {'sì' if preparation['highpass_applied'] else 'no'}")
        if preparation["note"]:
            lines.append(f"- Nota: {preparation['note']}")
    return lines


def _transcription_lines(source: dict[str, Any]) -> list[str]:
    transcription = source.get("transcription")
    if not transcription:
        return ["- Non ancora trascritto"]
    return [
        f"- Lingua: {transcription['language']} (probabilità {transcription['language_probability']:.2f})",
        f"- Modello: {transcription['model']}",
        f"- Dispositivo: {transcription['device']}",
    ]


def render_report(state: JobState, source: dict[str, Any]) -> str:
    duration = source.get("duration_seconds")
    lines = [
        "# Report di elaborazione",
        "",
        f"- Stato: {state.status}",
        f"- Fase: {state.stage or '-'}",
        f"- Messaggio: {state.message or '-'}",
        f"- Fasi completate: {', '.join(state.completed) or '-'}",
        "",
        "## Sorgente",
        "",
        f"- File: {source.get('path', '-')}",
        f"- SHA-256: {source.get('sha256', '-')}",
        f"- Durata: {format_timestamp(duration) if duration is not None else '-'}",
        f"- Formato: {source.get('format', '-')}",
        "",
        "## Audio",
        "",
        *_audio_lines(source),
        "",
        "## Trascrizione",
        "",
        *_transcription_lines(source),
        "",
        "## Eventi",
        "",
        *([f"- {event}" for event in state.events] or ["- Nessuno"]),
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_report.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/lecture_study/report.py tests/test_report.py
git commit -m "feat: render processing report"
```

---

### Task 11: Esecutore delle fasi

**Files:**
- Create: `src/lecture_study/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: tutto quanto prodotto dai Task 1–10.
- Produces: `Pipeline(settings: Settings, *, transcriber: Transcriber, model: LanguageModel, probe=audio.probe, analyze=audio.analyze, prepare=audio.prepare, free_bytes=lambda path: shutil.disk_usage(path).free, sleep=time.sleep)` con `process(recording: Recording, sha256: str) -> JobState`.

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_pipeline.py`:

```python
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
NOTES = "## Tema\n- Punto [00:00:05]"
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
            raise TransientError("Ollama non raggiungibile")
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


def make_pipeline(tmp_path, *, transcriber=None, model=None, probe=None, free=10**12, sleeps=None):
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
    assert "- Stato: done" in current.file("report.md").read_text(encoding="utf-8")
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
    state = make_pipeline(tmp_path, model=FakeModel(replies=["niente", "ancora niente"])).process(recording, SHA)
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
    assert "spazio insufficiente" in state.message


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
```

- [ ] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_pipeline.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.pipeline'`

- [ ] **Step 3: Scrivi `src/lecture_study/pipeline.py`**

```python
from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Callable, TypeVar

from lecture_study import audio
from lecture_study.atomic import read_json, write_json_atomic, write_text_atomic
from lecture_study.config import Settings
from lecture_study.errors import (
    GpuOutOfMemory,
    InsufficientSpace,
    InvalidModelOutput,
    RecordingMissing,
    RetriesExhausted,
    TransientError,
    UnreadableAudio,
)
from lecture_study.jobs import FINAL_STATUSES, STAGES, Job, JobState, Stage, Status
from lecture_study.llm import LanguageModel
from lecture_study.report import render_report
from lecture_study.retry import call_with_retries
from lecture_study.scanner import Recording
from lecture_study.study import StudyComposer
from lecture_study.transcribe import Transcriber, Transcript, render_transcript

log = logging.getLogger(__name__)
OUT_OF_MEMORY_BEFORE_CPU = 2
T = TypeVar("T")


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        transcriber: Transcriber,
        model: LanguageModel,
        probe: Callable[..., audio.ProbeResult] = audio.probe,
        analyze: Callable[..., audio.BandEnergy] = audio.analyze,
        prepare: Callable[..., audio.Prepared] = audio.prepare,
        free_bytes: Callable[[Path], int] = lambda path: shutil.disk_usage(path).free,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._transcriber = transcriber
        self._model = model
        self._probe = probe
        self._analyze_audio = analyze
        self._prepare_audio = prepare
        self._free_bytes = free_bytes
        self._sleep = sleep
        self._model_used = False
        self._handlers = {
            Stage.ACCEPT: self._accept,
            Stage.ANALYZE: self._analyze,
            Stage.PREPARE: self._prepare,
            Stage.TRANSCRIBE: self._transcribe,
            Stage.NOTES: self._notes,
            Stage.MINDMAP: self._mindmap,
            Stage.QUESTIONS: self._questions,
        }

    def process(self, recording: Recording, sha256: str) -> JobState:
        job = Job(self.settings.library_dir / sha256)
        state = job.load_state()
        if state.status in FINAL_STATUSES:
            return state
        self._remember_path(job, recording)
        self._model_used = False
        state.status, state.message = Status.RUNNING, ""
        try:
            for stage in STAGES:
                if stage in state.completed:
                    continue
                state.stage = stage
                self._handlers[stage](job, recording, sha256, state)
                job.file(f"{stage}.partial.md").unlink(missing_ok=True)
                state.completed.append(stage.value)
                job.save_state(state)
            state.status, state.stage = Status.DONE, None
            shutil.rmtree(job.work_dir, ignore_errors=True)
        except UnreadableAudio as exc:
            state.status, state.message = Status.FAILED, f"audio illeggibile: {exc}"
        except (RetriesExhausted, InsufficientSpace) as exc:
            state.status, state.message = Status.WAITING, str(exc)
        except RecordingMissing as exc:
            state.status, state.message = Status.PAUSED, str(exc)
        except InvalidModelOutput as exc:
            write_text_atomic(job.file(f"{state.stage}.partial.md"), exc.partial + "\n")
            state.status, state.message = Status.NEEDS_REVIEW, str(exc)
        except Exception as exc:
            log.exception("job %s: errore inatteso nella fase %s", sha256[:12], state.stage)
            state.status, state.message = Status.FAILED, f"errore inatteso: {type(exc).__name__}: {exc}"
        if self._model_used:
            self._model.release()
        job.save_state(state)
        write_text_atomic(job.file("report.md"), render_report(state, job.read_source()))
        log.info("job %s path=%s stage=%s status=%s", sha256[:12], recording.path, state.stage, state.status)
        return state

    def _remember_path(self, job: Job, recording: Recording) -> None:
        source = job.read_source()
        if source and source.get("path") != str(recording.path) and not Path(source["path"]).exists():
            source["path"] = str(recording.path)
            job.write_source(source)

    def _audio_call(self, recording: Recording, operation: Callable[[], T]) -> T:
        missing = RecordingMissing(f"registrazione non trovata: {recording.path}")
        if not recording.path.exists():
            raise missing
        try:
            return operation()
        except UnreadableAudio:
            if not recording.path.exists():
                raise missing from None
            raise

    def _on_retry(self, state: JobState, stage: Stage) -> Callable[[TransientError, int, int], None]:
        def record(error: TransientError, retry: int, delay: int) -> None:
            state.events.append(f"{stage}: {error}; ripetizione {retry} tra {delay} s")
            log.warning("fase %s: errore temporaneo, ripetizione %d tra %d s", stage, retry, delay)

        return record

    def _accept(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        info = self._audio_call(recording, lambda: self._probe(recording.path, ffprobe=self.settings.ffprobe))
        job.write_source(
            {
                "path": str(recording.path),
                "sha256": sha256,
                "size": recording.size,
                "duration_seconds": round(info.duration_seconds, 2),
                "format": info.format_name,
            }
        )

    def _analyze(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        energy = self._audio_call(recording, lambda: self._analyze_audio(recording.path, ffmpeg=self.settings.ffmpeg))
        source = job.read_source()
        source["analysis"] = {
            "low": energy.low,
            "voice": energy.voice,
            "ratio": round(energy.ratio, 4),
            "threshold": self.settings.highpass_ratio_threshold,
            "highpass_hz": self.settings.highpass_hz,
            "apply": audio.should_highpass(energy, self.settings.highpass_ratio_threshold),
        }
        job.write_source(source)

    def _prepare(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        source = job.read_source()
        required = audio.required_free_bytes(source["duration_seconds"])
        free = self._free_bytes(self.settings.library_dir)
        if free < required:
            raise InsufficientSpace(f"spazio insufficiente: servono {required // 2**20} MB, liberi {free // 2**20} MB")
        highpass_hz = self.settings.highpass_hz if source["analysis"]["apply"] else None
        prepared = self._audio_call(
            recording,
            lambda: self._prepare_audio(recording.path, job.work_dir, ffmpeg=self.settings.ffmpeg, highpass_hz=highpass_hz),
        )
        source["preparation"] = {"highpass_applied": prepared.highpass_applied, "note": prepared.note}
        job.write_source(source)

    def _transcribe(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        if not job.prepared_wav.exists():
            self._prepare(job, recording, sha256, state)
        out_of_memory = 0

        def attempt() -> Transcript:
            nonlocal out_of_memory
            device = "cpu" if out_of_memory >= OUT_OF_MEMORY_BEFORE_CPU else "cuda"
            try:
                return self._transcriber.transcribe(job.prepared_wav, device=device)
            except GpuOutOfMemory:
                out_of_memory += 1
                if out_of_memory == OUT_OF_MEMORY_BEFORE_CPU:
                    state.events.append("transcribe: memoria video esaurita due volte, si continua sulla CPU")
                raise

        transcript = call_with_retries(
            attempt,
            delays=self.settings.retry_delays,
            sleep=self._sleep,
            on_retry=self._on_retry(state, Stage.TRANSCRIBE),
        )
        write_json_atomic(job.file("transcript.json"), transcript.to_json())
        write_text_atomic(job.file("transcript.md"), render_transcript(transcript, recording.path.stem))
        source = job.read_source()
        source["transcription"] = {
            "language": transcript.language,
            "language_probability": transcript.language_probability,
            "model": transcript.model,
            "device": transcript.device,
        }
        job.write_source(source)
        shutil.rmtree(job.work_dir, ignore_errors=True)

    def _composer(self, state: JobState, stage: Stage) -> StudyComposer:
        self._model_used = True
        on_retry = self._on_retry(state, stage)
        return StudyComposer(
            self._model,
            call=lambda operation: call_with_retries(
                operation, delays=self.settings.retry_delays, sleep=self._sleep, on_retry=on_retry
            ),
        )

    def _transcript(self, job: Job) -> Transcript:
        return Transcript.from_json(read_json(job.file("transcript.json")))

    def _notes(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        transcript = self._transcript(job)
        notes = self._composer(state, Stage.NOTES).notes(transcript.segments, transcript.language)
        write_text_atomic(job.file("notes.md"), notes)

    def _mindmap(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        notes = job.file("notes.md").read_text(encoding="utf-8")
        mindmap = self._composer(state, Stage.MINDMAP).mindmap(notes, self._transcript(job).language)
        write_text_atomic(job.file("mindmap.md"), mindmap)

    def _questions(self, job: Job, recording: Recording, sha256: str, state: JobState) -> None:
        notes = job.file("notes.md").read_text(encoding="utf-8")
        questions = self._composer(state, Stage.QUESTIONS).questions(notes, self._transcript(job).language)
        write_text_atomic(job.file("questions.md"), questions)
```

- [ ] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_pipeline.py -q`
Expected: `9 passed`

- [ ] **Step 5: Esegui tutta la suite**

Run: `uv run pytest -q`
Expected: tutti i test passano, nessun errore o skip.

- [ ] **Step 6: Commit**

```powershell
git add src/lecture_study/pipeline.py tests/test_pipeline.py
git commit -m "feat: run lecture stages with resume, retries and review states"
```

---

### Task 12: Comando `lecture-study` e avvio automatico

**Files:**
- Create: `src/lecture_study/cli.py`, `tests/test_cli.py`, `scripts/register-autostart.ps1`

**Interfaces:**
- Consumes: `load_settings`, `Pipeline`, `HashIndex`, `find_stable_recordings`, `OllamaClient`, `FasterWhisperTranscriber`.
- Produces: `scan_once(settings, pipeline, index, *, now=time.time) -> int`; `main(argv: list[str] | None = None) -> int`; comando `lecture-study [--config PATH] once|watch`.

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_cli.py`:

```python
import os
import time

from lecture_study.cli import main, scan_once
from lecture_study.config import Settings
from lecture_study.scanner import HashIndex


def make(path, age):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(path.name.encode())
    moment = time.time() - age
    os.utime(path, (moment, moment))
    return path


class RecordingPipeline:
    def __init__(self):
        self.seen = []

    def process(self, recording, sha256):
        self.seen.append((recording.path, sha256))


def test_scan_once_processes_stable_recordings_oldest_first(tmp_path):
    settings = Settings(watch_dir=tmp_path / "in", library_dir=tmp_path / "out")
    settings.library_dir.mkdir()
    older = make(settings.watch_dir / "a.m4a", age=600)
    newer = make(settings.watch_dir / "b.mp3", age=120)
    make(settings.watch_dir / "c.wav", age=1)
    pipeline = RecordingPipeline()
    assert scan_once(settings, pipeline, HashIndex(settings.library_dir / "index.json")) == 2
    assert [path for path, _ in pipeline.seen] == [older, newer]
    assert all(len(sha) == 64 for _, sha in pipeline.seen)
    assert (settings.library_dir / "index.json").exists()


def test_main_rejects_ollama_outside_this_pc(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(
        f'watch_dir = "{(tmp_path / "in").as_posix()}"\n'
        f'library_dir = "{(tmp_path / "out").as_posix()}"\n'
        'ollama_url = "http://10.0.0.5:11434"\n',
        encoding="utf-8",
    )
    assert main(["--config", str(config), "once"]) == 2
    assert "questo PC" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
```

- [ ] **Step 2: Verifica che falliscano**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lecture_study.cli'`

- [ ] **Step 3: Scrivi `src/lecture_study/cli.py`**

```python
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Callable

from lecture_study.config import DEFAULT_CONFIG, ConfigError, Settings, load_settings
from lecture_study.llm import OllamaClient
from lecture_study.pipeline import Pipeline
from lecture_study.scanner import HashIndex, find_stable_recordings
from lecture_study.transcribe import FasterWhisperTranscriber

log = logging.getLogger("lecture_study")


def build_pipeline(settings: Settings) -> Pipeline:
    model = OllamaClient(
        settings.ollama_url,
        settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    return Pipeline(settings, transcriber=FasterWhisperTranscriber(settings.whisper_model), model=model)


def scan_once(settings: Settings, pipeline: Pipeline, index: HashIndex, *, now: Callable[[], float] = time.time) -> int:
    processed = 0
    for recording in find_stable_recordings(settings.watch_dir, stable_seconds=settings.stable_seconds, now=now()):
        try:
            sha256 = index.hash_of(recording)
        except OSError as exc:
            log.warning("impossibile leggere %s: %s", recording.path, exc)
            continue
        index.save()
        pipeline.process(recording, sha256)
        processed += 1
    return processed


def configure_logging(library_dir: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(library_dir / "lecture-study.log", encoding="utf-8"), logging.StreamHandler()],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lecture-study")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("command", choices=("once", "watch"))
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"configurazione non valida: {exc}", file=sys.stderr)
        return 2
    settings.watch_dir.mkdir(parents=True, exist_ok=True)
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.library_dir)
    pipeline = build_pipeline(settings)
    index = HashIndex(settings.library_dir / "index.json")
    if args.command == "once":
        scan_once(settings, pipeline, index)
        return 0
    log.info("osservo %s", settings.watch_dir)
    try:
        while True:
            scan_once(settings, pipeline, index)
            time.sleep(settings.scan_interval_seconds)
    except KeyboardInterrupt:
        return 0
```

- [ ] **Step 4: Verifica che passino**

Run: `uv run pytest tests/test_cli.py -q`
Expected: `2 passed`

- [ ] **Step 5: Scrivi `scripts/register-autostart.ps1`**

```powershell
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv -ErrorAction Stop).Source
$action = New-ScheduledTaskAction -Execute $uv -Argument "run --project `"$repo`" lecture-study watch" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'LectureStudyWatch' -Action $action -Trigger $trigger -Settings $settings -Description 'Osserva la cartella delle lezioni e produce il materiale di studio' -Force | Out-Null
Write-Output "Registrata l'attività LectureStudyWatch per $env:USERNAME"
```

- [ ] **Step 6: Registra e avvia l'attività**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register-autostart.ps1
Start-ScheduledTask -TaskName LectureStudyWatch
Start-Sleep -Seconds 20
Get-Content "$env:USERPROFILE\mba-studio\library\lecture-study.log" -Tail 5
```

Expected: `Registrata l'attività LectureStudyWatch ...` e, nel log, una riga `osservo C:\Users\Mathia.Scucchiari\mba-studio\lezioni`. Se la policy aziendale blocca `Register-ScheduledTask`, **STOP** e chiedi all'utente come avviare `uv run lecture-study watch`.

- [ ] **Step 7: Esegui tutta la suite**

Run: `uv run pytest -q`
Expected: tutti i test passano.

- [ ] **Step 8: Commit**

```powershell
git add src/lecture_study/cli.py tests/test_cli.py scripts/register-autostart.ps1
git commit -m "feat: add watch command and Windows autostart"
```

---

### Task 13: Prova con una lezione reale e documentazione

**Files:**
- Modify: `docs/workstreams.md`, `docs/codebase-knowledge/*.md` (tramite `/refresh-codebase-knowledge`)

**Interfaces:**
- Consumes: il servizio avviato nel Task 12.
- Produces: evidenza manuale dell'esito atteso della specifica.

- [ ] **Step 1: Prova breve**

Copia in `C:\Users\Mathia.Scucchiari\mba-studio\lezioni` un estratto di 10 minuti di una lezione reale. Durante l'elaborazione esegui `nvidia-smi` e annota la memoria video usata.

Expected, entro circa 15 minuti: in `C:\Users\Mathia.Scucchiari\mba-studio\library\<sha256>\` esistono `transcript.md`, `transcript.json`, `notes.md`, `mindmap.md`, `questions.md`, `report.md`, `source.json`, `state.json`; `report.md` riporta `Stato: done` e `Dispositivo: cuda`; il file originale ha lo stesso SHA-256 di prima (`Get-FileHash`).

- [ ] **Step 2: Verifica dei contenuti**

Apri `mindmap.md` con un visualizzatore Markmap e `questions.md`. Controlla con l'utente che appunti, mappa e domande siano utili per lo studio. Se la qualità del modello `qwen2.5:7b` non basta, **STOP** e riporta all'utente esempi concreti prima di cambiare modello o istruzioni.

- [ ] **Step 3: Ripresa dopo un'interruzione**

Copia una seconda lezione. Quando `transcript.md` compare nella sua cartella, ferma Ollama (`Stop-Process -Name ollama*`). Attendi che `report.md` riporti `Stato: waiting` e la fase `notes`; poi riavvia Ollama dal menu Start.

Expected: alla scansione successiva il lavoro riprende da `notes`, il log non mostra una nuova trascrizione e la cartella arriva a `Stato: done`.

- [ ] **Step 4: Lezione completa**

Copia una lezione intera (2–3 ore). Annota nel report durata dell'audio e tempo totale di elaborazione dalle righe del log.

Expected: `Stato: done`. Riporta all'utente i tempi misurati.

- [ ] **Step 5: Documentazione del repository**

Esegui `/refresh-codebase-knowledge` per riempire `docs/codebase-knowledge/`. Aggiorna la riga in `docs/workstreams.md`:

```markdown
| Lecture study pipeline | `feat/lecture-study-pipeline` | Implemented, manual checks done | Review and merge into `main` |
```

- [ ] **Step 6: Verifica finale e commit**

Run: `uv run pytest -q`
Expected: tutti i test passano. Mostra l'output nella stessa risposta del commit.

```powershell
git add docs
git commit -m "docs: record lecture pipeline knowledge and status"
```
