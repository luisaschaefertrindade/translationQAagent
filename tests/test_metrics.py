from mtqa.metrics import aggregate, match_findings, match_pairs, prf, severity_agreement, span_match, strict_match


def _f(category, severity, span=""):
    return {"category": category, "severity": severity, "span": span}


def test_span_match_is_accent_and_case_insensitive_both_ways():
    assert span_match("Telemovel", "telemóvel")
    assert span_match("número de telemóvel", "telemóvel")
    assert not span_match("", "telemóvel")
    assert not span_match("janela", "portas")


def test_category_match_ignores_span():
    pred = [_f("accuracy", "major", "totally wrong span")]
    gold = [_f("accuracy", "critical", "500")]
    tp, fp, fn = match_findings(pred, gold)
    assert (tp, fp, fn) == (1, 0, 0)


def test_strict_match_requires_span_overlap():
    pred = [_f("accuracy", "major", "totally wrong span")]
    gold = [_f("accuracy", "critical", "500")]
    tp, fp, fn = strict_match(pred, gold)
    assert (tp, fp, fn) == (0, 1, 1)


def test_strict_match_counts_right_place_right_category():
    pred = [_f("accuracy", "major", "500")]
    gold = [_f("accuracy", "critical", "500")]
    assert strict_match(pred, gold) == (1, 0, 0)


def test_greedy_closest_severity_first():
    pred = [_f("style", "minor", "a"), _f("style", "moderate", "b")]
    gold = [_f("style", "major", "b"), _f("style", "minor", "a")]
    pairs = match_pairs(pred, gold)
    assert sorted(pairs) == [(0, 1), (1, 0)]


def test_severity_agreement_within_one_level():
    pred = [_f("terminology", "moderate", "x"), _f("terminology", "critical", "y")]
    gold = [_f("terminology", "moderate", "x"), _f("terminology", "minor", "y")]
    agree, matched = severity_agreement(pred, gold)
    assert matched == 2
    assert agree == 1  # minor vs critical is two levels apart


def test_prf_zero_division_safe():
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)


def test_aggregate_counts_failed_segment_as_fn():
    results = [
        {
            "gold": [_f("accuracy", "critical", "500")],
            "pred": [],
            "error": "boom",
            "first_valid": False,
            "latency": 1.0,
        }
    ]
    metrics = aggregate(results)
    assert metrics["recall"] == 0.0
    assert metrics["json_valid_rate"] == 0.0
    assert "score_mae" in metrics


def test_aggregate_happy_path():
    pred = [_f("style", "minor", "Por favor,")]
    gold = [_f("style", "minor", "Por favor,")]
    metrics = aggregate(
        [{"gold": gold, "pred": pred, "score": 99, "gold_score": 99, "first_valid": True, "latency": 2.0}]
    )
    assert metrics["f1"] == 1.0
    assert metrics["strict_f1"] == 1.0
    assert metrics["severity_agreement"] == 1.0
    assert metrics["json_valid_rate"] == 1.0
    assert metrics["score_mae"] == 0.0
    assert metrics["avg_latency_s"] == 2.0
