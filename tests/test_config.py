import pytest

from mtqa import config


@pytest.fixture
def no_env(monkeypatch):
    for var in ("MTQA_BASE_URL", "MTQA_MODEL", "MTQA_TRACKING_URI", "MTQA_EXPERIMENT", "MTQA_CONFIG"):
        monkeypatch.delenv(var, raising=False)


def test_defaults_without_file_or_env(no_env, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    settings = config.Settings.load()
    assert settings.base_url == "http://localhost:13305/v1"
    assert settings.experiment == "mt-qa-agent"


def test_file_is_used(no_env, tmp_path):
    conf = tmp_path / "mtqa.toml"
    conf.write_text('[endpoint]\nmodel = "from-file"\n', encoding="utf-8")
    settings = config.Settings.load(path=conf)
    assert settings.model == "from-file"


def test_env_beats_file(no_env, tmp_path, monkeypatch):
    conf = tmp_path / "mtqa.toml"
    conf.write_text('[endpoint]\nmodel = "from-file"\n', encoding="utf-8")
    monkeypatch.setenv("MTQA_MODEL", "from-env")
    settings = config.Settings.load(path=conf)
    assert settings.model == "from-env"


def test_override_beats_env(no_env, tmp_path, monkeypatch):
    monkeypatch.setenv("MTQA_MODEL", "from-env")
    settings = config.Settings.load(overrides={"model": "from-cli"}, path=tmp_path / "none.toml")
    assert settings.model == "from-cli"
