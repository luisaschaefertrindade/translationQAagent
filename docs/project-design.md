# Translation QA Agent: Project Design

A small, tested, tracked tool-calling agent that reviews an English to Brazilian Portuguese machine translation and returns a structured quality report. Agentic design, production habits, and experiment tracking.

## 1. Goal and scope

Input: an English source segment, a PT-BR machine translation, and an optional glossary. Output: validated JSON with a list of findings and a score.

In scope: three deterministic tools, an LLM that calls them, enforced structured output, an eval set of 40 segments, MLflow tracking, pytest, CI and Docker.

Out of scope: a web UI, multiple language pairs, fine-tuning, any internal or confidential data. Use only synthetic or public text.

## 2. How it works

1. The segment goes into a Pydantic `Segment` object.
2. The agent receives the system prompt, 3 few-shot examples and the tool definitions.
3. It calls the tools it needs: glossary check, placeholder check, dialect and style check.
4. It writes a final report as JSON.
5. Pydantic validates the JSON. If invalid, the error message goes back to the model and it retries, at most 2 times.
6. The score is computed in code from the findings, not by the model, so it is deterministic and testable.

## 3. Tools (all deterministic Python)

Matching rules that apply to every check:
- Glossary lookup iterates over terms whose SOURCE word appears in the English segment, matched on word boundaries, so `user` does not match inside `usertype`.
- Approved-term matching is accent- and case-insensitive with a stem fallback that strips an infinitive ending, so `Salve` satisfies `salvar` and `exclua` satisfies `excluir`. Without this, clean segments report phantom violations.
- The forbidden column is used only inside `check_glossary`, only for rows whose source term is present. It is not a dialect marker list: `perfil`, `ordem` and `pedido` are valid PT-BR in other senses.
- `check_dialect_and_style` uses a curated marker list, and each result carries `kind`: lexicon, spacing, punctuation, capitalization, register.
- Malformed glossary rows (empty source) are skipped.

- `check_glossary(source, mt, glossary)`: rows whose source term appears in the source, whose approved translation is absent from the MT, or whose forbidden variant appears in the MT.
- `check_placeholders(source, mt)`: `{0}`, `%s`, tags, numbers and URLs dropped, added or altered.
- `check_dialect_and_style(mt)`: curated PT-EU lexicon markers, double spaces, doubled or missing terminal punctuation, heading title case, and register forms (vosso, mixed tu/você). Politeness formulas and tone are left to the model.

The model judges what the checks cannot: mistranslation, omission, addition,
courtesy formulas, punctuation appropriateness, and fluency.

## 4. Data model and scoring

The model returns a draft without a score; the score is injected in code.

```python
class AgentReport(BaseModel):   # what the model must return
    segment_id: str
    findings: list[Finding]

class Report(BaseModel):        # what the tool returns
    segment_id: str
    findings: list[Finding]
    score: int


- Severity points: minor 1, moderate 3, major 6, critical 10.
- Category weights: accuracy 1.5, terminology 1.2, fluency 1.0, style 0.8.

An empty findings list scores 100.

score = max(0, round(100 - sum(severity_points * category_weight)))
Rounding is round-half-up. Two style minors give 98.4 -> 98; a PT-EU word plus a
double space gives 95.6 -> 96. Fix the convention in a test, because most style
findings are minor and every one of them lands on a fraction.

## 5. Eval set (40 segments)

Use short enterprise-software strings (UI labels, help text, error messages), the kind SAP translates. Write them yourself or draft them with a model, then correct everything by hand. The gold labels must be yours.

| Group | Segments | What you inject |
| --- | --- | --- |
| Clean | 10 | A correct translation, no findings |
| Accuracy | 8 | Mistranslation, omission, addition |
| Terminology | 8 | A glossary violation |
| Fluency | 7 | Awkward or ungrammatical PT-BR |
| Style and dialect | 7 | PT-EU markers, punctuation, register |

Store as JSONL: `id, source, mt, glossary, gold_findings`. Include a few segments with two errors. Keep 10 of them as a held-out test set you never tune prompts on.

## 6. Experiments and metrics

Three variants, tracked as MLflow runs:

- A: LLM only, no tools.
- B: tools run first, results placed in the prompt (a fixed pipeline, not an agent).
- C: LLM decides which tools to call (the agent).

Metrics per run: category-level precision, recall and F1 (a finding counts as matched when category matches within a segment); severity agreement within one level; JSON validity rate before retries; score MAE against gold scores; average latency.

Log parameters (model, prompt version, variant), metrics, and the predictions file as an artifact. The comparison of A, B and C is your best finding, whichever wins. If a local model cannot do tool calling reliably, say so and report that as a finding.

## 7. Model setup

Put the model behind one small client class that talks to an OpenAI-compatible chat endpoint, so you can swap models by changing a base URL and name. Your local Lemonade setup may expose such an endpoint (check its docs); otherwise use any API you have. Test with a fake client so tests and CI never call a model.

## 8. Repository layout

```
mt-qa-agent/
  README.md
  pyproject.toml
  Dockerfile
  .github/workflows/ci.yml
  src/mtqa/
    schemas.py      # Segment, Finding, Report
    tools.py        # the three checks
    scoring.py      # penalty-based score
    llm.py          # client wrapper + fake client
    agent.py        # prompt, tool loop, validation, retry
    prompts/        # system prompt, few-shot examples
  data/eval.jsonl
  eval/run_eval.py  # runs variants, logs to MLflow
  tests/
```

## 9. Tests, CI and Docker

- Tool tests: one passing and one failing case each for glossary, placeholder and dialect checks.
- Scoring tests: empty findings give 100, one critical accuracy finding gives 85, the floor at 0 holds.
- Agent tests with the fake client: valid JSON passes, invalid JSON triggers a retry, two failures raise a clear error.
- GitHub Actions: install, run pytest on push.
- Dockerfile: install the package and run the eval script.
- Glossary tool: conjugated approved term is not flagged; `user` does not match inside `usertype`; a malformed row is skipped; a forbidden variant whose source term is absent from the source is not flagged.
- Dialect tool: one case per `kind`.
- Scoring: the three original cases plus rounding (98.4 -> 98, 95.6 -> 96).
- Prompt assembly: variant A's prompt contains no tool name and no tool_results; no few-shot output contains a score.
- Data: few_shot.json parses, and every few-shot `output` validates against AgentReport, and every gold span appears in its MT unless it is a placeholder token.

## 10. Cut list if time runs short

Cut in this order: Docker, the style and dialect tool, the eval set down to 30 segments, variant B. Do not cut tests, structured output enforcement or the MLflow comparison, because those are what close the gaps.

## 11. Definition of done

- [ ] Agent returns validated JSON for all 40 segments
- [ ] Three variants compared in MLflow with a results table in the README
- [ ] Tests pass locally and in GitHub Actions
- [ ] README explains the problem, design, results and limitations

## 12. Mapping to the week

- Mon: probe the endpoint for tool calling; scaffold the repo, pyproject, CI workflow, green pytest on an empty test file.
- Tue: schemas, tools, scoring, prompt, first end-to-end run.
- Wed: tool loop, validation and retry; build the eval set.
- Thu: eval script, MLflow, variants A, B and C, short error analysis.
- Fri: tests, CI, Docker, README, CV bullet, apply.

## 13. Describing it

A tool-calling agent that reviews machine translations, with deterministic checks for glossary, placeholders and dialect, enforced structured output, and a tracked evaluation comparing three designs.
