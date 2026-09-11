from orion.mcp import MCPManager, load_mcp_config
from orion.tools import Tool


def register(registry, config):
    """MCP serverlarini ulab, ularning tool'larini ro'yxatga oladi.

    `mcp` paketi yoki `~/.orion/mcp.json` konfiguratsiyasi bo'lmasa,
    jimgina o'tkazib yuboriladi (ORION boshqa tool'lar bilan ishlayveradi).
    """

    try:
        import mcp  # noqa: F401
    except ImportError:
        return

    servers = load_mcp_config()
    if not servers:
        return

    try:
        manager = MCPManager(servers)
        manager.connect()
        tools = manager.list_tools()
    except Exception:  # noqa: BLE001
        return

    for server, tool in tools:
        registry.register(MCPTool(manager, server, tool))


class MCPTool(Tool):
    def __init__(self, manager: MCPManager, server: str, tool):
        schema = getattr(tool, "inputSchema", None) or {}
        super().__init__(
            name=f"mcp__{server}__{tool.name}",
            description=(tool.description or f"MCP tool '{tool.name}' from '{server}'"),
            parameters=schema.get("properties", {}),
            required=schema.get("required", []),
        )
        self._manager = manager
        self._server = server
        self._tool = tool.name

    def execute(self, **kwargs):
        result = self._manager.call_tool(self._server, self._tool, kwargs)

        text = ""
        for block in getattr(result, "content", None) or []:
            if getattr(block, "type", "") == "text":
                text += getattr(block, "text", "")

        if getattr(result, "isError", False):
            return {"error": text or "MCP tool error"}

        return {"result": text or "(no text output)"}
