"""Run variants A/B/C over the eval set, score against gold, log to MLflow.

Usage:
  python eval/run_eval.py                      # all variants, real client from env
  python eval/run_eval.py --variants C --limit 5
  MTQA_BASE_URL=... MTQA_MODEL=... python eval/run_eval.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtqa import agent as agent_mod  # noqa: E402
from mtqa.llm import OpenAICompatClient  # noqa: E402
from mtqa.schemas import SEVERITY_ORDER, Segment  # noqa: E402
from mtqa.scoring import compute_score  # noqa: E402

EVAL_PATH = ROOT / "data" / "eval.jsonl"
CATEGORIES = ["accuracy", "terminology", "fluency", "style"]


def load_segments(holdout: bool | None = None) -> list[Segment]:
    segments = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if holdout is not None and row.get("holdout") != holdout:
            continue
        segments.append((row, Segment.model_validate(row)))
    return segments  # type: ignore[return-value]


def match_findings(pred: list[dict], gold: list[dict]) -> tuple[int, int, int]:
    """Greedy per-segment matching on category; returns (tp, fp, fn).

    Closest severity wins first so that category TP does not depend on order.
    """
    used = [False] * len(gold)
    tp = 0
    for p in pred:
        candidates = [
            (abs(SEVERITY_ORDER[p["severity"]] - SEVERITY_ORDER[g["severity"]]), i)
            for i, g in enumerate(gold)
            if not used[i] and g["category"] == p["category"]
        ]
        if candidates:
            candidates.sort()
            used[candidates[0][1]] = True
            tp += 1
    return tp, len(pred) - tp, len(gold) - tp


def severity_agreement(pred: list[dict], gold: list[dict]) -> tuple[int, int]:
    """Matched pairs whose severity is within one level / total category matches."""
    used = [False] * len(gold)
    agree = matched = 0
    for p in pred:
        candidates = [
            (abs(SEVERITY_ORDER[p["severity"]] - SEVERITY_ORDER[g["severity"]]), i)
            for i, g in enumerate(gold)
            if not used[i] and g["category"] == p["category"]
        ]
        if candidates:
            _, i = candidates[0]
            used[i] = True
            matched += 1
            if abs(SEVERITY_ORDER[p["severity"]] - SEVERITY_ORDER[gold[i]["severity"]]) <= 1:
                agree += 1
    return agree, matched


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def first_draft_valid(drafts: list[str]) -> bool:
    if not drafts:
        return False
    try:
        agent_mod.parse_draft(drafts[0])
        return True
    except Exception:
        return False


def run_variant(client, variant: str, segments) -> tuple[dict, list[dict]]:
    tp = fp = fn = 0
    cat_counts = {c: [0, 0, 0] for c in CATEGORIES}  # tp, fp, fn
    sev_agree = sev_total = 0
    valid_first = 0
    abs_errors: list[int] = []
    latencies: list[float] = []
    predictions = []

    for row, segment in segments:
        gold = row["gold_findings"]
        drafts: list[str] = []
        started = time.perf_counter()
        try:
            report = agent_mod.review(segment, client, variant, drafts=drafts)
        except agent_mod.AgentError as exc:
            latencies.append(time.perf_counter() - started)
            predictions.append({"id": segment.segment_id, "error": str(exc), "findings": []})
            fn += len(gold)
            for g in gold:
                cat_counts[g["category"]][2] += 1
            continue
        latencies.append(time.perf_counter() - started)

        pred = [f.model_dump() for f in report.findings]
        st, sf, sfn = match_findings(pred, gold)
        tp += st
        fp += sf
        fn += sfn
        _update_categories(cat_counts, pred, gold)
        a, m = severity_agreement(pred, gold)
        sev_agree += a
        sev_total += m
        valid_first += int(first_draft_valid(drafts))
        gold_score = compute_score(gold)
        abs_errors.append(abs(report.score - gold_score))
        predictions.append(
            {
                "id": segment.segment_id,
                "findings": pred,
                "score": report.score,
                "gold_findings": gold,
                "gold_score": gold_score,
            }
        )

    p, r, f1 = prf(tp, fp, fn)
    metrics = {
        "precision": p,
        "recall": r,
        "f1": f1,
        "severity_agreement": sev_agree / sev_total if sev_total else 0.0,
        "json_valid_rate": valid_first / len(segments) if segments else 0.0,
        "score_mae": mean(abs_errors) if abs_errors else 0.0,
        "avg_latency_s": mean(latencies) if latencies else 0.0,
    }
    for cat, (ct, cf, cn) in cat_counts.items():
        cp, cr, cff = prf(ct, cf, cn)
        metrics[f"f1_{cat}"] = cff
        metrics[f"precision_{cat}"] = cp
        metrics[f"recall_{cat}"] = cr
    return metrics, predictions


def _update_categories(cat_counts: dict, pred: list[dict], gold: list[dict]) -> None:
    used = [False] * len(gold)
    matched_pred = set()
    for p in pred:
        candidates = [
            (abs(SEVERITY_ORDER[p["severity"]] - SEVERITY_ORDER[g["severity"]]), i)
            for i, g in enumerate(gold)
            if not used[i] and g["category"] == p["category"]
        ]
        if candidates:
            candidates.sort()
            used[candidates[0][1]] = True
            matched_pred.add(id(p))
            cat_counts[p["category"]][0] += 1
    for p in pred:
        if id(p) not in matched_pred:
            cat_counts[p["category"]][1] += 1
    for i, g in enumerate(gold):
        if not used[i]:
            cat_counts[g["category"]][2] += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="A,B,C")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--holdout", action="store_true", help="run only the held-out split")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--experiment", default="mt-qa-agent")
    args = parser.parse_args()

    segments = load_segments(holdout=True if args.holdout else None)
    if args.limit:
        segments = segments[: args.limit]

    try:
        import mlflow
    except ImportError:
        mlflow = None
    if mlflow and args.tracking_uri:
        mlflow.set_tracking_uri(args.tracking_uri)

    client = OpenAICompatClient(base_url=args.base_url, model=args.model)
    summary = {}
    for variant in [v.strip().upper() for v in args.variants.split(",") if v.strip()]:
        metrics, predictions = run_variant(client, variant, segments)
        summary[variant] = metrics
        print(f"\n=== variant {variant} ===")
        for k, v in metrics.items():
            print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
        if mlflow:
            with mlflow.start_run(run_name=f"variant-{variant}"):
                mlflow.log_params(
                    {
                        "variant": variant,
                        "model": client.model or "unset",
                        "prompt_version": agent_mod.prompt_version(),
                        "n_segments": len(segments),
                    }
                )
                mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
                out = Path("predictions") / f"{variant}.json"
                out.parent.mkdir(exist_ok=True)
                out.write_text(json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8")
                mlflow.log_artifact(str(out))

    if mlflow and summary:
        try:
            mlflow.log_table(
                {
                    "variant": list(summary),
                    **{m: [summary[v][m] for v in summary] for m in next(iter(summary.values()))}
                },
                artifact_file="comparison.json",
            )
        except Exception as exc:  # older mlflow versions lack log_table
            print(f"log_table skipped: {exc}")
    print("\ncomparison:")
    header = ["variant", "f1", "precision", "recall", "severity_agreement", "score_mae", "avg_latency_s"]
    print("  " + " | ".join(header))
    for v, m in summary.items():
        print(f"  {v} | " + " | ".join(f"{m[h]:.3f}" for h in header[1:]))


if __name__ == "__main__":
    main()
