import json

from mtqa.agent import FEW_SHOT_PATH, TOOL_SCHEMAS, build_messages, system_prompt
from mtqa.schemas import AgentReport, Segment

SEGMENT = Segment(segment_id="t1", source="Save the file.", mt="Salve o arquivo.", glossary={"save": "salvar"})
TOOL_NAMES = {s["function"]["name"] for s in TOOL_SCHEMAS}


def test_variant_a_prompt_contains_no_tool_name_and_no_tool_results():
    messages = build_messages(SEGMENT, "A")
    blob = json.dumps(messages, ensure_ascii=False)
    for name in TOOL_NAMES:
        assert name not in blob
    assert "tool_results" not in blob


def test_variant_b_prompt_mentions_tools_and_includes_tool_results():
    messages = build_messages(SEGMENT, "B")
    assert "tool_results" in messages[-1]["content"]
    assert "check_glossary" in messages[0]["content"]


def test_variant_c_prompt_has_tools_section():
    prompt = system_prompt("C")
    assert "check_dialect_and_style" in prompt
    assert "Call the ones that are relevant" in prompt


def test_few_shot_outputs_never_contain_a_score():
    examples = json.loads(FEW_SHOT_PATH.read_text(encoding="utf-8"))
    for example in examples:
        assert "score" not in example["output"]
        AgentReport.model_validate(example["output"])


def test_few_shot_note_never_reaches_the_model():
    messages = build_messages(SEGMENT, "B")
    assert "note" not in json.dumps(messages, ensure_ascii=False)


def test_unknown_variant_rejected():
    import pytest

    with pytest.raises(ValueError):
        system_prompt("D")
