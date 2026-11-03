from __future__ import annotations

from typing import Any

from lecture_study.jobs import JobState
from lecture_study.transcribe import format_timestamp


def _audio_lines(source: dict[str, Any]) -> list[str]:
    analysis = source.get("analysis")
    if not analysis:
        return ["- Not analyzed yet"]
    decision = f"apply high-pass at {analysis['highpass_hz']} Hz" if analysis["apply"] else "no high-pass"
    lines = [
        f"- Energy 20-80 Hz: {analysis['low']:.4g}",
        f"- Energy 80-300 Hz: {analysis['voice']:.4g}",
        f"- Ratio: {analysis['ratio']:.3f} (threshold {analysis['threshold']})",
        f"- Decision: {decision}",
    ]
    if not analysis["apply"]:
        lines.append("- Energy below 80 Hz is low. A high-pass does not reduce broadband noise.")
    preparation = source.get("preparation")
    if preparation:
        lines.append(f"- Applied: {'yes' if preparation['highpass_applied'] else 'no'}")
        if preparation["note"]:
            lines.append(f"- Note: {preparation['note']}")
    return lines


def _transcription_lines(source: dict[str, Any]) -> list[str]:
    transcription = source.get("transcription")
    if not transcription:
        return ["- Not transcribed yet"]
    return [
        f"- Language: {transcription['language']} (probability {transcription['language_probability']:.2f})",
        f"- Model: {transcription['model']}",
        f"- Device: {transcription['device']}",
    ]


def render_report(state: JobState, source: dict[str, Any]) -> str:
    duration = source.get("duration_seconds")
    lines = [
        "# Processing report",
        "",
        f"- Status: {state.status}",
        f"- Stage: {state.stage or '-'}",
        f"- Message: {state.message or '-'}",
        f"- Completed stages: {', '.join(state.completed) or '-'}",
        "",
        "## Source",
        "",
        f"- File: {source.get('path', '-')}",
        f"- SHA-256: {source.get('sha256', '-')}",
        f"- Duration: {format_timestamp(duration) if duration is not None else '-'}",
        f"- Format: {source.get('format', '-')}",
        "",
        "## Audio",
        "",
        *_audio_lines(source),
        "",
        "## Transcription",
        "",
        *_transcription_lines(source),
        "",
        "## Events",
        "",
        *([f"- {event}" for event in state.events] or ["- None"]),
    ]
    return "\n".join(lines) + "\n"
