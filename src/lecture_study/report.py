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
