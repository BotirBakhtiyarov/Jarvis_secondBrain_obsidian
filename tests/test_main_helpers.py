from types import SimpleNamespace

import pytest

from orion import i18n, ui
from orion.main import _split_model_arg, cmd_model, trim_history


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")


@pytest.fixture
def model_ctx(monkeypatch):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OLLAMA_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config = SimpleNamespace(
        provider="deepseek",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="k",
        input_price=0.27,
        output_price=1.10,
    )
    return {"config": config, "client": object(), "args": []}


def test_cmd_model_lists_providers(model_ctx):
    with ui.console.capture() as cap:
        cmd_model(model_ctx)
    out = cap.get()
    for name in ("deepseek", "anthropic", "openai", "gemini", "ollama"):
        assert name in out
    assert "(current)" in out
    assert "/model <provider>:<model>" in out


def test_cmd_model_switch_provider_and_model(model_ctx, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model_ctx["args"] = ["openai:gpt-4o-mini"]
    with ui.console.capture():
        cmd_model(model_ctx)

    cfg = model_ctx["config"]
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"
    assert "api.openai.com" in str(model_ctx["client"].base_url)
    assert cfg.input_price == 0.15 and cfg.output_price == 0.60


def test_cmd_model_ollama_colon_model(model_ctx):
    model_ctx["args"] = ["ollama:llama3.2:3b"]
    with ui.console.capture():
        cmd_model(model_ctx)

    cfg = model_ctx["config"]
    assert cfg.provider == "ollama"
    assert cfg.model == "llama3.2:3b"


def test_cmd_model_plain_model_keeps_provider(model_ctx):
    model_ctx["args"] = ["deepseek-reasoner"]
    with ui.console.capture():
        cmd_model(model_ctx)

    cfg = model_ctx["config"]
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-reasoner"


def test_cmd_model_unknown_prefix_treated_as_model(model_ctx):
    # "bogus" is not a registered provider, so the whole token becomes the
    # model name on the current provider (graceful degradation).
    model_ctx["args"] = ["bogus:model"]
    with ui.console.capture():
        cmd_model(model_ctx)
    cfg = model_ctx["config"]
    assert cfg.model == "bogus:model"
    assert cfg.provider == "deepseek"  # unchanged


# --- _split_model_arg --------------------------------------------------------


def test_split_model_arg_provider_model():
    assert _split_model_arg("openai:gpt-4o-mini") == ("openai", "gpt-4o-mini")


def test_split_model_arg_ollama_colon_model():
    assert _split_model_arg("ollama:llama3.2:3b") == ("ollama", "llama3.2:3b")


def test_split_model_arg_plain_model():
    assert _split_model_arg("deepseek-reasoner") == (None, "deepseek-reasoner")


def test_split_model_arg_unknown_prefix_is_model():
    assert _split_model_arg("bogus:model") == (None, "bogus:model")


def test_cmd_model_missing_key_rejected(model_ctx):
    model_ctx["args"] = ["openai:gpt-4o-mini"]  # OPENAI_API_KEY unset
    with ui.console.capture() as cap:
        cmd_model(model_ctx)
    assert "OPENAI_API_KEY" in cap.get()
    assert model_ctx["config"].provider == "deepseek"


def _msgs(n: int) -> list[dict]:
    """n plain user/assistant messages."""
    out = []
    for i in range(n):
        out.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"})
    return out


def test_trim_keeps_last_max_history():
    msgs = [{"role": "system", "content": "sys"}] + _msgs(20)
    out = trim_history(msgs, max_history=6)
    assert len(out) == 7
    assert out[0]["role"] == "system"
    assert out[-1]["content"] == "msg 19"


def test_trim_does_nothing_within_limit():
    msgs = [{"role": "system", "content": "sys"}] + _msgs(5)
    assert trim_history(msgs, max_history=50) is msgs


def test_trim_zero_disabled():
    msgs = [{"role": "system", "content": "sys"}] + _msgs(20)
    assert trim_history(msgs, max_history=0) is msgs


def test_trim_never_splits_tool_call_chain():
    # assistant(tool_calls) -> tool result -> user -> assistant
    chain = [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "result"},
        {"role": "user", "content": "continue"},
        {"role": "assistant", "content": "answer"},
    ]
    msgs = [{"role": "system", "content": "sys"}, *(_msgs(14) + chain)]
    out = trim_history(msgs, max_history=6)

    # the tool chain must survive intact
    assert out[1:][-4:] == chain
    # trimming must never start on a "tool" message
    assert out[1]["role"] != "tool"
