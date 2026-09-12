import pytest

from orion import i18n, ui


@pytest.fixture(autouse=True)
def _english_and_clean_state():
    i18n.set_language("en")
    ui._REMEMBERED["label"] = ""
    ui._REMEMBERED["text"] = ""
    ui.remember_thinking("")
    yield
    ui._REMEMBERED["label"] = ""
    ui._REMEMBERED["text"] = ""
    ui.remember_thinking("")


def test_user_box_parts_shape():
    top, prefix, bottom = ui.user_box_parts(40)
    assert top.startswith("╭─ ")
    assert top.endswith("╮")
    assert bottom.startswith("╰")
    assert bottom.endswith("╯")
    assert prefix == "│ "
    assert len(top) == len(bottom) == 40


def test_user_box_parts_clamps_to_minimum():
    top, _prefix, bottom = ui.user_box_parts(5)
    assert len(top) == len(bottom) == 20


def test_print_user_box_draws_box():
    with ui.console.capture() as cap:
        ui.print_user_box("hello")
    out = cap.get()
    assert "hello" in out
    assert out.count("╭") == 1 and out.count("╰") == 1


def test_collapsed_preview_shows_hint_and_remembers_full():
    lines = [f"line-{i}" for i in range(10)]
    with ui.console.capture() as cap:
        ui.collapsed_preview("output", lines)
    out = cap.get()
    assert "line-0" in out
    assert "line-3" in out
    assert "line-9" not in out
    assert "/show" in out
    assert ui._REMEMBERED["text"].splitlines() == lines


def test_show_remembered_prints_full_text():
    ui.remember("output", "aaa\nbbb")
    with ui.console.capture() as cap:
        ui.show_remembered()
    out = cap.get()
    assert "aaa" in out and "bbb" in out


def test_show_without_content_is_empty():
    with ui.console.capture() as cap:
        ui.show_remembered()
        ui.show_thinking()
    assert "Nothing collapsed yet." in cap.get()


def test_turn_view_buffers_answer_without_terminal():
    view = ui.TurnView(interactive=True)
    with ui.console.capture() as cap:
        view.text_delta("Hello ")
        view.text_delta("**world**")
        view.end_turn()
    out = cap.get()
    assert "Hello" in out and "world" in out


def test_turn_view_collapses_reasoning_with_hint():
    view = ui.TurnView(interactive=True)
    with ui.console.capture() as cap:
        view.reasoning_delta("deep thought " * 100)
        view.end_turn()
    out = cap.get()
    assert "Thinking" in out and "/think" in out
    assert "deep thought" not in out

    with ui.console.capture() as cap2:
        ui.show_thinking()
    assert "deep thought" in cap2.get()


def test_turn_view_reasoning_then_answer():
    view = ui.TurnView(interactive=True)
    with ui.console.capture() as cap:
        view.reasoning_delta("think " * 50)
        view.text_delta("# Answer\nbody")
        view.end_turn()
    out = cap.get()
    assert "Answer" in out and "body" in out
    assert "/think" in out


def test_tool_result_collapses_long_output(monkeypatch):
    long_out = "\n".join(f"log-{i}" for i in range(30))
    with ui.console.capture() as cap:
        ui.print_tool_result({"exit_code": 0, "stdout": long_out, "stderr": ""})
    out = cap.get()
    assert "log-0" in out and "log-3" in out
    assert "log-29" not in out
    assert "/show" in out
    assert ui._REMEMBERED["text"].splitlines()[29] == "log-29"


def test_tool_result_small_output_not_collapsed():
    with ui.console.capture() as cap:
        ui.print_tool_result({"exit_code": 0, "stdout": "ok", "stderr": ""})
    assert "ok" in cap.get()
