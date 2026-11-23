import json

import pytest

from mtqa.agent import AgentError, parse_draft, review
from mtqa.llm import FakeClient, text_msg, tool_call_msg
from mtqa.schemas import Segment

SEGMENT = Segment(
    segment_id="t1",
    source="Hello {0}, {1} added you to team \"{2}\".",
    mt="Olá {0}, foi adicionado à equipe.",
    glossary={"team": "equipe"},
)


def draft(findings=None):
    return json.dumps({"segment_id": "t1", "findings": findings or []})


def test_valid_json_passes_and_score_is_injected():
    client = FakeClient([text_msg(draft([{"category": "style", "severity": "minor", "span": "x", "comment": "y"}]))])
    report = review(SEGMENT, client, variant="A")
    assert report.score == 99
    assert report.segment_id == "t1"


def test_invalid_json_triggers_retry():
    client = FakeClient([text_msg("not json at all"), text_msg(draft())])
    report = review(SEGMENT, client, variant="A")
    assert report.findings == []
    assert len(client.calls) == 2
    assert "Invalid report" in client.calls[1]["messages"][-1]["content"]


def test_two_failures_raise_clear_error():
    client = FakeClient([text_msg("nope"), text_msg("still nope"), text_msg("nope again")])
    with pytest.raises(AgentError):
        review(SEGMENT, client, variant="A")
    assert len(client.calls) == 3


def test_variant_a_gets_no_tools():
    client = FakeClient([text_msg(draft())])
    review(SEGMENT, client, variant="A")
    assert client.calls[0]["tools"] is None


def test_variant_c_tool_loop_executes_check():
    call = tool_call_msg("check_placeholders", {"source": SEGMENT.source, "mt": SEGMENT.mt})
    client = FakeClient([call, text_msg(draft())])
    report = review(SEGMENT, client, variant="C")
    assert report is not None
    tool_msgs = [m for m in client.calls[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs
    payload = json.loads(tool_msgs[0]["content"])
    assert any(r["token"] == "{1}" for r in payload)


def test_variant_c_broken_tool_call_does_not_crash():
    call = tool_call_msg("check_unknown", {})
    client = FakeClient([call, text_msg(draft())])
    report = review(SEGMENT, client, variant="C")
    tool_msgs = [m for m in client.calls[1]["messages"] if m["role"] == "tool"]
    assert "error" in json.loads(tool_msgs[0]["content"])


def test_segment_id_drift_is_corrected():
    client = FakeClient([text_msg(json.dumps({"segment_id": "WRONG", "findings": []}))])
    report = review(SEGMENT, client, variant="A")
    assert report.segment_id == "t1"


def test_code_fenced_json_is_parsed():
    assert parse_draft('```json\n{"segment_id": "x", "findings": []}\n```').segment_id == "x"


def test_variant_b_prompt_has_tool_results():
    client = FakeClient([text_msg(draft())])
    review(SEGMENT, client, variant="B")
    user = client.calls[0]["messages"][-1]["content"]
    assert "tool_results" in user


def test_variant_c_prefills_placeholder_results():
    client = FakeClient([text_msg(draft())])
    review(SEGMENT, client, variant="C")
    user = json.loads(client.calls[0]["messages"][-1]["content"])
    assert "tool_results" in user
    assert user["tool_results"]["check_placeholders"]


def test_variant_c_plain_segment_gets_no_prefill():
    plain = Segment(segment_id="t2", source="Save the file.", mt="Salve o arquivo.")
    client = FakeClient([text_msg(draft())])
    review(plain, client, variant="C")
    user = json.loads(client.calls[0]["messages"][-1]["content"])
    assert "tool_results" not in user


def test_json_mode_requested_on_final_calls():
    client = FakeClient([text_msg(draft())])
    review(SEGMENT, client, variant="A")
    assert client.calls[0]["json_mode"] is True


def test_json_mode_only_after_tool_round():
    call = tool_call_msg("check_placeholders", {"source": SEGMENT.source, "mt": SEGMENT.mt})
    client = FakeClient([call, text_msg(draft())])
    review(SEGMENT, client, variant="C")
    assert client.calls[0]["json_mode"] is False
    assert client.calls[1]["json_mode"] is True
