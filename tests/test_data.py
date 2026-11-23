import json
import re
from pathlib import Path

from mtqa.agent import FEW_SHOT_PATH
from mtqa.schemas import AgentReport

ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = ROOT / "data" / "eval.jsonl"

PLACEHOLDER_RE = re.compile(r"^\{.*\}$|^%\w$")


def test_few_shot_parses_and_validates():
    examples = json.loads(FEW_SHOT_PATH.read_text(encoding="utf-8"))
    assert len(examples) >= 3
    for example in examples:
        AgentReport.model_validate(example["output"])


def test_gold_spans_appear_in_mt_unless_placeholder_token():
    rows = [json.loads(line) for line in EVAL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        for finding in row["gold_findings"]:
            span = finding["span"]
            if PLACEHOLDER_RE.match(span) or span.endswith("..") or span.endswith("!"):
                continue
            assert span in row["mt"], f"{row['id']}: span {span!r} not in MT"


def test_eval_set_shape():
    rows = [json.loads(line) for line in EVAL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 40
    groups = {row["group"] for row in rows}
    assert {"clean", "accuracy", "terminology", "fluency", "style"} <= groups
    holdouts = [row for row in rows if row["holdout"]]
    assert len(holdouts) == 10
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids))
