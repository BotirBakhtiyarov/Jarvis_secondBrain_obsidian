"""Vault transports: local filesystem (default) or the Obsidian Local REST API.

Both transports expose the same small interface, so ``orion.obsidian.Vault``
runs unchanged on top of either one:

* :class:`FileTransport` — read/write Markdown directly on disk. Works with no
  extra software and is the default.
* :class:`RestTransport` — talk to the community
  `Obsidian Local REST API <https://github.com/coddingtonbear/obsidian-local-rest-api>`_
  plugin over HTTP. Lets ORION read/write the vault while Obsidian is open.
* :class:`FallbackTransport` — try REST first and transparently fall back to
  the filesystem when the server is unreachable.

The interface is intentionally tiny: ``exists``, ``read``, ``write``,
``append``, ``delete``, ``move`` and ``list_markdown``.
"""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Internal vault dirs (index, backups, Obsidian config).
IGNORED_DIRS = {
    ".obsidian",
    ".orion_backups",
    ".orion_index",
    ".jarvis_backups",
    ".jarvis_index",
}

DEFAULT_API_URL = "https://127.0.0.1:27124"


class FileTransport:
    """Read/write notes directly on disk (the default, no server needed)."""

    scheme = "file"

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, rel: str) -> Path:
        return self.root / rel

    def exists(self, rel: str) -> bool:
        return self._path(rel).exists()

    def read(self, rel: str) -> str:
        return self._path(rel).read_text(encoding="utf-8", errors="ignore")

    def write(self, rel: str, content: str) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def append(self, rel: str, content: str) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(content)

    def delete(self, rel: str) -> None:
        self._path(rel).unlink(missing_ok=True)

    def move(self, src: str, dst: str) -> None:
        source = self._path(src)
        target = self._path(dst)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)

    def list_markdown(self, folder: str = "") -> list[str]:
        base = self._path(folder) if folder else self.root
        if not base.exists():
            return []
        notes = (
            str(p.relative_to(self.root))
            for p in base.rglob("*.md")
            if not (IGNORED_DIRS & set(p.parts))
        )
        return sorted(notes)


class RestTransport:
    """Talk to the Obsidian *Local REST API* plugin over HTTP.

    Only the standard library is used (``urllib``), so enabling this transport
    adds no dependency. The default URL is the plugin's HTTPS endpoint; its
    self-signed certificate is not verified unless ``verify=True``.
    """

    scheme = "rest"

    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        api_key: str = "",
        verify: bool = False,
        timeout: float = 10.0,
    ):
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        self.api_key = api_key or ""
        self.verify = verify
        self.timeout = timeout
        self._context = None if verify else ssl._create_unverified_context()

    # --- HTTP plumbing ----------------------------------------------------

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, rel: str = "", data: bytes | None = None):
        quoted = urllib.parse.quote(rel) if rel else ""
        url = f"{self.base_url}/vault/{quoted}"
        request = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        if data is not None:
            request.add_header("Content-Type", "text/markdown; charset=utf-8")
        return urllib.request.urlopen(request, timeout=self.timeout, context=self._context)

    # --- Transport interface ---------------------------------------------

    def exists(self, rel: str) -> bool:
        try:
            with self._request("GET", rel) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return False
            raise

    def read(self, rel: str) -> str:
        with self._request("GET", rel) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def write(self, rel: str, content: str) -> None:
        with self._request("PUT", rel, data=content.encode("utf-8")) as resp:
            resp.read()

    def append(self, rel: str, content: str) -> None:
        with self._request("POST", rel, data=content.encode("utf-8")) as resp:
            resp.read()

    def delete(self, rel: str) -> None:
        try:
            with self._request("DELETE", rel) as resp:
                resp.read()
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise

    def move(self, src: str, dst: str) -> None:
        if not self.exists(src):
            raise FileNotFoundError(src)
        self.write(dst, self.read(src))
        self.delete(src)

    def list_markdown(self, folder: str = "") -> list[str]:
        rel = folder.rstrip("/") + "/" if folder else ""
        with self._request("GET", rel) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
        files = payload.get("files", []) if isinstance(payload, dict) else []
        out = [
            f
            for f in files
            if str(f).lower().endswith(".md") and not (IGNORED_DIRS & set(Path(f).parts))
        ]
        return sorted(out)


class FallbackTransport:
    """Try ``primary`` (REST) and fall back to ``fallback`` (file) on failure.

    Only *connection* errors trigger the fallback — an HTTP error from a
    reachable server (a real 4xx/5xx) is surfaced, so misconfiguration does not
    silently read stale files.
    """

    scheme = "rest+file"

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback

    def _call(self, name: str, *args):
        try:
            return getattr(self.primary, name)(*args)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            return getattr(self.fallback, name)(*args)

    def exists(self, rel: str) -> bool:
        return self._call("exists", rel)

    def read(self, rel: str) -> str:
        return self._call("read", rel)

    def write(self, rel: str, content: str) -> None:
        self._call("write", rel, content)

    def append(self, rel: str, content: str) -> None:
        self._call("append", rel, content)

    def delete(self, rel: str) -> None:
        self._call("delete", rel)

    def move(self, src: str, dst: str) -> None:
        self._call("move", src, dst)

    def list_markdown(self, folder: str = "") -> list[str]:
        return self._call("list_markdown", folder)


def make_transport(config) -> object:
    """Build the transport selected by ``config.obsidian_transport``.

    ``"file"`` (default) uses the filesystem; ``"rest"`` uses the Local REST
    API with a filesystem fallback when the server is unreachable.
    """
    root = Path(config.obsidian_vault)
    file_transport = FileTransport(root)

    if getattr(config, "obsidian_transport", "file") != "rest":
        return file_transport

    rest = RestTransport(
        getattr(config, "obsidian_api_url", "") or DEFAULT_API_URL,
        getattr(config, "obsidian_api_key", ""),
        verify=bool(getattr(config, "obsidian_api_verify", False)),
    )
    return FallbackTransport(rest, file_transport)
