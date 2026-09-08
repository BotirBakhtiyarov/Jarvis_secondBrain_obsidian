from jarvis.obsidian import Vault
from jarvis.plugins.memory_plugin import SaveMemoryTool


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
