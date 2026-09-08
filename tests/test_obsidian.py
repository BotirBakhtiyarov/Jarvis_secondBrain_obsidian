from pathlib import Path

import pytest

from orion.obsidian import Vault


@pytest.fixture
def vault(tmp_path):
    v = Vault(tmp_path)
    (v.root / "Inbox").mkdir()
    (v.root / "Projects").mkdir()
    (v.root / "Inbox" / "Meeting notes.md").write_text(
        "# Meeting\nDiscussed the Q3 roadmap and budget.\n",
        encoding="utf-8",
    )
    (v.root / "Projects" / "Apollo.md").write_text(
        "---\ntags: [apollo, space]\n---\nApollo project status: on track.\n",
        encoding="utf-8",
    )
    return v


def test_search_finds_by_content(vault):
    results = vault.search("budget")
    assert any("Meeting notes" in r["path"] for r in results)


def test_search_ranks_filename_highest(vault):
    results = vault.search("apollo")
    assert results[0]["path"] == "Projects/Apollo.md"


def test_search_reads_frontmatter_tags(vault):
    results = vault.search("space")
    assert any("Apollo.md" in r["path"] for r in results)


def test_read_note(vault):
    out = vault.read("Inbox/Meeting notes.md")
    assert "roadmap" in out["content"]
    assert out["truncated"] is False


def test_create_append_update_flow(vault):
    assert vault.create("Inbox/Idea.md", "hello")["success"] is True
    assert vault.append("Inbox/Idea.md", "world")["success"] is True
    assert "world" in vault.read("Inbox/Idea.md")["content"]

    res = vault.update("Inbox/Idea.md", "replaced")
    assert res["success"] is True
    assert "backup" in res
    assert vault.read("Inbox/Idea.md")["content"] == "replaced"


def test_create_duplicate_rejected(vault):
    vault.create("Inbox/Idea.md", "hello")
    assert vault.create("Inbox/Idea.md", "again")["success"] is False


def test_list_notes(vault):
    out = vault.list_notes()
    assert out["total"] == 2
    assert "Inbox/Meeting notes.md" in out["notes"]


def test_path_traversal_blocked(vault):
    with pytest.raises(ValueError):
        vault.safe_path("../../etc/passwd")
