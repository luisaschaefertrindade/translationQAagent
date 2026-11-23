"""Run variants A/B/C over the eval set, score against gold, log to MLflow.

Usage:
  python eval/run_eval.py                       # all variants, config from mtqa.toml/env
  python eval/run_eval.py --variants C --limit 5
  python eval/run_eval.py --workers 4 --holdout
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtqa import agent as agent_mod  # noqa: E402
from mtqa import config  # noqa: E402
from mtqa.llm import OpenAICompatClient  # noqa: E402
from mtqa.metrics import aggregate  # noqa: E402
from mtqa.schemas import Segment  # noqa: E402
from mtqa.scoring import compute_score  # noqa: E402

EVAL_PATH = ROOT / "data" / "eval.jsonl"


def load_segments(holdout: bool | None = None) -> list[tuple[dict, Segment]]:
    segments = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if holdout is not None and row.get("holdout") != holdout:
            continue
        segments.append((row, Segment.model_validate(row)))
    return segments


def run_one(client, variant: str, row: dict, segment: Segment) -> dict:
    gold = row["gold_findings"]
    drafts: list[str] = []
    started = time.perf_counter()
    try:
        report = agent_mod.review(segment, client, variant, drafts=drafts)
    except agent_mod.AgentError as exc:
        return {
            "id": segment.segment_id,
            "gold": gold,
            "pred": [],
            "error": str(exc),
            "first_valid": bool(drafts) and _valid(drafts[0]),
            "latency": time.perf_counter() - started,
        }
    pred = [f.model_dump() for f in report.findings]
    return {
        "id": segment.segment_id,
        "gold": gold,
        "pred": pred,
        "score": report.score,
        "gold_score": compute_score(gold),
        "first_valid": bool(drafts) and _valid(drafts[0]),
        "latency": time.perf_counter() - started,
    }


def _valid(text: str) -> bool:
    try:
        agent_mod.parse_draft(text)
        return True
    except Exception:
        return False


def run_variant(client, variant: str, segments, workers: int = 1) -> tuple[dict, list[dict]]:
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda rs: run_one(client, variant, *rs), segments))
    else:
        results = [run_one(client, variant, *rs) for rs in segments]
    return aggregate(results), results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="A,B,C")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--holdout", action="store_true", help="run only the held-out split")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--experiment", default=None)
    parser.add_argument("--workers", type=int, default=1, help="parallel requests per variant")
    parser.add_argument(
        "--log-param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="extra param for MLflow, e.g. probe_autonomous_tool_rate=0.5",
    )
    args = parser.parse_args()

    settings = config.Settings.load(
        {
            "model": args.model,
            "base_url": args.base_url,
            "tracking_uri": args.tracking_uri,
            "experiment": args.experiment,
        }
    )

    segments = load_segments(holdout=True if args.holdout else None)
    if args.limit:
        segments = segments[: args.limit]

    try:
        import mlflow
    except ImportError:
        mlflow = None
    if mlflow and settings.tracking_uri:
        mlflow.set_tracking_uri(settings.tracking_uri)
        mlflow.set_experiment(settings.experiment)

    client = OpenAICompatClient(base_url=settings.base_url, model=settings.model)
    summary = {}
    for variant in [v.strip().upper() for v in args.variants.split(",") if v.strip()]:
        metrics, results = run_variant(client, variant, segments, workers=args.workers)
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
                        "split": "holdout" if args.holdout else "all",
                        "workers": args.workers,
                        **dict(item.split("=", 1) for item in args.log_param if "=" in item),
                    }
                )
                mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
                out = Path("predictions") / f"{variant}.json"
                out.parent.mkdir(exist_ok=True)
                out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
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
    header = ["variant", "f1", "strict_f1", "precision", "recall", "severity_agreement", "json_valid_rate", "score_mae", "avg_latency_s"]
    print("  " + " | ".join(header))
    for v, m in summary.items():
        print(f"  {v} | " + " | ".join(f"{m[h]:.3f}" for h in header[1:]))


if __name__ == "__main__":
    main()
