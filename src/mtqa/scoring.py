"""Penalty-based scoring, computed in code so it is deterministic and testable.

score = max(0, round-half-up(100 - sum(severity_points * category_weight)))
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping

SEVERITY_POINTS: dict[str, int] = {
    "minor": 1,
    "moderate": 3,
    "major": 6,
    "critical": 10,
}

CATEGORY_WEIGHTS: dict[str, Decimal] = {
    "accuracy": Decimal("1.5"),
    "terminology": Decimal("1.2"),
    "fluency": Decimal("1.0"),
    "style": Decimal("0.8"),
}


def compute_score(findings: Iterable) -> int:
    penalty = Decimal(0)
    for finding in findings:
        if isinstance(finding, Mapping):
            category = str(finding.get("category"))
            severity = str(finding.get("severity"))
        else:
            category = str(getattr(finding, "category"))
            severity = str(getattr(finding, "severity"))
        penalty += Decimal(SEVERITY_POINTS[severity]) * CATEGORY_WEIGHTS[category]
    raw = Decimal(100) - penalty
    if raw <= 0:
        return 0
    return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
