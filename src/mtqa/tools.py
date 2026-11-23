"""Deterministic quality checks for the MT QA agent.

Contract
--------
Each check returns a plain, JSON-serialisable list of records so the results can
be pasted into a prompt, logged to MLflow and scored against gold with no model
in the loop [1]. Nothing here imports a client or touches the network.

Matching rules -- these are what keep the clean segments clean:

1. A glossary row is consulted only when the row's SOURCE word appears in the
   English segment, matched as a whole normalised token. So `user` never matches
   inside `usertype`, and `perfil` is never consulted for a segment whose source
   does not say "role".
2. Approved and forbidden terms are matched against the MT with an accent- and
   case-insensitive stem prefix, so `Salve` satisfies `salvar` and `exclua`
   satisfies `excluir` [2].
3. `-ao/-oes` (and `-al/-ais`, `-el/-eis`, `-ol/-ois`) collapse to a common
   singular before comparison. Folding alone is not enough: `alteracao` is NOT a
   prefix of `alteracoes`, and without this rule clean-01 reports a phantom
   violation of `change -> alteracao`.
4. Irregular forms no stem can reach (`insira` from `inserir`) come from the
   optional 4th CSV column or DEFAULT_VARIANTS below.
5. The forbidden column is NOT a dialect marker list. `perfil`, `ordem`, `pedido`
   and `envio` are valid PT-BR in other senses; only LEXICON below is [3].
   Lexicon markers match by whole-token equality, never by prefix, because the
   prefix `equipa` would otherwise match `equipamento`.
6. Folding is length-preserving (one codepoint in, one out), so a match found in
   the folded text slices straight out of the raw MT. Returned spans therefore
   carry the original accents and are directly comparable to gold [1].

Known limits, to be measured by the tool audit before any model is called:

* A missing approved term is reported even when the whole phrase containing it
  was omitted -- gold acc-01 drops "for 12 users", and the tool cannot tell
  "wrong term" from "not translated at all" [2]. The system prompt carries a rule
  telling the model to report that as one accuracy omission, not as terminology.
* `ligacao` and `introduzir` are PT-EU only in some senses (PT-BR `ligacao` is a
  phone call), so the lexicon check trades precision for recall.
* Not detected here, deliberately: courtesy formulas and a missing final period.
  sty-02, sty-06 and sty-07 are therefore model-only findings, and variant B
  cannot inherit them from the pipeline [2].
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

# ------------------------------------------------------------------ folding --

def _build_fold_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for cp in range(0x20, 0x0300):
        ch = chr(cp)
        decomposed = unicodedata.normalize("NFD", ch)
        if len(decomposed) > 1 and decomposed[0] != ch:
            table[cp] = decomposed[0].lower()
    return table


_FOLD = _build_fold_table()


def fold(text: str) -> str:
    """Lowercase and strip diacritics, preserving string length."""
    return text.lower().translate(_FOLD)


_PLURALS = (("oes", "ao"), ("ais", "al"), ("eis", "el"), ("ois", "ol"))


def _sing(word: str) -> str:
    """Folded word reduced to a common singular form."""
    for suffix, replacement in _PLURALS:
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _stems(word: str) -> list[str]:
    """Singular plus, for infinitives, the bare stem. Guarded by length."""
    base = _sing(word)
    out = [base]
    if len(base) >= 6:
        for ending in ("ar", "er", "ir"):
            if base.endswith(ending) and len(base) - len(ending) >= 4:
                out.append(base[: -len(ending)])
    return out


_TOKEN_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)
_MIN_STEM = 4


def _scan(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Folded text plus (start, end, folded_token) for every word."""
    folded = fold(text)
    return folded, [(m.start(), m.end(), m.group()) for m in _TOKEN_RE.finditer(folded)]


# ---------------------------------------------------------------- glossary ---

#: Forms no stem can reach, keyed by folded source term. Insurance, not
#: architecture: the audit decides whether each line moves into CSV column 4.
DEFAULT_VARIANTS: dict[str, tuple[str, ...]] = {
    "change": ("alterar", "altere", "alterado"),      # glossary approves the noun [3]
    "enter": ("insira", "insiram", "digite"),          # inserir -> insira
    "log out": ("saia", "sai"),                        # sair is suppletive-ish
    "download": ("baixe", "baixado"),
    "registration": ("cadastre", "cadastrado"),
}


@dataclass
class Entry:
    source: str
    translation: str
    forbidden: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return fold(self.source)


def load_glossary(path: str | Path) -> dict[str, Entry]:
    """Read `source;translation;forbidden[;variants]`, skipping junk rows."""
    entries: dict[str, Entry] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            source = (row.get("source") or "").strip()
            translation = (row.get("translation") or "").strip()
            if not source or not translation:          # trailing `;;` artefact
                continue
            if source.lower() == "source":             # repeated-header artefact
                continue
            forbidden = tuple(
                f.strip() for f in re.split(r"[|/]", row.get("forbidden") or "") if f.strip()
            )
            variants = tuple(
                v.strip() for v in re.split(r"[|/]", row.get("variants") or "") if v.strip()
            )
            entries[fold(source)] = Entry(source, translation, forbidden, variants)
    return entries


def _coerce(glossary: Mapping | Sequence | None) -> dict[str, Entry]:
    out: dict[str, Entry] = {}
    if glossary is None:
        return out
    items: Iterable[tuple[str, object]]
    if isinstance(glossary, Mapping):
        items = glossary.items()
    else:
        items = [
            (item.get("source") or item.get("source_term") or "", item) for item in glossary
        ]
    for source, value in items:
        source = str(source).strip()
        if not source:
            continue
        if isinstance(value, str):
            out[fold(source)] = Entry(source, value.strip())
        elif isinstance(value, Mapping):
            translation = str(value.get("translation") or value.get("expected") or "").strip()
            if not translation:
                continue
            raw_forbidden = value.get("forbidden") or ()
            if isinstance(raw_forbidden, str):
                raw_forbidden = re.split(r"[|/]", raw_forbidden)
            out[fold(source)] = Entry(
                source,
                translation,
                tuple(str(f).strip() for f in raw_forbidden if str(f).strip()),
                tuple(str(v).strip() for v in value.get("variants") or () if str(v).strip()),
            )
    return out


_GLOBAL: dict[str, Entry] | None = None
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "glossary.csv"


def global_glossary(path: str | Path | None = None) -> dict[str, Entry]:
    global _GLOBAL
    if path is not None:
        _GLOBAL = load_glossary(path)
    elif _GLOBAL is None:
        _GLOBAL = load_glossary(DEFAULT_PATH) if DEFAULT_PATH.exists() else {}
    return _GLOBAL


def resolve_glossary(segment: Mapping | Sequence | None) -> dict[str, Entry]:
    """Segment entries override the CSV, which fills the terms the segment omits.

    Layering is required, not cosmetic: term-07 flags `Introduza` only because the
    `enter -> inserir` row comes from the CSV, since that segment lists just
    `username` and `licence key` [2].
    """
    merged = dict(global_glossary())
    merged.update(_coerce(segment))
    return merged


# ------------------------------------------------------------ term matching --

def _in_source(entry: Entry, folded_source: str, source_words: set[str]) -> bool:
    parts = fold(entry.source).split()
    if len(parts) == 1:
        return _sing(parts[0]) in source_words
    head = re.escape(parts[0]) + r"[\w-]*"             # "logging out" matches "log out"
    tail = r"\s+".join(re.escape(_sing(p)) + r"[\w-]*" for p in parts[1:])
    return re.search(rf"(?<![\w-]){head}\s+{tail}", folded_source) is not None


def _find_in_mt(term: str, folded_text: str, raw: str, tokens, variants=()) -> str | None:
    """Raw span of the first MT occurrence of `term`, or None."""
    parts = fold(term).split()
    if len(parts) > 1:
        head = re.escape(_sing(parts[0])) + r"[\w-]*"
        tail = r"\s+".join(re.escape(_sing(p)) + r"[\w-]*" for p in parts[1:])
        match = re.search(rf"(?<![\w-]){head}\s+{tail}", folded_text)
        return raw[match.start() : match.end()] if match else None

    base = parts[0]
    for variant in variants:                            # curated: any length allowed
        match = re.search(rf"(?<![\w-]){re.escape(variant)}[\w-]*", folded_text)
        if match:
            return raw[match.start() : match.end()]
    for start, end, token in tokens:                    # exact, plural-insensitive
        if _sing(token) == _sing(base):
            return raw[start:end]
    for stem in _stems(base):                           # family match
        if len(stem) >= _MIN_STEM:
            match = re.search(rf"(?<![\w-]){re.escape(stem)}[\w-]*", folded_text)
            if match:
                return raw[match.start() : match.end()]
    return None


def check_glossary(
    source: str, mt: str, glossary: Mapping | Sequence | None = None
) -> list[dict]:
    entries = resolve_glossary(glossary)
    folded_source, source_tokens = _scan(source)
    source_words = {_sing(token) for _, _, token in source_tokens}
    folded_mt, mt_tokens = _scan(mt)

    results: list[dict] = []
    for entry in entries.values():
        if not _in_source(entry, folded_source, source_words):
            continue
        variants = tuple(fold(v) for v in entry.variants or DEFAULT_VARIANTS.get(entry.key, ()))
        if _find_in_mt(entry.translation, folded_mt, mt, mt_tokens, variants) is None:
            results.append(
                {
                    "kind": "missing_approved",
                    "source_term": entry.source,
                    "expected": entry.translation,
                    "found": False,
                    "span": "",
                }
            )
        for forbidden in entry.forbidden:
            span = _find_in_mt(forbidden, folded_mt, mt, mt_tokens)
            if span is not None:
                results.append(
                    {
                        "kind": "forbidden_used",
                        "source_term": entry.source,
                        "expected": entry.translation,
                        "used": span,
                        "found": True,
                        "span": span,
                    }
                )
    return results


# ----------------------------------------------------------- placeholders ----

_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
_DATE_RE = re.compile(r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b")
_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
_PH_RE = re.compile(r"\{\{?\w+\}?\}|%(?:\d*(?:\.\d+)?)[sdif]")
_NUM_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")
_CURRENCY_RE = re.compile(r"R\$\s?|US\$\s?|\$\s?|€\s?|£\s?")


def _norm_number(token: str) -> str:
    parts = re.split(r"[.,]", token)
    if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and len(parts[0]) <= 3:
        return "".join(parts)                           # 5,000 and 1.500 -> 5000 / 1500
    return token.replace(",", ".")


def _extract(text: str) -> dict[str, Counter]:
    rest = _URL_RE.sub(" ", text)
    out = {
        "url": Counter(_URL_RE.findall(text)),
        "date": Counter(_DATE_RE.findall(rest)),
        "tag": Counter(t.lower() for t in _TAG_RE.findall(rest)),
    }
    rest = _TAG_RE.sub(" ", rest)
    rest = _DATE_RE.sub(" ", rest)
    out["placeholder"] = Counter(_PH_RE.findall(rest))
    rest = _PH_RE.sub(" ", rest)
    out["number"] = Counter(_norm_number(n) for n in _NUM_RE.findall(rest))
    rest = _NUM_RE.sub(" ", rest)
    out["currency"] = Counter(c.strip() for c in _CURRENCY_RE.findall(rest))
    return out


def _diff(kind: str, src: Counter, mt: Counter, out: list[dict]) -> None:
    for token, count in src.items():
        missing = count - mt.get(token, 0)
        if missing > 0:
            out.append({"kind": "dropped", "type": kind, "token": token, "count": missing})
    for token, count in mt.items():
        extra = count - src.get(token, 0)
        if extra > 0:
            out.append({"kind": "added", "type": kind, "token": token, "count": extra})


def check_placeholders(source: str, mt: str) -> list[dict]:
    a, b = _extract(source), _extract(mt)
    out: list[dict] = []
    for kind in ("url", "date", "tag", "placeholder"):
        _diff(kind, a[kind], b[kind], out)
    # Numbers are compared as values, not as tokens, so 5,000 vs 500 is one
    # mismatch and not two unrelated dropped/added tokens.
    _diff("number", a["number"], b["number"], out)
    if a["currency"] != b["currency"]:
        out.append(
            {
                "kind": "wrong_currency",
                "type": "currency",
                "source": "".join(sorted(a["currency"])) or None,
                "mt": "".join(sorted(b["currency"])) or None,
            }
        )
    return out


# ------------------------------------------------------- dialect and style ---

#: Curated PT-EU lexicon. Deliberately narrower than the CSV forbidden column:
#: perfil, ordem, pedido and envio are valid PT-BR elsewhere. Matched by whole
#: token (plural-insensitive), never by prefix.
LEXICON: tuple[tuple[str, str], ...] = (
    ("telemóvel", "celular"), ("ecrã", "tela"), ("ficheiro", "arquivo"),
    ("equipa", "equipe"), ("registo", "registro"), ("utilizador", "usuário"),
    ("ligação", "link (hoyperlink sense only)"), ("descarregamento", "download"),
    ("definições", "configurações"), ("secção", "seção"),
    ("palavra-passe", "senha"), ("contacto", "contato"), ("contacte", "entre em contato"),
    ("comprovativo", "comprovante"), ("subscrição", "assinatura"),
    ("freguês", "cliente"), ("introduzir", "inserir"), ("introduza", "inserir"),
)
_LEXICON = {(_sing(fold(marker))): suggestion for marker, suggestion in LEXICON}

REGISTER = {
    "vosso": "seu", "vossa": "sua", "vossos": "seus", "vossas": "suas",
}
TU_FORMS = {"tu", "teu", "tua", "teus", "tuas", "contigo", "podes", "és", "estás", "tens", "fazes", "queres"}
VOCE_FORMS = {"voce", "voces", "seu", "sua", "seus", "suas", "pode", "esta", "tem", "quer"}
_STOP_CAP = {
    "de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "no", "na",
    "nos", "nas", "para", "com", "por", "que", "um", "uma", "ao", "aos",
}

_DOUBLE_SPACE_RE = re.compile(r"(?<=\S)[ \t]{2,}(?=\S)")
_DOUBLE_PERIOD_RE = re.compile(r"(?<!\.)\.{2}(?!\.)")
_STRAY_RE = re.compile(r"[ \t]+[,.;:!?]|\s!\S|(?<=\S),(?=\S)")
_BANGBang_RE = re.compile(r"!!")


def check_dialect_and_style(mt: str) -> list[dict]:
    folded, tokens = _scan(mt)
    out: list[dict] = []

    for start, end, token in tokens:
        key = _sing(token)
        if key in _LEXICON:
            out.append(
                {
                    "kind": "lexicon", "marker": token, "severity": "moderate",
                    "suggestion": _LEXICON[key], "span": mt[start:end],
                }
            )
        if key in REGISTER:
            out.append(
                {
                    "kind": "register", "marker": token, "severity": "moderate",
                    "suggestion": REGISTER[key], "span": mt[start:end],
                }
            )

    tu = {t for _, _, t in tokens if _sing(t) in {fold(x) for x in TU_FORMS}}
    voce = {t for _, _, t in tokens if _sing(t) in {fold(x) for x in VOCE_FORMS}}
    if tu and voce:
        last = max(((start, end) for start, end, t in tokens if _sing(t) in voce), key=lambda s: s[1])
        out.append(
            {
                "kind": "register", "marker": "mixed tu/voce", "severity": "moderate",
                "suggestion": "pick one form of address",
                "span": mt[last[0] : last[1]],
                "tu_forms": sorted(tu),
            }
        )

    for match in _DOUBLE_SPACE_RE.finditer(mt):
        out.append({"kind": "spacing", "severity": "minor", "span": match.group(),
                    "context": mt[max(0, match.start() - 12) : match.end() + 12]})
    for pattern in (_DOUBLE_PERIOD_RE, _STRAY_RE, _BANGBang_RE):
        for match in pattern.finditer(mt):
            out.append({"kind": "punctuation", "severity": "minor", "span": match.group(),
                        "context": mt[max(0, match.start() - 12) : match.end() + 12]})

    raw_tokens = [t for t in re.split(r"\s+", mt.strip()) if t]
    if 1 < len(raw_tokens) <= 12:
        hits = [
            t for t in raw_tokens[1:]
            if t[0].isupper() and not t.isupper() and len(t) > 2
            and fold(t) not in _STOP_CAP
        ]
        if len(hits) >= 2 and raw_tokens[0][0].isupper():
            out.append({"kind": "capitalization", "severity": "minor", "span": mt.strip(),
                        "suggestion": "PT-BR headings use sentence case"})
    return out


# ------------------------------------------------------------------ plumbing -

def run_all(source: str, mt: str, glossary=None) -> dict[str, list[dict]]:
    """Variant B input: all three checks, unconditional and in a fixed order [1]."""
    return {
        "check_glossary": check_glossary(source, mt, glossary),
        "check_placeholders": check_placeholders(source, mt),
        "check_dialect_and_style": check_dialect_and_style(mt),
    }


def dedupe_findings(results: Mapping[str, Sequence[dict]]) -> list[dict]:
    """Collapse two checks reporting the same span into one finding.

    `ligação` in term-03 is both a glossary violation and a lexicon marker, and
    gold lists it once [2]; reporting it twice is a false positive by construction.
    Order fixes which record survives: glossary carries the approved term.
    """
    seen: dict[str, dict] = {}
    for check, records in results.items():
        for record in records:
            key = fold(record.get("span") or "") or f"{check}:{len(seen)}"
            if key in seen:
                seen[key].setdefault("also_reported_by", []).append(check)
            else:
                merged = dict(record)
                merged["reported_by"] = check
                seen[key] = merged
    return list(seen.values())


if __name__ == "__main__":
    demo = [
        ("Save your changes before closing the window.",
         "Salve as alterações antes de fechar a janela.",
         {"save": "salvar", "window": "janela"}),
        ("Hello {0}, {1} added you to team \"{2}\".", "Olá {0}, foi adicionado à equipe.", None),
        ("Select the team you belong to.", "Selecione a equipa à qual pertence.", None),
    ]
    for src, target, gl in demo:
        print(json.dumps(run_all(src, target, gl), ensure_ascii=False, indent=2))