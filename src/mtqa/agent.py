"""Prompt assembly, the tool-calling loop, JSON validation and retry.

review(segment, client, variant) returns a scored `Report`. The model emits a
draft (`AgentReport`); the score is injected in code, never trusted from the model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .llm import ChatClient
from .schemas import AgentReport, Report, Segment
from .scoring import compute_score
from . import tools as checks

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PATH = PROMPT_DIR / "system.md"
FEW_SHOT_PATH = PROMPT_DIR / "few_shot.json"
MAX_RETRIES = 2

VARIANTS = ("A", "B", "C")

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "check_glossary",
            "description": "Report glossary terms whose approved translation is "
            "missing from the MT or whose forbidden variant is present.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "mt": {"type": "string"},
                    "glossary": {"type": "object"},
                },
                "required": ["source", "mt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_placeholders",
            "description": "Compare placeholders, tags, numbers, dates and URLs "
            "between source and MT; report dropped, added or altered tokens.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "mt": {"type": "string"},
                },
                "required": ["source", "mt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_dialect_and_style",
            "description": "Report PT-EU lexicon markers, spacing, punctuation, "
            "capitalization and register problems in the MT.",
            "parameters": {
                "type": "object",
                "properties": {"mt": {"type": "string"}},
                "required": ["mt"],
            },
        },
    },
]

_TOOL_NAMES = {s["function"]["name"] for s in TOOL_SCHEMAS}


def _section(markdown: str, name: str) -> str:
    match = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", markdown, re.MULTILINE | re.DOTALL)
    if not match:
        raise KeyError(f"section {name!r} not found in system prompt")
    return match.group(1).strip()


def prompt_version(path: Path = SYSTEM_PATH) -> str:
    match = re.search(r"prompt_version:\s*(\S+)", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "unknown"


def load_few_shots(path: Path = FEW_SHOT_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def system_prompt(variant: str, path: Path = SYSTEM_PATH) -> str:
    markdown = path.read_text(encoding="utf-8")
    base = _section(markdown, "BASE")
    if variant == "A":
        return base
    if variant == "B":
        return base + "\n\n" + _section(markdown, "TOOLS_PIPELINE")
    if variant == "C":
        return base + "\n\n" + _section(markdown, "TOOLS_AGENT")
    raise ValueError(f"unknown variant {variant!r}")


def _strip_notes(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_notes(v) for k, v in obj.items() if k != "note"}
    if isinstance(obj, list):
        return [_strip_notes(v) for v in obj]
    return obj


def _few_shot_messages(variant: str) -> list[dict]:
    messages: list[dict] = []
    for example in load_few_shots():
        payload = _strip_notes(example["input"])
        if variant == "A":
            payload.pop("tool_results", None)
        elif "tool_results" in example:
            payload["tool_results"] = _strip_notes(example["tool_results"])
        messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
        messages.append(
            {"role": "assistant", "content": json.dumps(example["output"], ensure_ascii=False)}
        )
    return messages


def user_payload(segment: Segment, variant: str) -> dict:
    payload = {
        "segment_id": segment.segment_id,
        "source": segment.source,
        "mt": segment.mt,
        "glossary": segment.glossary,
    }
    if variant == "B":
        payload["tool_results"] = run_tools(segment)
    elif variant == "C":
        # Pre-filter: a 0.6B-class model declines ~half of needed tool calls
        # (probe_tools.py, 2026-11), but this check is free, so run it up front
        # and hand over any non-empty result instead of hoping for a call.
        hits = checks.check_placeholders(segment.source, segment.mt)
        if hits:
            payload["tool_results"] = {"check_placeholders": hits}
    return payload


def build_messages(segment: Segment, variant: str) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt(variant)}]
    messages.extend(_few_shot_messages(variant))
    messages.append({"role": "user", "content": json.dumps(user_payload(segment, variant), ensure_ascii=False)})
    return messages


def run_tools(segment: Segment) -> dict[str, list[dict]]:
    return checks.run_all(segment.source, segment.mt, segment.glossary)


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def parse_draft(raw: str) -> AgentReport:
    text = _FENCE_RE.sub("", raw or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"output is not valid JSON: {exc}") from exc
    return AgentReport.model_validate(data)


class AgentError(RuntimeError):
    pass


def _execute_tool(name: str, arguments: dict, segment: Segment) -> Any:
    if name == "check_glossary":
        glossary = arguments.get("glossary") or segment.glossary or None
        return checks.check_glossary(arguments["source"], arguments["mt"], glossary)
    if name == "check_placeholders":
        return checks.check_placeholders(arguments["source"], arguments["mt"])
    if name == "check_dialect_and_style":
        return checks.check_dialect_and_style(arguments["mt"])
    raise ValueError(f"unknown tool {name!r}")


def review(
    segment: Segment,
    client: ChatClient,
    variant: str = "C",
    max_retries: int = MAX_RETRIES,
    drafts: list[str] | None = None,
) -> Report:
    """Run one segment through the model and return a validated, scored report.

    Invalid JSON is fed back to the model with the validation error, at most
    `max_retries` times. After that an AgentError is raised. Every final content
    string the model produced is appended to `drafts` (for validity-rate metrics).
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    messages = build_messages(segment, variant)
    tools = TOOL_SCHEMAS if variant == "C" else None

    attempts = max_retries + 1
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            reply = _collect_reply(client, messages, tools, segment, drafts)
        except ValueError as exc:
            last_error = exc
            messages.append({"role": "user", "content": f"Invalid report: {exc}. Return only the JSON object."})
            continue
        return Report(
            segment_id=segment.segment_id,
            findings=reply.findings,
            score=compute_score(reply.findings),
        )
    raise AgentError(f"model failed to produce a valid report after {attempts} attempts: {last_error}")


def _collect_reply(
    client: ChatClient,
    messages: list[dict],
    tools: list[dict] | None,
    segment: Segment,
    drafts: list[str] | None = None,
) -> AgentReport:
    """One model turn, including at most one round of tool calls.

    `json_mode` is requested whenever the expected reply is the final JSON
    report, so compliant endpoints constrain decoding. The tool round itself
    runs without it (tools + response_format is unsupported on some servers).
    """
    reply = client.chat(messages, tools, json_mode=tools is None)
    if tools and reply.get("tool_calls"):
        messages.append({"role": "assistant", **{k: v for k, v in reply.items() if k != "role"}})
        for call in reply["tool_calls"]:
            fn = call["function"]
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
                result = _execute_tool(fn["name"], arguments, segment)
            except Exception as exc:  # a broken call must not kill the run
                result = {"error": str(exc)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        # tools have run; the rest is pure JSON generation, constrain it
        reply = client.chat(messages, None, json_mode=True)
    content = reply.get("content") or ""
    if drafts is not None and content:
        drafts.append(content)
    if content:
        messages.append({"role": "assistant", "content": content})
    draft = parse_draft(content)
    if draft.segment_id != segment.segment_id:
        draft.segment_id = segment.segment_id  # tolerate echo drift, keep gold id
    return draft
