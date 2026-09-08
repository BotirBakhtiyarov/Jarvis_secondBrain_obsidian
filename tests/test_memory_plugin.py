from jarvis.obsidian import Vault
from jarvis.plugins.memory_plugin import (
    DailyNoteTool,
    SaveMemoryTool,
    TriageInboxTool,
)


def _vault(tmp_path):
    vault = Vault(tmp_path)
    (vault.root / "Inbox").mkdir()
    (vault.root / "Projects").mkdir()
    return vault


def test_new_note_has_frontmatter_and_related(tmp_path):
    vault = _vault(tmp_path)
    vault.create("Projects/Apollo.md", "Apollo project: rocket roadmap and budget.\n")
    tool = SaveMemoryTool(vault)

    res = tool.execute("Apollo budget notes", "Keep budget under 1M.", folder="Inbox")
    assert res["success"] is True
    assert res["action"] == "created"

    note = vault.read(res["path"])["content"]
    assert note.startswith("---")
    assert "created:" in note
    assert "tags: [inbox]" in note
    assert "## Related" in note
    assert "[[Apollo]]" in note


def test_same_title_appends_instead_of_duplicate(tmp_path):
    vault = _vault(tmp_path)
    vault.create("Inbox/Notes.md", "old\n")
    tool = SaveMemoryTool(vault)

    res = tool.execute("Notes", "new info", folder="Inbox")
    assert res["action"] == "appended"

    content = vault.read("Inbox/Notes.md")["content"]
    assert "old" in content
    assert "new info" in content
    assert "## " in content  # sana sarlavhasi


def test_different_title_creates_new_note(tmp_path):
    vault = _vault(tmp_path)
    vault.create("Projects/Apollo.md", "Apollo project.\n")
    tool = SaveMemoryTool(vault)

    res = tool.execute("Apollo budget notes", "Budget details", folder="Inbox")
    assert res["action"] == "created"
    assert res["path"] == "Inbox/Apollo budget notes.md"


def test_daily_note_creates_and_links_yesterday(tmp_path):
    from datetime import date, timedelta

    vault = _vault(tmp_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    vault.create(f"Daily/{yesterday}.md", "---\n---\n")

    tool = DailyNoteTool(vault)
    res = tool.execute()
    today = date.today().isoformat()

    assert res["path"] == f"Daily/{today}.md"
    content = vault.read(res["path"])["content"]
    assert "tags: [daily]" in content
    assert f"[[{yesterday}]]" in content

    res2 = tool.execute("hello world")
    assert "hello world" in vault.read(res2["path"])["content"]


def test_triage_inbox_moves_to_archive(tmp_path):
    vault = _vault(tmp_path)
    vault.create("Inbox/a.md", "a")
    vault.create("Inbox/b.md", "b")

    tool = TriageInboxTool(vault)
    res = tool.execute()

    assert res["action"] == "triage"
    assert len(res["moved"]) == 2
    assert not (vault.root / "Inbox" / "a.md").exists()
    assert not (vault.root / "Inbox" / "b.md").exists()

    moved_names = {p.split("/")[-1] for p in res["moved"]}
    assert moved_names == {"a.md", "b.md"}
