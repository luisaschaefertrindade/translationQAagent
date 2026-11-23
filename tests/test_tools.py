from mtqa.tools import (
    check_dialect_and_style,
    check_glossary,
    check_placeholders,
    dedupe_findings,
    load_glossary,
    run_all,
)


def test_glossary_clean_segment_passes():
    results = check_glossary(
        "Save your changes before closing the window.",
        "Salve as alterações antes de fechar a janela.",
        {"save": "salvar", "window": "janela"},
    )
    assert results == []


def test_glossary_flags_missing_approved_term():
    results = check_glossary(
        "Delete the user account permanently.",
        "Suprima a conta de usuário definitivamente.",
        {"delete": "excluir"},
    )
    assert any(r["kind"] == "missing_approved" and r["source_term"] == "delete" for r in results)


def test_conjugated_approved_term_is_not_flagged():
    # `Salve` must satisfy `salvar` via the stem fallback.
    results = check_glossary(
        "Save the file.", "Salve o arquivo.", {"save": "salvar", "file": "arquivo"}
    )
    assert results == []


def test_word_boundaries_prevent_substring_match():
    # `user` must not match inside `usertype`, so no phantom `user -> usuario` miss.
    results = check_glossary(
        "The usertype cannot be empty.",
        "O tipo de usuario nao pode estar vazio.",
        {"user": "usuário"},
    )
    assert results == []


def test_malformed_glossary_row_is_skipped(tmp_path):
    path = tmp_path / "g.csv"
    path.write_text("source;translation;forbidden\n;traducao;\nfile;arquivo;\n", encoding="utf-8")
    entries = load_glossary(path)
    assert list(entries) == ["file"]


def test_forbidden_variant_without_source_term_is_not_flagged():
    # `perfil` is only checked when the source says `role`.
    results = check_glossary(
        "Open your profile page.",
        "Abra a página do seu perfil.",
        {"role": "função"},
    )
    assert results == []


def test_forbidden_variant_is_flagged_when_source_term_present():
    results = check_glossary(
        "Assign a new role.",
        "Atribua um novo perfil.",
        {"role": {"translation": "função", "forbidden": "perfil"}},
    )
    assert any(r["kind"] == "forbidden_used" and r["span"] == "perfil" for r in results)


def test_placeholders_clean_passes():
    assert check_placeholders(
        "Your session will expire in {0} minutes.",
        "A sua sessão expirará em {0} minutos.",
    ) == []


def test_placeholders_dropped_is_reported():
    results = check_placeholders(
        'Hello {0}, {1} added you to team "{2}".',
        "Olá {0}, foi adicionado à equipe.",
    )
    dropped = {r["token"] for r in results if r["kind"] == "dropped"}
    assert "{1}" in dropped and "{2}" in dropped


def test_placeholders_number_value_mismatch_is_one_finding():
    results = check_placeholders(
        "Export up to 5,000 rows per request.",
        "Exporte até 500 linhas por solicitação.",
    )
    assert len([r for r in results if r["type"] == "number"]) == 2  # one dropped + one added = 1 mismatch pair
    kinds = {r["kind"] for r in results if r["type"] == "number"}
    assert kinds == {"dropped", "added"}


def test_placeholders_currency_change():
    results = check_placeholders(
        "Shipping is free for orders over $99.",
        "O frete é grátis para pedidos acima de R$99.",
    )
    assert any(r["kind"] == "wrong_currency" for r in results)


def test_dialect_lexicon_marker():
    results = check_dialect_and_style("Toque em Definições para alterar o seu número de telemóvel.")
    lex = [r for r in results if r["kind"] == "lexicon"]
    assert {r["marker"] for r in lex} >= {"definicoes", "telemovel"} or {r["span"] for r in lex} >= {"Definições", "telemóvel"}


def test_dialect_spacing():
    results = check_dialect_and_style("Contacte-nos através do seu  telemóvel.")
    assert any(r["kind"] == "spacing" for r in results)


def test_dialect_punctuation():
    results = check_dialect_and_style("A senha deve conter pelo menos 8 caracteres..")
    assert any(r["kind"] == "punctuation" for r in results)


def test_dialect_capitalization():
    results = check_dialect_and_style("Sua Atividade Recente")
    assert any(r["kind"] == "capitalization" for r in results)


def test_dialect_register_vosso():
    results = check_dialect_and_style("Agradecemos pelo vosso feedback!")
    assert any(r["kind"] == "register" and r["marker"] == "vosso" for r in results)


def test_dialect_register_mixed_tu_voce():
    results = check_dialect_and_style("Podes alterar a tua foto de perfil. Só você pode vê-la.")
    assert any(r["kind"] == "register" and "tu" in r["marker"] for r in results)


def test_dialect_clean_text_is_clean():
    assert check_dialect_and_style("Salve as alterações antes de fechar a janela.") == []


def test_equipa_does_not_match_equipamento():
    assert [r for r in check_dialect_and_style("O equipamento foi atualizado.") if r["kind"] == "lexicon"] == []


def test_dedupe_merges_same_span():
    results = {
        "check_glossary": [{"kind": "forbidden_used", "span": "ligação", "expected": "link"}],
        "check_dialect_and_style": [{"kind": "lexicon", "span": "ligação"}],
    }
    merged = dedupe_findings(results)
    assert len(merged) == 1
    assert merged[0]["reported_by"] == "check_glossary"
    assert merged[0]["also_reported_by"] == ["check_dialect_and_style"]


def test_run_all_returns_three_checks():
    out = run_all("Save the file.", "Salve o arquivo.", {"save": "salvar"})
    assert set(out) == {"check_glossary", "check_placeholders", "check_dialect_and_style"}
