# Avvio

Il programma legge lezioni audio su questo PC, le trascrive e scrive appunti, mappa e domande. Il codice sta in questo repository. I dati e i programmi scaricati stanno in `~/mba-studio`, fuori da OneDrive. Cancellare quella cartella toglie l'ambiente, i modelli e la libreria predefinita. Il codice resta nel repository.

Non serve Docker e non serve un account amministratore. I driver della GPU, se ci sono, restano quelli già installati. Lo script non usa l'installer di `uv` nel profilo utente e non contatta la porta 11434.

## Cosa serve

- Windows o macOS.
- Circa 15 GB liberi sul disco del profilo, fuori da OneDrive. Il primo avvio scarica Whisper `large-v3`.
- `ffmpeg` e `ffprobe` nel `PATH`. Su macOS vanno installati a parte: gli archivi macOS non sono nel file dei pin.
- Ollama in ascolto su `http://127.0.0.1:11435` con il modello `qwen2.5:7b`. Se sulla porta 11434 c'è un Ollama più vecchio, lascialo com'è.
- Python 3.12. Lo procura `uv` dentro `~/mba-studio`. Non va creato un ambiente nel repository.

Una GPU NVIDIA accelera la trascrizione. Senza CUDA il primo tentativo usa la CPU. Con CUDA, dopo due errori di memoria insufficiente si passa alla CPU.

## Cartelle

| Percorso | Contenuto |
|---|---|
| `~/mba-studio/bin` | `uv` scaricato dallo script |
| `~/mba-studio/.venv` | pacchetti Python |
| `~/mba-studio/python` | interprete installato da `uv` |
| `~/mba-studio/cache` | cache di `uv` |
| `~/mba-studio/hf` | Whisper `large-v3` |
| `~/mba-studio/lezioni` | audio predefinito, se non ne scegli un altro |
| `~/mba-studio/library` | risultati predefiniti |
| `~/mba-studio/config.toml` | creato solo se manca |
| `~/mba-studio/hold.json` | presente quando la coda è ferma |

`config.toml` assente: `up` lo crea. Se in `~/mba-studio/bin` ci sono già `ffmpeg` e `ffprobe`, il file punta a quelli. Altrimenti usa i nomi `ffmpeg` e `ffprobe` del `PATH`. L'indirizzo di Ollama resta `http://127.0.0.1:11435`. Se il file esiste già, l'avvio non lo riscrive.

## Setup

Dal repository, su Windows:

```powershell
scripts\studio.cmd
```

Su macOS:

```sh
sh scripts/studio.sh
```

Lo script scarica `uv` 0.11.16 in `~/mba-studio/bin` se manca o se il checksum non torna, imposta `UV_PROJECT_ENVIRONMENT`, `UV_PYTHON_INSTALL_DIR` e `UV_CACHE_DIR` dentro `~/mba-studio`, poi esegue `lecture-study up`.

`up` apre `http://127.0.0.1:8765/` solo su questo PC. Se la porta è occupata, si ferma prima di leggere gli audio. Se il browser non si apre, l'indirizzo resta nel terminale. La pagina risponde anche mentre Whisper viene scaricato. Il browser si apre a download finito.

Sulla pagina scegli la cartella audio e la cartella risultati, poi premi **Usa queste cartelle**. I file non vengono copiati. Una cartella dentro OneDrive, un disco di rete, o una cartella risultati dentro quella audio vengono rifiutate e restano i percorsi precedenti. Un file parte dopo 30 secondi senza cambi di dimensione e di data. Il controllo successivo arriva entro circa un minuto.

La tabella elenca ogni file audio con la fase e lo stato. **Ferma** blocca la coda: la fase già iniziata finisce, le altre no. **Riprendi** compare se la coda è ferma o su una lezione in stato `stopped`. `failed`, `needs_review`, `waiting` e `paused` non hanno **Riprendi**.

## Altri comandi

Dalla root del repository, con l'ambiente dello studio:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run lecture-study once
uv run lecture-study watch
```

`once` elabora i file stabili e termina. `watch` resta in esecuzione. Su questo PC il task `LectureStudyWatch` può già eseguire `watch`: non lanciare un secondo `once` o `watch` sulla stessa cartella.

## Test

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv run pytest -q
```

Se la pagina è già aperta, il test che occupa la porta 8765 fallisce. Chiudi `up` e rilancialo.
