import asyncio
import json
import threading
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".jarvis" / "mcp.json"


def load_mcp_config(path: str | Path | None = None) -> dict:
    """MCP server konfiguratsiyasini o'qiydi.

    Fayl formati (Claude Code'nikiga o'xshash):

        {
          "mcpServers": {
            "time": {"command": "uvx", "args": ["mcp-server-time"]}
          }
        }
    """

    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        return {}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    servers = data.get("mcpServers", data)
    return servers if isinstance(servers, dict) else {}


class MCPManager:
    """MCP (stdio) serverlarini boshqaradi.

    MCP SDK asinxron, JARVIS esa sinxron bo'lgani uchun alohida event-loop
    thread'da ishlatiladi va sinxron usullar orqali murojaat qilinadi.
    """

    def __init__(self, servers: dict):
        self._servers = servers
        self._sessions: dict[str, object] = {}
        self._contexts: dict[str, tuple] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True
        )
        self._thread.start()

    def _sync(self, coro, timeout: int = 60):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def _connect():
            for name, spec in self._servers.items():
                params = StdioServerParameters(
                    command=spec.get("command"),
                    args=list(spec.get("args", [])),
                    env=spec.get("env"),
                )
                ctx = stdio_client(params)
                read, write = await ctx.__aenter__()
                session_ctx = ClientSession(read, write)
                session = await session_ctx.__aenter__()
                await session.initialize()
                self._sessions[name] = session
                self._contexts[name] = (ctx, session_ctx)

        self._sync(_connect())

    def list_tools(self) -> list:
        async def _list():
            out = []
            for name, session in self._sessions.items():
                result = await session.list_tools()
                for tool in result.tools:
                    out.append((name, tool))
            return out

        return self._sync(_list())

    def call_tool(self, server: str, tool: str, arguments: dict):
        async def _call():
            session = self._sessions[server]
            return await session.call_tool(tool, arguments=arguments or {})

        return self._sync(_call())
