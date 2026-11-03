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


def test_notes_prompt_joins_short_lines_and_keeps_a_pause():
    fragments = [
        Segment(0.0, 1.0, "con la"),
        Segment(1.0, 2.0, "Polonia"),
        Segment(2.0, 3.0, "con il Brasile"),
        Segment(8.0, 9.0, "altra frase"),
    ]
    model = ScriptedModel(["## Tema\n- punto [00:00:00]"])
    StudyComposer(model).notes(fragments, "it")
    prompt = model.prompts[0]
    assert "[00:00:00] con la Polonia con il Brasile" in prompt
    assert "[00:00:01]" not in prompt
    assert "[00:00:08] altra frase" in prompt


def test_notes_prompt_starts_a_new_line_after_twelve_words():
    fragments = [Segment(float(i), float(i) + 1, f"parola{i}") for i in range(20)]
    model = ScriptedModel(["## Tema\n- punto [00:00:00]"])
    StudyComposer(model).notes(fragments, "it")
    prompt = model.prompts[0]
    assert "[00:00:00] " + " ".join(f"parola{i}" for i in range(12)) in prompt
    assert "[00:00:12] parola12" in prompt


def test_notes_join_block_notes_under_one_title():
    model = ScriptedModel(["## Domanda e offerta\n- Prezzo di equilibrio [00:00:00]"])
    notes = StudyComposer(model).notes(segments(3), "it")
    assert notes.startswith("# Appunti\n\n## Domanda e offerta")
    assert "[00:00:00] frase 0" in model.prompts[0]
    assert "italiano" in model.systems[0]


def test_invalid_reply_is_retried_once_then_reported_with_partial():
    model = ScriptedModel(["testo senza struttura", "ancora niente", "ancora niente"])
    with pytest.raises(InvalidModelOutput) as caught:
        StudyComposer(model).notes(segments(3), "it")
    assert caught.value.partial == "ancora niente"
    assert len(model.prompts) == 3


def test_time_range_is_stored_as_its_start():
    model = ScriptedModel(["## Topic\n- point [00:34:48-00:34:52]"])
    notes = StudyComposer(model).notes([Segment(2088.0, 2092.0, "point")], "en")
    assert "[00:34:48]" in notes
    assert "00:34:52" not in notes


def test_spaced_parenthesis_range_keeps_only_the_start():
    model = ScriptedModel(["## Tema\n- punto (00:11:49 - 00:17:00)"])
    notes = StudyComposer(model).notes([Segment(709.0, 720.0, "punto")], "it")
    assert "[00:11:49]" in notes
    assert "00:17:00" not in notes


def test_notes_repair_copies_a_time_from_the_transcript():
    model = ScriptedModel([
        "## Tema\n- punto senza orario",
        "## Tema\n- ancora senza orario",
        "## Tema\n- punto [00:00:00]",
    ])
    notes = StudyComposer(model).notes(segments(1), "it")
    assert "[00:00:00]" in notes
    assert "ancora senza orario" in model.prompts[-1]
    assert "[00:00:00] frase 0" in model.prompts[-1]


def test_a_timestamp_on_its_own_line_does_not_save_the_bullets():
    loose = "## Tema\n- definizione\n- esempio\n- [00:00:00]"
    spoken = [Segment(0.0, 1.0, "definizione"), Segment(8.0, 9.0, "esempio")]
    model = ScriptedModel([
        loose,
        loose,
        "## Tema\n- definizione [00:00:00]\n- esempio [00:00:08]",
    ])
    notes = StudyComposer(model).notes(spoken, "it")
    assert "- definizione [00:00:00]" in notes
    assert "- esempio [00:00:08]" in notes
    assert len(model.prompts) == 3


def test_notes_reject_an_invented_time_before_repair():
    invented = "## Tema\n- punto [00:09:09]"
    model = ScriptedModel([invented, invented, "## Tema\n- punto [00:00:00]"])
    notes = StudyComposer(model).notes(segments(1), "it")
    assert "- punto [00:00:00]" in notes
    assert "[00:09:09]" not in notes
    assert len(model.prompts) == 3


def test_format_placeholder_is_rejected():
    echoed = "## Tema\n- punto [00:00:00](hh:mm:ss)"
    model = ScriptedModel([echoed, echoed, "## Tema\n- punto [00:00:00]"])
    notes = StudyComposer(model).notes(segments(1), "it")
    assert "(hh:mm:ss)" not in notes
    assert len(model.prompts) == 3


def test_italian_notes_prompt_asks_for_one_point_per_idea():
    model = ScriptedModel(["## Tema\n- punto [00:00:00]"])
    StudyComposer(model).notes(segments(1), "it")
    prompt = model.prompts[0]
    assert "uno per idea" in prompt
    assert "definizioni, concetti, esempi e collegamenti" not in prompt


def test_english_notes_prompt_asks_for_one_point_per_idea():
    model = ScriptedModel(["## Topic\n- point [00:00:00]"])
    StudyComposer(model).notes(segments(1), "en")
    prompt = model.prompts[0]
    assert "one bullet per idea" in prompt
    assert "definitions, concepts, examples and connections" not in prompt


def test_notes_prompt_shows_one_real_line_as_the_pattern():
    spoken = [Segment(24.0, 30.0, "ci diamo del tu")]
    model = ScriptedModel(["## Tema\n- punto [00:00:24]"])
    StudyComposer(model).notes(spoken, "it")
    prompt = model.prompts[0]
    assert "Esempio. Dalla riga [00:00:24] ci diamo del tu scrivi: - ci diamo del tu [00:00:24]" in prompt
    assert "[hh:mm:ss]" not in prompt


def test_english_notes_prompt_shows_one_real_line_as_the_pattern():
    spoken = [Segment(24.0, 30.0, "we use first names")]
    model = ScriptedModel(["## Topic\n- point [00:00:24]"])
    StudyComposer(model).notes(spoken, "en")
    prompt = model.prompts[0]
    assert "Example. From the line [00:00:24] we use first names write: - we use first names [00:00:24]" in prompt
    assert "[hh:mm:ss]" not in prompt


def test_notes_repair_prompt_shows_one_real_line_as_the_pattern():
    spoken = [Segment(24.0, 30.0, "ci diamo del tu")]
    bad = "## Tema\n- punto (00:24-00:38)"
    model = ScriptedModel([bad, bad, "## Tema\n- punto [00:00:24]"])
    StudyComposer(model).notes(spoken, "it")
    assert "Esempio. Dalla riga [00:00:24] ci diamo del tu scrivi: - ci diamo del tu [00:00:24]" in model.prompts[-1]


def test_notes_repair_rejects_an_invented_time():
    model = ScriptedModel([
        "## Tema\n- punto senza orario",
        "## Tema\n- ancora senza orario",
        "## Tema\n- punto [00:09:09]",
    ])
    with pytest.raises(InvalidModelOutput) as caught:
        StudyComposer(model).notes(segments(1), "it")
    assert "[00:09:09]" in caught.value.partial
    assert len(model.prompts) == 3


def test_parenthesis_times_are_stored_as_square_brackets():
    ranged = ScriptedModel(["## Tema\n- punto (00:03:48-00:04:04)"])
    notes = StudyComposer(ranged).notes([Segment(228.0, 244.0, "punto")], "it")
    assert "[00:03:48]" in notes
    assert "00:04:04" not in notes

    single = ScriptedModel(["## Tema\n- punto (00:11:40)"])
    notes = StudyComposer(single).notes([Segment(700.0, 710.0, "punto")], "it")
    assert "[00:11:40]" in notes
    assert "(00:11:40)" not in notes


def test_parentheses_around_words_stay():
    model = ScriptedModel(["## Tema\n- ricavi (modello di ricavi) [00:00:00]"])
    notes = StudyComposer(model).notes(segments(1), "it")
    assert "(modello di ricavi)" in notes


def test_second_attempt_can_recover():
    model = ScriptedModel(["niente", "## Tema\n- punto [00:00:00]"])
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
    model = ScriptedModel(["## Topic\n- point [00:00:00]"])
    notes = StudyComposer(model).notes(segments(1), "en")
    assert notes.startswith("# Notes\n\n## Topic")
    assert "Transcript:" in model.prompts[0]


def test_call_wrapper_is_used_for_every_model_call():
    calls = []

    def call(operation):
        calls.append(1)
        return operation()

    StudyComposer(ScriptedModel(["## Tema\n- punto [00:00:00]"]), call=call).notes(segments(3), "it")
    assert calls == [1]
