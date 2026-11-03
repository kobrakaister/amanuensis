from __future__ import annotations

import re
from typing import Callable, Sequence

from lecture_study.errors import InvalidModelOutput
from lecture_study.llm import LanguageModel
from lecture_study.prompts import PROMPTS
from lecture_study.transcribe import Segment, render_segments

BLOCK_SECONDS = 720
OVERLAP_SECONDS = 30
NOTE_GAP_SECONDS = 1.0
NOTE_MAX_WORDS = 12
MIN_QUESTIONS = 5
TIMESTAMP = re.compile(r"\[\d{2}:\d{2}:\d{2}\]")
TIMESTAMP_AT_END = re.compile(r"\[\d{2}:\d{2}:\d{2}\]\s*$")
BULLET = re.compile(r"^\s*-\s+(.*?)\s*$", re.MULTILINE)
TOPIC_HEADING = re.compile(r"^## \S", re.MULTILINE)
QUESTION_HEADING = re.compile(r"^### \d+\.", re.MULTILINE)
FORMAT_PLACEHOLDER = "(hh:mm:ss)"

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


def join_for_notes(segments: Sequence[Segment]) -> list[Segment]:
    if not segments:
        return []
    groups: list[Segment] = []
    start = segments[0].start
    end = segments[0].end
    words = segments[0].text.split()
    for segment in segments[1:]:
        extra = segment.text.split()
        if segment.start - end <= NOTE_GAP_SECONDS and len(words) + len(extra) <= NOTE_MAX_WORDS:
            words.extend(extra)
            end = segment.end
            continue
        groups.append(Segment(start, end, " ".join(words)))
        start, end, words = segment.start, segment.end, extra
    groups.append(Segment(start, end, " ".join(words)))
    return groups


def _content_bullets(text: str) -> list[str]:
    bullets = []
    for body in BULLET.findall(text):
        without_time = TIMESTAMP.sub("", body).strip()
        if without_time and without_time != FORMAT_PLACEHOLDER:
            bullets.append(body)
    return bullets


def notes_are_valid(text: str) -> bool:
    if FORMAT_PLACEHOLDER in text or not TOPIC_HEADING.search(text):
        return False
    bullets = _content_bullets(text)
    return bool(bullets) and all(TIMESTAMP_AT_END.search(bullet) for bullet in bullets)


def mindmap_is_valid(text: str) -> bool:
    return text.startswith("# ") and bool(TOPIC_HEADING.search(text))


def questions_are_valid(text: str) -> bool:
    return len(QUESTION_HEADING.findall(text)) >= MIN_QUESTIONS and bool(TIMESTAMP.search(text))


def normalize_timestamps(text: str) -> str:
    text = re.sub(r"\[(\d{2}:\d{2}:\d{2})-\d{2}:\d{2}:\d{2}\]", r"[\1]", text)
    text = re.sub(r"\(\s*(\d{2}:\d{2}:\d{2})\s*-\s*\d{2}:\d{2}:\d{2}\s*\)", r"[\1]", text)
    return re.sub(r"\((\d{2}:\d{2}:\d{2})\)", r"[\1]", text)


def _times_are_copied(notes: str, source: str) -> bool:
    found = set(TIMESTAMP.findall(notes))
    return bool(found) and found <= set(TIMESTAMP.findall(source))


def time_example(transcript: str, language: str) -> str:
    match = re.search(r"^\[(\d{2}:\d{2}:\d{2})\]\s+(\S.*?)\s*$", transcript, re.MULTILINE)
    if match:
        stamp, words = match.group(1), match.group(2)
    else:
        stamp, words = "00:00:00", "frase" if language == "it" else "sentence"
    if language == "en":
        return f"Example. From the line [{stamp}] {words} write: - {words} [{stamp}]"
    return f"Esempio. Dalla riga [{stamp}] {words} scrivi: - {words} [{stamp}]"


def _strip_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        lines = lines[1:-1]
    return "\n".join(lines).strip()


class StudyComposer:
    def __init__(self, model: LanguageModel, call: Call = lambda operation: operation()) -> None:
        self._model = model
        self._call = call

    def _generate(
        self,
        language: str,
        kind: str,
        text: str,
        is_valid: Callable[[str], bool],
        example: str | None = None,
    ) -> str:
        prompts = PROMPTS[language]
        fields = {"text": text}
        if example is not None:
            fields["example"] = example
        prompt = prompts[kind].format(**fields)
        output = ""
        for _ in range(2):
            output = normalize_timestamps(_strip_fence(self._call(lambda: self._model.complete(prompts["system"], prompt))))
            if is_valid(output):
                return output
        raise InvalidModelOutput(f"invalid response for {kind}", output)

    def _repair_notes(self, language: str, notes: str, source: str) -> str:
        prompts = PROMPTS[language]
        prompt = prompts["notes_repair"].format(notes=notes, text=source, example=time_example(source, language))
        output = normalize_timestamps(_strip_fence(self._call(lambda: self._model.complete(prompts["system"], prompt))))
        if notes_are_valid(output) and _times_are_copied(output, source):
            return output
        raise InvalidModelOutput("invalid response for notes", output)

    def notes(self, segments: Sequence[Segment], language: str) -> str:
        parts: list[str] = []
        for block in make_blocks(segments):
            source = render_segments(join_for_notes(block))

            def accept(output: str, transcript: str = source) -> bool:
                return notes_are_valid(output) and _times_are_copied(output, transcript)

            try:
                parts.append(self._generate(language, "notes", source, accept, time_example(source, language)))
            except InvalidModelOutput as exc:
                try:
                    parts.append(self._repair_notes(language, exc.partial, source))
                except InvalidModelOutput as repair_error:
                    raise InvalidModelOutput(str(repair_error), "\n\n".join([*parts, repair_error.partial])) from repair_error
        return f"{PROMPTS[language]['notes_title']}\n\n" + "\n\n".join(parts) + "\n"

    def mindmap(self, notes: str, language: str) -> str:
        return self._generate(language, "mindmap", notes, mindmap_is_valid) + "\n"

    def questions(self, notes: str, language: str) -> str:
        body = self._generate(language, "questions", notes, questions_are_valid)
        return f"{PROMPTS[language]['questions_title']}\n\n{body}\n"
