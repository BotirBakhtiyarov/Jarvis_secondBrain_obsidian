"""Tests for the vault transports (file, REST and fallback)."""

import json
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from orion import obsidian_transport as ot
from orion.obsidian import Vault


class _StubHandler(BaseHTTPRequestHandler):
    """Minimal stand-in for the Obsidian Local REST API."""

    files: dict[str, str] = {}

    def log_message(self, *args):  # keep the test output quiet
        pass

    def _send(self, code: int, body: bytes = b"", ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _key(self) -> str:
        path = urllib.parse.unquote(self.path)
        return path[len("/vault/") :] if path.startswith("/vault/") else path.lstrip("/")

    def do_GET(self):
        key = self._key()
        if key == "" or key.endswith("/"):
            files = sorted(f for f in type(self).files if f.startswith(key))
            self._send(200, json.dumps({"files": files}).encode())
            return
        if key in type(self).files:
            self._send(200, type(self).files[key].encode("utf-8"), "text/markdown")
        else:
            self._send(404, b'{"message":"not found"}')

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        type(self).files[self._key()] = self.rfile.read(length).decode("utf-8")
        self._send(200, b'{"ok":true}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        key = self._key()
        type(self).files[key] = type(self).files.get(key, "") + body
        self._send(200, b'{"ok":true}')

    def do_DELETE(self):
        type(self).files.pop(self._key(), None)
        self._send(204)


@pytest.fixture
def rest_server():
    _StubHandler.files = {"Notes/Apollo.md": "Apollo project notes", "Inbox.md": "hi"}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base, _StubHandler.files
    server.shutdown()
    server.server_close()


def _closed_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


# --- FileTransport ---------------------------------------------------------


def test_file_transport_roundtrip(tmp_path):
    t = ot.FileTransport(tmp_path)
    assert t.exists("a.md") is False
    t.write("a.md", "hello")
    assert t.exists("a.md") is True
    assert t.read("a.md") == "hello"
    t.append("a.md", "\n\nmore")
    assert t.read("a.md").endswith("more")


def test_file_transport_move_and_delete(tmp_path):
    t = ot.FileTransport(tmp_path)
    t.write("a.md", "a")
    t.move("a.md", "dir/b.md")
    assert t.exists("dir/b.md") and not t.exists("a.md")
    t.delete("dir/b.md")
    assert t.exists("dir/b.md") is False


def test_file_transport_ignores_internal_dirs(tmp_path):
    t = ot.FileTransport(tmp_path)
    t.write("A.md", "a")
    t.write(".orion_index/secret.md", "x")
    t.write(".jarvis_backups/old.md", "y")
    assert t.list_markdown() == ["A.md"]


# --- RestTransport ---------------------------------------------------------


def test_rest_transport_read_write_append_delete(rest_server):
    base, files = rest_server
    t = ot.RestTransport(base)
    assert t.exists("Notes/Apollo.md") is True
    assert t.exists("missing.md") is False
    assert t.read("Notes/Apollo.md") == "Apollo project notes"

    t.write("Notes/New.md", "hello")
    assert files["Notes/New.md"] == "hello"
    t.append("Notes/New.md", "\n\nmore")
    assert files["Notes/New.md"].endswith("more")
    t.delete("Notes/New.md")
    assert "Notes/New.md" not in files


def test_rest_transport_list_markdown(rest_server):
    base, _ = rest_server
    t = ot.RestTransport(base)
    assert t.list_markdown() == ["Inbox.md", "Notes/Apollo.md"]
    assert t.list_markdown("Notes") == ["Notes/Apollo.md"]


def test_rest_transport_move(rest_server):
    base, files = rest_server
    t = ot.RestTransport(base)
    t.move("Inbox.md", "Archive/Inbox.md")
    assert files["Archive/Inbox.md"] == "hi"
    assert "Inbox.md" not in files


# --- FallbackTransport / factory ------------------------------------------


def test_fallback_transport_uses_file_on_connection_error(tmp_path):
    file_t = ot.FileTransport(tmp_path)
    file_t.write("a.md", "on disk")
    dead = ot.RestTransport(f"http://127.0.0.1:{_closed_port()}")
    t = ot.FallbackTransport(dead, file_t)
    assert t.read("a.md") == "on disk"
    assert t.list_markdown() == ["a.md"]


def test_fallback_transport_prefers_rest_when_reachable(rest_server, tmp_path):
    base, _ = rest_server
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "Apollo.md").write_text("stale disk copy", encoding="utf-8")
    t = ot.FallbackTransport(ot.RestTransport(base), ot.FileTransport(tmp_path))
    assert t.read("Notes/Apollo.md") == "Apollo project notes"


def test_make_transport_defaults_to_file(tmp_path):
    class Cfg:
        obsidian_vault = tmp_path

    assert ot.make_transport(Cfg()).scheme == "file"


def test_make_transport_rest_returns_fallback(tmp_path):
    class Cfg:
        obsidian_vault = tmp_path
        obsidian_transport = "rest"
        obsidian_api_url = "http://127.0.0.1:1"
        obsidian_api_key = "k"
        obsidian_api_verify = False

    transport = ot.make_transport(Cfg())
    assert isinstance(transport, ot.FallbackTransport)


# --- Vault on top of a REST transport -------------------------------------


def test_vault_crud_over_rest(rest_server):
    base, files = rest_server
    v = Vault("/tmp/orion-rest-vault", transport=ot.RestTransport(base))

    assert v.read("Notes/Apollo.md")["content"] == "Apollo project notes"
    assert v.create("Notes/New.md", "fresh")["success"] is True
    assert files["Notes/New.md"] == "fresh"
    assert v.create("Notes/New.md", "again")["success"] is False
    assert v.append("Notes/New.md", "plus")["success"] is True
    assert "plus" in files["Notes/New.md"]


def test_vault_search_over_rest(rest_server):
    base, _ = rest_server
    v = Vault("/tmp/orion-rest-vault", transport=ot.RestTransport(base))
    results = v.search("apollo")
    assert results and results[0]["path"] == "Notes/Apollo.md"
