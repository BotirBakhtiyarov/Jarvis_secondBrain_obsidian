"""Tests for the Telegram front-end (formatting, API, dispatch)."""

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from orion import telegram

# --- formatting / helpers --------------------------------------------------


def test_to_telegram_html_escapes_and_formats():
    out = telegram.to_telegram_html("a < b & c **bold** `code`")
    assert "&lt;" in out and "&amp;" in out
    assert "<b>bold</b>" in out
    assert "<code>code</code>" in out
    assert "**bold**" not in out


def test_to_telegram_html_renders_code_block():
    out = telegram.to_telegram_html("```python\nx = 1 < 2\n```")
    assert "<pre>" in out
    assert "x = 1 &lt; 2" in out


def test_split_message_short_text_is_single_chunk():
    assert telegram.split_message("hello") == ["hello"]


def test_split_message_prefers_newlines_and_respects_limit():
    text = "\n".join(["a" * 30] * 10)
    chunks = telegram.split_message(text, limit=100)
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_parse_allowed_ids():
    assert telegram.parse_allowed_ids("1, 2 3") == {1, 2, 3}
    assert telegram.parse_allowed_ids("") == set()
    assert telegram.parse_allowed_ids("abc 5") == {5}


def test_permission_keyboard_shape():
    keyboard = telegram.permission_keyboard()
    buttons = keyboard["inline_keyboard"][0]
    assert {b["callback_data"] for b in buttons} == {"allow", "deny", "always"}


# --- TelegramAPI over a stub server ----------------------------------------


class _TgHandler(BaseHTTPRequestHandler):
    calls: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = urllib.parse.parse_qs(self.rfile.read(length).decode())
        type(self).calls.append((self.path, body))
        method = self.path.rsplit("/", 1)[-1]
        result = [{"update_id": 1}] if method == "getUpdates" else {"ok": True}
        payload = json.dumps({"ok": True, "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def tg_server():
    _TgHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TgHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", _TgHandler.calls
    server.shutdown()
    server.server_close()


def test_telegram_api_hits_correct_endpoints(tg_server):
    base, calls = tg_server
    api = telegram.TelegramAPI("TOKEN", base_url=base)

    assert api.get_updates(offset=None, timeout=0) == [{"update_id": 1}]
    api.send_message(5, "hello", reply_markup=telegram.permission_keyboard())
    api.answer_callback_query("cb1", "done")

    paths = [path for path, _ in calls]
    assert any(path.endswith("/botTOKEN/getUpdates") for path in paths)
    assert any(path.endswith("/botTOKEN/sendMessage") for path in paths)

    send = next(body for path, body in calls if path.endswith("sendMessage"))
    assert send["chat_id"] == ["5"] and send["text"] == ["hello"]
    assert json.loads(send["reply_markup"][0])["inline_keyboard"]


# --- TelegramFrontend ------------------------------------------------------


class FakeAPI:
    def __init__(self, updates=None):
        self.sent: list[tuple] = []
        self.answered: list[str] = []
        self._updates = list(updates or [])

    def send_message(self, chat_id, text, parse_mode="HTML", reply_markup=None):
        self.sent.append((chat_id, text))
        return {"message_id": len(self.sent)}

    def answer_callback_query(self, callback_query_id, text=""):
        self.answered.append(callback_query_id)
        return {"ok": True}

    def get_updates(self, offset=None, timeout=30):
        updates, self._updates = self._updates, []
        return updates


def _callback(update_id, chat_id, data, cid="cb"):
    return {
        "update_id": update_id,
        "callback_query": {"id": cid, "data": data, "message": {"chat": {"id": chat_id}}},
    }


def test_handle_update_calls_agent_and_replies():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api, agent=lambda chat, text: "**hi** there")
    answer = frontend.handle_update(
        {"update_id": 1, "message": {"chat": {"id": 7}, "text": "hello"}}
    )
    assert answer == "**hi** there"
    assert api.sent[0][0] == 7
    assert "<b>hi</b>" in api.sent[0][1]


def test_handle_update_rejects_unknown_chat():
    api = FakeAPI()
    seen: list[str] = []
    frontend = telegram.TelegramFrontend(
        api, agent=lambda chat, text: seen.append(text) or "x", allowed_ids=[1]
    )
    frontend.handle_update({"update_id": 1, "message": {"chat": {"id": 2}, "text": "hi"}})
    assert seen == []
    assert "not authorised" in api.sent[0][1]


def test_handle_update_start_sends_help():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api, agent=lambda chat, text: "nope")
    frontend.handle_update({"update_id": 1, "message": {"chat": {"id": 1}, "text": "/start"}})
    assert "ORION" in api.sent[0][1]


def test_handle_update_reports_agent_errors():
    api = FakeAPI()

    def boom(chat, text):
        raise RuntimeError("kaboom")

    frontend = telegram.TelegramFrontend(api, agent=boom)
    frontend.handle_update({"update_id": 1, "message": {"chat": {"id": 1}, "text": "hi"}})
    assert "kaboom" in api.sent[0][1]


def test_handle_update_splits_long_answers():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api, agent=lambda chat, text: "x" * 5000)
    frontend.handle_update({"update_id": 1, "message": {"chat": {"id": 1}, "text": "hi"}})
    assert len(api.sent) >= 2


def test_handle_update_callback_is_acknowledged():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api, agent=lambda chat, text: "x")
    assert frontend.handle_update(_callback(1, 5, "allow")) is None
    assert api.answered == ["cb"]


def test_confirm_allow_via_callback():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api)
    frontend._deferred = [_callback(1, 5, "allow")]
    assert frontend.confirm(5, "run_command: ls", SimpleNamespace(bypass=False)) is True
    assert api.answered == ["cb"]


def test_confirm_deny_via_callback():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api)
    frontend._deferred = [_callback(1, 5, "deny")]
    assert frontend.confirm(5, "x", SimpleNamespace(bypass=False)) is False


def test_confirm_always_sets_bypass():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api)
    frontend._deferred = [_callback(1, 5, "always")]
    session = SimpleNamespace(bypass=False)
    assert frontend.confirm(5, "x", session) is True
    assert session.bypass is True


def test_confirm_accepts_text_yes():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api)
    frontend._deferred = [{"update_id": 1, "message": {"chat": {"id": 5}, "text": "yes"}}]
    assert frontend.confirm(5, "x", SimpleNamespace(bypass=False)) is True


def test_confirm_defers_updates_for_other_chats():
    api = FakeAPI()
    frontend = telegram.TelegramFrontend(api)
    other = {"update_id": 1, "message": {"chat": {"id": 99}, "text": "hi"}}
    frontend._deferred = [other, _callback(2, 5, "deny")]
    assert frontend.confirm(5, "x", SimpleNamespace(bypass=False)) is False
    assert other in frontend._deferred


def test_run_processes_updates():
    api = FakeAPI(updates=[{"update_id": 1, "message": {"chat": {"id": 1}, "text": "hi"}}])
    frontend = telegram.TelegramFrontend(api, agent=lambda chat, text: "ok")
    assert frontend.run(max_polls=1) == 1
    assert api.sent
