"""Data model: input segment, findings, the model's draft report and the final report."""

from __future__ import annotations

from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class Category(str, Enum):
    accuracy = "accuracy"
    terminology = "terminology"
    fluency = "fluency"
    style = "style"


class Severity(str, Enum):
    minor = "minor"
    moderate = "moderate"
    major = "major"
    critical = "critical"


SEVERITY_ORDER = {
    Severity.minor: 0,
    Severity.moderate: 1,
    Severity.major: 2,
    Severity.critical: 3,
}


class Finding(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    category: Category
    severity: Severity
    span: str = ""
    comment: str = ""


class Segment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    segment_id: str = Field(validation_alias=AliasChoices("segment_id", "id"))
    source: str
    mt: str
    glossary: dict[str, str] = Field(default_factory=dict)


class AgentReport(BaseModel):
    """What the model must return: findings only, never a score."""

    model_config = ConfigDict(populate_by_name=True)

    segment_id: str = Field(validation_alias=AliasChoices("segment_id", "id"))
    findings: list[Finding] = Field(default_factory=list)


class Report(AgentReport):
    """What the library returns: the draft plus the deterministic score."""

    score: int
