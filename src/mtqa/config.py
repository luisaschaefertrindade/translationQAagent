"""Endpoint and run configuration from mtqa.toml, env vars and CLI flags.

Precedence: explicit argument > environment variable > mtqa.toml > default.
The file lives at the repo root (or wherever MTQA_CONFIG points). Never put
API keys in the file; use the MTQA_API_KEY environment variable.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: str | Path | None = None) -> dict:
    file = Path(path or os.environ.get("MTQA_CONFIG", ROOT / "mtqa.toml"))
    data = {}
    if file.exists():
        with open(file, "rb") as handle:
            raw = tomllib.load(handle)
        data = {k: v for k, v in raw.get("endpoint", {}).items()}
    env = {
        "base_url": os.environ.get("MTQA_BASE_URL"),
        "model": os.environ.get("MTQA_MODEL"),
        "tracking_uri": os.environ.get("MTQA_TRACKING_URI"),
        "experiment": os.environ.get("MTQA_EXPERIMENT"),
    }
    merged = {
        "base_url": "http://localhost:13305/v1",
        "model": "",
        "tracking_uri": None,
        "experiment": "mt-qa-agent",
    }
    for source in (data, env):
        for key, value in source.items():
            if value:
                merged[key] = value
    return merged


@dataclass
class Settings:
    base_url: str
    model: str
    tracking_uri: str | None
    experiment: str

    @classmethod
    def load(cls, overrides: dict | None = None, path: str | Path | None = None) -> "Settings":
        merged = load(path)
        for key, value in (overrides or {}).items():
            if value:
                merged[key] = value
        return cls(**merged)
