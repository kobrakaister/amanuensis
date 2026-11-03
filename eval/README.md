# WER evaluation

Measures the local transcription service on a streaming sample. It does not download the whole datasets. The config, split, and column names were read from a real example on 2026-10-28.

| Language | Dataset | Config | Split | Audio | Reference | Grouping |
|---|---|---|---|---|---|---|
| en | `edinburghcstr/ami` | `sdm` | `test` | `audio` (16 kHz) | `text` | `meeting_id` |
| it | `deepdml/mtedx` | `it` | `test` | `audio` (44.1 kHz in the first example) | `transcript` | `talk_id` |

The Italian split is named `test`, next to `train` and `valid`. AMI `sdm` has `train`, `validation`, and `test`.

There is no HTTP endpoint. `client.py` uses the same rule as `FasterWhisperTranscriber` and the `large-v3` model. The service chooses the decode language: Italian or English when the probability is at least 0.80, otherwise Italian. The model is loaded on the first call and reused for the rest of the batch. The first sample's time includes that load.

`longform` joins consecutive segments from the same meeting or talk up to about 5 minutes, with 0.3 seconds of silence between segments, and joins the references in the same order. Saved audio is always mono 16 kHz WAV under `out-dir/audio/`.

Normalization lowercases the text, removes punctuation, and compresses spaces. Internal apostrophes stay, so `l'aula` remains one word. In English, bracket tags are removed as well, for example `[laughter]`. In the first Italian example the reference starts with `[Roberto Battiston]`: the brackets are dropped and the name stays in the text.

Aggregate WER is the total number of errors divided by the total number of reference words, not the mean of the per-sample WER values. A service error is written in the `hypothesis` column of the CSV and the batch continues. A segment that cannot be decoded is skipped and does not count in the sample.

From the repository root, with the project virtual environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\mba-studio\.venv"
uv pip install -r eval/requirements.txt
uv run python eval/eval_asr.py --lang en --n-samples 50 --mode segment --out-dir eval/out/en-segment
uv run python eval/eval_asr.py --lang it --n-samples 50 --mode longform --out-dir eval/out/it-longform
```

Results are `results.csv` and `summary.json` inside the output folder.
