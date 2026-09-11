import asyncio
import json
import threading
from concurrent.futures import Future
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".orion" / "mcp.json"

# All live managers; closed when ORION exits.
_MANAGERS: list["MCPManager"] = []


def register_manager(manager: "MCPManager") -> None:
    _MANAGERS.append(manager)


def close_all(timeout: int = 10) -> None:
    """Close all registered MCP managers."""
    for manager in _MANAGERS:
        try:
            manager.close(timeout=timeout)
        except Exception:  # noqa: BLE001
            pass
    _MANAGERS.clear()


def load_mcp_config(path: str | Path | None = None) -> dict:
    """Read MCP server config from a Claude Code-style ``mcpServers`` JSON file."""

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
    """Manage stdio MCP servers from synchronous code.

    The MCP SDK is async, so all sessions live in one long-lived task
    ("actor") — anyio cancel scopes must enter and exit on the same task.
    Sync callers send requests over an asyncio.Queue and wait.
    """

    def __init__(self, servers: dict):
        self._servers = servers
        self._loop = asyncio.new_event_loop()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        sessions: dict[str, object] = {}
        contexts: list = []

        try:
            for name, spec in self._servers.items():
                try:
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
                    sessions[name] = session
                    contexts.extend([ctx, session_ctx])
                except Exception:  # noqa: BLE001
                    continue  # one broken server must not break the others

            self._ready.set()

            while True:
                future, op, args = await self._queue.get()
                try:
                    if op == "list":
                        future.set_result(await self._list(sessions))
                    elif op == "close":
                        future.set_result(None)
                        break
                    else:
                        future.set_result(await self._call(sessions, args[0], args[1], args[2]))
                except Exception as exc:  # noqa: BLE001
                    future.set_exception(exc)
        finally:
            self._ready.set()
            for ctx in reversed(contexts):
                try:
                    await ctx.__aexit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass

    async def _list(self, sessions):
        out = []
        for name, session in sessions.items():
            result = await session.list_tools()
            for tool in result.tools:
                out.append((name, tool))
        return out

    async def _call(self, sessions, server, tool, arguments):
        return await sessions[server].call_tool(tool, arguments=arguments or {})

    def _request(self, op, *args, timeout: int = 60):
        future: Future = Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (future, op, args))
        return future.result(timeout=timeout)

    def connect(self, timeout: int = 60):
        if not self._ready.wait(timeout=timeout):
            raise TimeoutError("MCP servers did not connect in time")

    def list_tools(self) -> list:
        return self._request("list")

    def call_tool(self, server: str, tool: str, arguments: dict):
        return self._request("call", server, tool, arguments)

    def close(self, timeout: int = 10):
        """Close all MCP sessions and stop the worker thread."""
        try:
            self._request("close", timeout=timeout)
        except Exception:  # noqa: BLE001
            pass
