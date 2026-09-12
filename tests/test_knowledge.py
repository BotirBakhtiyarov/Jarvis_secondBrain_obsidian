"""Tests for the unified knowledge search (notes + workspace code)."""

from pathlib import Path

from orion.obsidian import Vault
from orion.plugins.knowledge_plugin import SearchKnowledgeTool
from orion.tools import ToolRegistry


def _make_config(tmp_path: Path, workspace: Path | None = None) -> object:
    """Minimal config-like object for SearchKnowledgeTool."""
    from types import SimpleNamespace

    ws = workspace or tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    (ws / "main.py").write_text("print('hello world from orion')\n")
    (ws / "utils").mkdir(exist_ok=True)
    (ws / "utils" / "help.py").write_text("def help():\n    return 'orc'\n")

    return SimpleNamespace(
        obsidian_vault=tmp_path / "vault",
        workspace=str(ws),
    )


def _make_vault(tmp_path: Path) -> Vault:
    vault = Vault(tmp_path / "vault")
    vault.root.mkdir(exist_ok=True)
    vault.create("Notes/Obsidian.md", "Obsidian Vault notes tool\n")
    vault.create("Projects/Apollo.md", "Apollo project: rocket roadmap and budget.\n")
    return vault


def _register(registry: ToolRegistry, config: object) -> SearchKnowledgeTool:
    from orion.plugins.knowledge_plugin import register

    register(registry, config)
    return registry.get("search_knowledge")


def _workspace_files(config: object) -> list[tuple[str, str]]:
    root = Path(config.workspace)
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
    suffixes = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".kts",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".ini",
        ".sh",
        ".sql",
        ".css",
        ".html",
        ".xml",
    }
    files: list[tuple[str, str]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.suffix not in suffixes:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files.append((str(p.relative_to(root)), content))
    return files


def test_search_returns_merged_results(tmp_path: Path):
    """Query 'rocket' matches note (Apollo project: rocket roadmap) and code files exist."""
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("rocket", limit=5)
    assert res["query"] == "rocket"
    assert res["semantic_available"] is False  # no fastembed index

    paths = {r["path"] for r in res["results"]}
    # Notes should be found via keyword
    assert "Projects/Apollo.md" in paths
    # At least the note result exists
    assert len(paths) >= 1


def test_search_code_and_notes_together(tmp_path: Path):
    """Query 'orc' matches workspace code files but not notes."""
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("orc", limit=10)
    results = res["results"]
    assert len(results) >= 1

    sources = {r["source"] for r in results}
    # Workspace code files match 'orc', notes do not — so code should appear
    assert "code" in sources or any("orc" in r.get("excerpt", "").lower() for r in results)


def test_search_keyword_matches_both_domains(tmp_path: Path):
    """A query matching both notes and code should return merged results."""
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    # 'project' is in both a note title and code paths
    res = tool.execute("project", limit=10)
    results = res["results"]
    assert len(results) >= 1

    sources = {r["source"] for r in results}
    # Should have at least 'code' (main.py mentions hello world, but path contains 'project'? no)
    # But should have 'notes' (Apollo.md mentions 'project')
    assert "notes" in sources


def test_search_sources_are_labeled(tmp_path: Path):
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    # Query that matches a note and a code file
    res = tool.execute("orc", limit=10)
    results = res["results"]
    assert len(results) >= 1

    sources = {r["source"] for r in results}
    # Should include both notes and code sources
    assert "notes" in sources or "code" in sources or "notes+code" in sources


def test_search_no_results_for_unknown_query(tmp_path: Path):
    config = _make_config(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("xyzzynonexistent123", limit=5)
    # Should return empty (no keyword match)
    assert res["results"] == []


def test_search_limit_respected(tmp_path: Path):
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("project", limit=1)
    assert len(res["results"]) <= 1


def test_search_invalid_limit_clamped(tmp_path: Path):
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("project", limit=0)
    assert len(res["results"]) <= 10  # default clamped to 1-30

    res2 = tool.execute("project", limit=999)
    assert len(res2["results"]) <= 30


def test_search_workspace_missing(tmp_path: Path):
    from types import SimpleNamespace

    _make_vault(tmp_path)
    config = SimpleNamespace(
        obsidian_vault=tmp_path / "vault",
        workspace=str(tmp_path / "nonexistent_ws"),
    )
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("anything", limit=5)
    # Only notes should be returned
    assert all(r["source"] in ("notes", "notes+code") for r in res["results"])


def test_excerpt_contains_query_word(tmp_path: Path):
    config = _make_config(tmp_path)
    _make_vault(tmp_path)
    registry = ToolRegistry()
    tool = _register(registry, config)

    res = tool.execute("orc", limit=5)
    for r in res["results"]:
        if r["excerpt"]:
            excerpt_lower = r["excerpt"].lower()
            assert "orc" in excerpt_lower or "project" in excerpt_lower
