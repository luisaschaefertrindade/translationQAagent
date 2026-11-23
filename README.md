# MT QA Agent

A tool-calling agent that reviews English → Brazilian Portuguese machine
translation of enterprise-software text and returns a validated, scored JSON
report. Three deterministic checks (glossary, placeholders, PT-BR dialect and
style) back the model; the score is computed in code, never by the model.

## Why

Machine translation of UI strings fails in repeatable ways: glossary
violations, dropped placeholders (`{0}`, `%s`), European Portuguese
vocabulary, register slips. Some of these are mechanically checkable — those
should not be left to an LLM's opinion. The rest (mistranslation, omission,
fluency, politeness) is exactly what deterministic checks cannot see. This
project draws that line in code and measures what it costs and buys.

## Design

```
Segment ──► system prompt + few-shots (+ tool results or tool defs)
        ──► LLM ──► draft JSON {segment_id, findings[]}
        ──► Pydantic validation (retry ≤ 2 with the error fed back)
        ──► score injected in code ──► Report
```

- **Tools** (`src/mtqa/tools.py`) — accent- and case-insensitive glossary
  matching with stem and plural folding, word-boundary source lookup,
  placeholder/number/date/currency diffing, curated PT-EU lexicon plus
  spacing, punctuation, capitalization and register checks.
- **Scoring** (`src/mtqa/scoring.py`) —
  `score = max(0, round_half_up(100 − Σ severity_points × category_weight))`,
  severity minor 1 / moderate 3 / major 6 / critical 10; weights accuracy
  1.5, terminology 1.2, fluency 1.0, style 0.8.
- **Variants** — A: LLM only; B: tools run first, results placed in the
  prompt (fixed pipeline); C: the LLM decides which tools to call (agent).
- **Eval** — 40 hand-labelled enterprise-software segments (10 held out),
  category-level P/R/F1 (headline) and a stricter span-overlap F1, severity
  agreement within one level, JSON validity rate before retries (with
  `response_format=json_object` where the endpoint supports it), score MAE,
  latency. Runs logged to MLflow with the predictions file as artifact.

## Quickstart

```bash
pip install -e ".[dev]"
pytest

# endpoint config: mtqa.toml, overridden by MTQA_BASE_URL / MTQA_MODEL env vars
# (API keys only via MTQA_API_KEY, never the file)
pip install -e ".[eval]"
python eval/run_eval.py --variants A,B,C --workers 4
```

`scripts/probe_tools.py` checks whether an endpoint does reliable tool calling
before you trust variant C. The probe on Qwen3-0.6B showed the model declines
~50% of needed tool calls when left to decide, so variant C pre-runs the free
placeholder check and hands the result over; the model still chooses the other
two tools.

## Results

_To be filled after the A/B/C runs (see `eval/run_eval.py`)._

| Variant | F1 | Strict F1 | Severity agree | Valid JSON | Score MAE | Latency |
| --- | --- | --- | --- | --- | --- |
| A (LLM only) | | | | | |
| B (pipeline) | | | | | |
| C (agent) | | | | | |

## Limitations

- A glossary miss is also reported when the whole phrase was omitted; the
  tool cannot tell "wrong term" from "not translated".
- `ligação` and `introduzir` are PT-EU only in some senses; the lexicon check
  trades precision for recall.
- Courtesy formulas and a missing final period are model-only findings —
  variant B cannot inherit them.
- The eval set is synthetic, authored for this project.

## Layout

```
src/mtqa/        schemas, tools, scoring, metrics, config, llm (client + fake), agent loop
src/mtqa/prompts/  system.md (3 sections, versioned), few_shot.json
data/            glossary.csv, eval.jsonl (40 segments, 10 hold-out)
mtqa.toml        endpoint/experiment config (no secrets)
eval/run_eval.py  variants A/B/C, threads, metrics, MLflow
scripts/         endpoint tool-calling probe
tests/           tools, scoring, metrics, config, agent (fake client), prompts, data
```

Design rationale and week plan: `docs/project-design.md`.
