# Dependencies

Checked with `pip-audit` on 2026-10-27. None of these are redistributed. The project runs only on this PC.

| Component | Version | Use | License | Source | Support | Vendor SBOM |
|---|---|---|---|---|---|---|
| numpy | 2.5.4 | audio band analysis | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | PyPI | active releases | not published |
| faster-whisper | 1.2.1 | transcription | MIT | PyPI, SYSTRAN | active releases | not published |
| nvidia-cublas-cu12 | 12.9.2.10 | GPU libraries for CTranslate2 | NVIDIA proprietary | PyPI, NVIDIA | CUDA 12 supported | not published |
| nvidia-cudnn-cu12 | 9.27.0.42 | GPU libraries for CTranslate2 | NVIDIA proprietary | PyPI, NVIDIA | cuDNN 9 supported | not published |
| pytest | 9.1.1 | tests, development only | MIT | PyPI | active releases | not published |
| ffmpeg | 9.0.2 | decode and filter | LGPL/GPL | winget Gyan.FFmpeg; the studio also downloads the GyanD zip `ffmpeg-9.0.2-essentials_build.zip` (SHA-256 `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`) for Windows only | active releases | not published |
| Ollama | 0.40.11 | local language model | MIT | winget Ollama.Ollama; the studio downloads the GitHub zips for `v0.40.11` listed in `sha256sum.txt` | active releases | not published |
| uv | 0.11.16 | studio environment | MIT OR Apache-2.0 | GitHub astral-sh/uv, checksum in the dist-manifest | active releases | not published |

The harness in `eval/` is not part of the package. The four direct dependencies below were resolved on 2026-10-28. `uv pip compile` plus `pip-audit` on the resulting lock found no known vulnerabilities. They are not redistributed.

| Component | Version | Use | License | Source | Support | Vendor SBOM |
|---|---|---|---|---|---|---|
| datasets | 5.1.0 | streaming reads of AMI and mTEDx | Apache-2.0 | PyPI, Hugging Face | active releases | not published |
| soundfile | 0.14.0 | WAV read and write | BSD-3-Clause | PyPI | active releases | not published |
| librosa | 1.0.0 | resampling to 16 kHz | ISC | PyPI | active releases | not published |
| jiwer | 4.0.0 | WER and CER | Apache-2.0 | PyPI | active releases | not published |
