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
