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
