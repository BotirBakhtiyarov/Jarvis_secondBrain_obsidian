import sys
import textwrap

import pytest

mcp = pytest.importorskip("mcp")

from orion.mcp import MCPManager  # noqa: E402

SERVER_CODE = textwrap.dedent(
    """
    from mcp.server.fastmcp import FastMCP

    app = FastMCP("test-server")

    @app.tool()
    def add(a: int, b: int) -> int:
        return a + b

    if __name__ == "__main__":
        app.run()
    """
)


def test_mcp_manager_lists_and_calls_tools(tmp_path):
    server_file = tmp_path / "server.py"
    server_file.write_text(SERVER_CODE, encoding="utf-8")

    manager = MCPManager({"test": {"command": sys.executable, "args": [str(server_file)]}})
    manager.connect()

    tools = manager.list_tools()
    names = [tool.name for _, tool in tools]
    assert "add" in names

    result = manager.call_tool("test", "add", {"a": 2, "b": 3})
    text = "".join(block.text for block in result.content if getattr(block, "type", "") == "text")
    assert "5" in text
