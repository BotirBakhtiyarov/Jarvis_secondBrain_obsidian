from types import SimpleNamespace

from orion.plugins import load_plugins
from orion.tools import ToolRegistry


def test_plugin_discovery_registers_tools(tmp_path):
    config = SimpleNamespace(obsidian_vault=tmp_path, workspace=tmp_path)
    registry = ToolRegistry()

    loaded = load_plugins(registry, config)

    assert "obsidian_plugin" in loaded
    assert "code_plugin" in loaded
    assert "memory_plugin" in loaded
    assert "system_plugin" in loaded

    names = set(registry.names())
    assert "search_notes" in names
    assert "run_command" in names
    assert "save_memory" in names
    assert "open_url" in names
    assert "screenshot" in names
    assert "get_time" in names
    assert "daily_note" in names
    assert "triage_inbox" in names
    assert "reindex" in names
    assert "link_notes" in names
    assert "web_search" in names
    assert "git_status" in names
    assert "git_diff" in names
    assert "git_log" in names
    assert "git_commit" in names
    assert "git_create_pr" in names
