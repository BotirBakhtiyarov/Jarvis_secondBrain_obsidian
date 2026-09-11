from orion.main import trim_history


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
