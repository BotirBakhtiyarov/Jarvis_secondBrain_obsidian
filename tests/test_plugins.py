from types import SimpleNamespace

from jarvis.plugins import load_plugins
from jarvis.tools import ToolRegistry


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
