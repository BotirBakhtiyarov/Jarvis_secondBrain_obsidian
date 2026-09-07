from pathlib import Path

import pytest

from jarvis.workspace import Workspace


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path)
    (w.root / "src").mkdir()
    (w.root / "src" / "app.py").write_text(
        "print('hello')\nprint('world')\n",
        encoding="utf-8",
    )
    return w


def test_list_files(ws):
    out = ws.list_files()
    assert any(e["name"] == "src" and e["type"] == "dir" for e in out["entries"])


def test_read_file_with_range(ws):
    out = ws.read_file("src/app.py", start=2, end=2)
    assert out["content"] == "print('world')"
    assert out["total_lines"] == 2


def test_write_file(ws):
    res = ws.write_file("src/new.py", "x = 1\n")
    assert res["success"] is True
    assert "x = 1" in ws.read_file("src/new.py")["content"]


def test_edit_file_replaces_unique(ws):
    res = ws.edit_file("src/app.py", "hello", "HELLO")
    assert res["success"] is True
    assert res["replacements"] == 1
    assert "HELLO" in ws.read_file("src/app.py")["content"]


def test_edit_file_ambiguous_requires_context(ws):
    ws.write_file("src/dup.py", "aa bb aa bb\n")
    res = ws.edit_file("src/dup.py", "bb", "BB")
    assert "error" in res


def test_edit_file_missing_old_text(ws):
    res = ws.edit_file("src/app.py", "does-not-exist", "x")
    assert "error" in res


def test_path_traversal_blocked(ws):
    with pytest.raises(ValueError):
        ws.safe_path("../../etc/passwd")
