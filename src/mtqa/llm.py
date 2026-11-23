"""Chat clients behind one small interface.

`OpenAICompatClient` talks to any OpenAI-compatible /chat/completions endpoint, so
models swap by changing a base URL and a name. `FakeClient` lets tests and CI run
the whole agent loop without ever touching the network.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Iterable, Protocol

import httpx


class ChatClient(Protocol):
    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        """Return the assistant message dict: {content, tool_calls?}."""
        ...


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        temperature: float = 0.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("MTQA_BASE_URL", "http://localhost:13305/v1")).rstrip("/")
        self.model = model or os.environ.get("MTQA_MODEL", "")
        self.api_key = api_key or os.environ.get("MTQA_API_KEY", "")
        self.timeout = timeout
        self.temperature = temperature

    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = httpx.post(
            f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]


class FakeClient:
    """Scripted client for tests.

    `responses` is an iterable of message dicts or callables
    (messages, tools) -> message. Each chat() pops the next one.
    """

    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        import copy

        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        if not self._responses:
            raise AssertionError("FakeClient ran out of scripted responses")
        item = self._responses.pop(0)
        return copy.deepcopy(item(messages, tools) if callable(item) else item)


def text_msg(content: str) -> dict:
    return {"content": content}


def tool_call_msg(name: str, arguments: dict, call_id: str = "c1") -> dict:
    return {
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": _dump(arguments)},
            }
        ],
    }


def _dump(arguments: Any) -> str:
    import json

    return json.dumps(arguments, ensure_ascii=False)
