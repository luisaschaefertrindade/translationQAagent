import pytest

from mtqa.schemas import Finding
from mtqa.scoring import compute_score


def _f(category, severity):
    return {"category": category, "severity": severity}


def test_empty_findings_score_100():
    assert compute_score([]) == 100


def test_one_critical_accuracy_scores_85():
    assert compute_score([_f("accuracy", "critical")]) == 85


def test_floor_at_zero():
    findings = [_f("accuracy", "critical") for _ in range(15)]
    assert compute_score(findings) == 0


def test_rounding_two_style_minors():
    # 100 - 2 * 1 * 0.8 = 98.4 -> 98
    assert compute_score([_f("style", "minor"), _f("style", "minor")]) == 98


def test_rounding_lexicon_plus_double_space():
    # 100 - (3 * 1.2 + 1 * 0.8) = 95.6 -> 96
    assert compute_score([_f("terminology", "moderate"), _f("style", "minor")]) == 96


def test_accepts_finding_models():
    finding = Finding(category="fluency", severity="major", span="x", comment="y")
    assert compute_score([finding]) == 94  # 100 - 6 * 1.0
