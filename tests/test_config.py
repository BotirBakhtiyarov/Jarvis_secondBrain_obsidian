import pytest

from orion.config import load_config

_CLEAR_VARS = [
    "ORION_PROVIDER",
    "ORION_MODEL",
    "ORION_BASE_URL",
    "ORION_INPUT_PRICE",
    "ORION_OUTPUT_PRICE",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_INPUT_PRICE",
    "DEEPSEEK_OUTPUT_PRICE",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OLLAMA_API_KEY",
]


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in _CLEAR_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OBSIDIAN_VAULT", str(tmp_path))
    return monkeypatch


def test_default_provider_is_deepseek(clean_env):
    config = load_config()
    assert config.provider == "deepseek"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-chat"
    assert config.input_price == 0.27
    assert config.output_price == 1.10


def test_legacy_deepseek_env_still_works(clean_env):
    clean_env.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    clean_env.setenv("DEEPSEEK_INPUT_PRICE", "0.5")
    config = load_config()
    assert config.model == "deepseek-reasoner"
    assert config.input_price == 0.5


def test_provider_switch_via_env(clean_env):
    clean_env.setenv("ORION_PROVIDER", "openai")
    clean_env.setenv("OPENAI_API_KEY", "sk-test")
    config = load_config()
    assert config.provider == "openai"
    assert config.api_key == "sk-test"
    assert "api.openai.com" in config.base_url
    assert config.model == "gpt-4o-mini"
    assert config.input_price == 0.15
    assert config.output_price == 0.60


def test_orion_model_overrides_any_provider(clean_env):
    clean_env.setenv("ORION_PROVIDER", "openai")
    clean_env.setenv("OPENAI_API_KEY", "sk-test")
    clean_env.setenv("ORION_MODEL", "gpt-4o")
    config = load_config()
    assert config.model == "gpt-4o"


def test_ollama_local_defaults(clean_env):
    clean_env.setenv("ORION_PROVIDER", "ollama")
    config = load_config()
    assert config.api_key == "ollama"
    assert config.input_price == 0.0 and config.output_price == 0.0
    assert "localhost:11434" in config.base_url


def test_unknown_provider_raises(clean_env):
    clean_env.setenv("ORION_PROVIDER", "bogus")
    with pytest.raises(ValueError, match="Unknown provider"):
        load_config()


def test_global_price_override(clean_env):
    clean_env.setenv("ORION_PROVIDER", "openai")
    clean_env.setenv("OPENAI_API_KEY", "sk")
    clean_env.setenv("ORION_INPUT_PRICE", "2.5")
    config = load_config()
    assert config.input_price == 2.5
    assert config.output_price == 0.60
