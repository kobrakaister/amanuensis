# Dipendenze

Verificate con `pip-audit` il 2026-10-27. Nessuna viene redistribuita: il progetto gira solo su questo PC.

| Componente | Versione | Uso | Licenza | Fonte | Supporto | SBOM del fornitore |
|---|---|---|---|---|---|---|
| numpy | 2.5.4 | analisi delle bande audio | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | PyPI | rilasci attivi | non pubblicata |
| faster-whisper | 1.2.1 | trascrizione | MIT | PyPI, SYSTRAN | rilasci attivi | non pubblicata |
| nvidia-cublas-cu12 | 12.9.2.10 | GPU per CTranslate2 | NVIDIA proprietaria | PyPI, NVIDIA | CUDA 12 supportato | non pubblicata |
| nvidia-cudnn-cu12 | 9.27.0.42 | GPU per CTranslate2 | NVIDIA proprietaria | PyPI, NVIDIA | cuDNN 9 supportato | non pubblicata |
| pytest | 9.1.1 | test, solo sviluppo | MIT | PyPI | rilasci attivi | non pubblicata |
| ffmpeg | 9.0.2 | decodifica e filtro | LGPL/GPL | winget Gyan.FFmpeg; lo studio scarica anche lo zip GyanD `ffmpeg-9.0.2-essentials_build.zip` (SHA-256 `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`) solo per Windows | rilasci attivi | non pubblicata |
| Ollama | 0.40.11 | modello linguistico locale | MIT | winget Ollama.Ollama; lo studio scarica gli zip GitHub `v0.40.11` elencati in `sha256sum.txt` | rilasci attivi | non pubblicata |
| uv | 0.11.16 | ambiente dello studio | MIT OR Apache-2.0 | GitHub astral-sh/uv, checksum nel dist-manifest | rilasci attivi | non pubblicata |

Il harness in `eval/` non entra nel pacchetto. Le quattro dipendenze dirette sotto sono state risolte il 2026-10-28; `uv pip compile` più `pip-audit` sul lock risultante non ha trovato vulnerabilità note. Non vengono redistribuite.

| Componente | Versione | Uso | Licenza | Fonte | Supporto | SBOM del fornitore |
|---|---|---|---|---|---|---|
| datasets | 5.1.0 | lettura in streaming di AMI e mTEDx | Apache-2.0 | PyPI, Hugging Face | rilasci attivi | non pubblicata |
| soundfile | 0.14.0 | lettura e scrittura WAV | BSD-3-Clause | PyPI | rilasci attivi | non pubblicata |
| librosa | 1.0.0 | ricampionamento a 16 kHz | ISC | PyPI | rilasci attivi | non pubblicata |
| jiwer | 4.0.0 | WER e CER | Apache-2.0 | PyPI | rilasci attivi | non pubblicata |
