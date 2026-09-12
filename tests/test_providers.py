import pytest

from orion.providers import PROVIDERS, get_provider, resolve_api_key


def test_all_providers_present():
    assert set(PROVIDERS) == {"deepseek", "anthropic", "openai", "gemini", "ollama"}


def test_get_provider_normalizes_name():
    assert get_provider("OpenAI ").key_env == "OPENAI_API_KEY"
    assert get_provider("DEEPSEEK").default_model == "deepseek-chat"


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("nope")


def test_ollama_is_local_and_free():
    ollama = get_provider("ollama")
    assert ollama.local is True
    assert ollama.input_price == 0.0 and ollama.output_price == 0.0


def test_resolve_api_key_reads_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert resolve_api_key(get_provider("openai")) == "sk-test"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert resolve_api_key(get_provider("openai")) == ""


def test_resolve_api_key_ollama_fallback(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert resolve_api_key(get_provider("ollama")) == "ollama"

    monkeypatch.setenv("OLLAMA_API_KEY", "custom")
    assert resolve_api_key(get_provider("ollama")) == "custom"
