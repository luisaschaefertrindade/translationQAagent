"""Finding matching and variant metrics: pure functions, no I/O, unit-testable.

Two matching modes are reported:
- category (the design doc's headline): a finding matches when the category
  agrees within a segment, closest severity first.
- strict: same category AND the spans overlap (accent/case-insensitive), which
  punishes findings that name the right problem in the wrong place.
"""

from __future__ import annotations

from statistics import mean

from .tools import fold

CATEGORIES = ["accuracy", "terminology", "fluency", "style"]

SEV_RANK = {"minor": 0, "moderate": 1, "major": 2, "critical": 3}


def span_match(pred_span: str, gold_span: str) -> bool:
    """Accent- and case-insensitive containment either way; empty never matches."""
    a = fold((pred_span or "").strip())
    b = fold((gold_span or "").strip())
    if not a or not b:
        return False
    return a == b or a in b or b in a


def match_pairs(pred: list[dict], gold: list[dict], require_span: bool = False) -> list[tuple[int, int]]:
    """Greedy pred->gold assignment on category, closest severity wins first."""
    used = [False] * len(gold)
    pairs: list[tuple[int, int]] = []
    for pi, p in enumerate(pred):
        candidates = [
            (abs(SEV_RANK[p["severity"]] - SEV_RANK[g["severity"]]), gi)
            for gi, g in enumerate(gold)
            if not used[gi]
            and g["category"] == p["category"]
            and (not require_span or span_match(p.get("span", ""), g.get("span", "")))
        ]
        if candidates:
            candidates.sort()
            used[candidates[0][1]] = True
            pairs.append((pi, candidates[0][1]))
    return pairs


def match_findings(pred: list[dict], gold: list[dict]) -> tuple[int, int, int]:
    tp = len(match_pairs(pred, gold))
    return tp, len(pred) - tp, len(gold) - tp


def strict_match(pred: list[dict], gold: list[dict]) -> tuple[int, int, int]:
    tp = len(match_pairs(pred, gold, require_span=True))
    return tp, len(pred) - tp, len(gold) - tp


def severity_agreement(pred: list[dict], gold: list[dict]) -> tuple[int, int]:
    pairs = match_pairs(pred, gold)
    agree = sum(
        1
        for pi, gi in pairs
        if abs(SEV_RANK[pred[pi]["severity"]] - SEV_RANK[gold[gi]["severity"]]) <= 1
    )
    return agree, len(pairs)


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def category_counts(pred: list[dict], gold: list[dict]) -> dict[str, list[int]]:
    counts = {c: [0, 0, 0] for c in CATEGORIES}
    pairs = match_pairs(pred, gold)
    matched_pred = {pi for pi, _ in pairs}
    matched_gold = {gi for _, gi in pairs}
    for pi, p in enumerate(pred):
        counts[p["category"]][0 if pi in matched_pred else 1] += 1
    for gi, g in enumerate(gold):
        if gi not in matched_gold:
            counts[g["category"]][2] += 1
    return counts


def aggregate(results: list[dict]) -> dict:
    """Roll per-segment results into the variant's metric dict.

    Each result: {gold, pred, first_valid, latency} and, on success,
    {score, gold_score}; on failure {error}.
    """
    tp = fp = fn = 0
    stp = sfp = sfn = 0
    cat = {c: [0, 0, 0] for c in CATEGORIES}
    sev_agree = sev_total = valid = 0
    abs_errors: list[int] = []
    latencies: list[float] = []

    for r in results:
        latencies.append(r["latency"])
        gold = r.get("gold") or []
        valid += int(bool(r.get("first_valid")))
        if r.get("error"):
            fn += len(gold)
            for g in gold:
                cat[g["category"]][2] += 1
            continue
        pred = r["pred"]
        a1, b1, c1 = match_findings(pred, gold)
        tp += a1
        fp += b1
        fn += c1
        s1, s2, s3 = strict_match(pred, gold)
        stp += s1
        sfp += s2
        sfn += s3
        for c, (a, b, n) in category_counts(pred, gold).items():
            cat[c][0] += a
            cat[c][1] += b
            cat[c][2] += n
        a, m = severity_agreement(pred, gold)
        sev_agree += a
        sev_total += m
        abs_errors.append(abs(r["score"] - r["gold_score"]))

    p, rc, f1 = prf(tp, fp, fn)
    _, _, strict_f1 = prf(stp, sfp, sfn)
    metrics = {
        "precision": p,
        "recall": rc,
        "f1": f1,
        "strict_f1": strict_f1,
        "severity_agreement": sev_agree / sev_total if sev_total else 0.0,
        "json_valid_rate": valid / len(results) if results else 0.0,
        "score_mae": mean(abs_errors) if abs_errors else 0.0,
        "avg_latency_s": mean(latencies) if latencies else 0.0,
    }
    for c, (a, b, n) in cat.items():
        cp, cr, cf = prf(a, b, n)
        metrics[f"f1_{c}"] = cf
        metrics[f"precision_{c}"] = cp
        metrics[f"recall_{c}"] = cr
    return metrics
