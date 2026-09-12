"""Minimal Telegram bot front-end (long polling, no extra dependencies).

Start it with ``orion telegram`` (or ``orion --telegram``). It talks to the
Telegram Bot API over HTTPS using only the standard library, so enabling it
adds no dependency. Sensitive tools still ask for confirmation — the prompt is
sent to Telegram as an inline keyboard, and other updates received while we
wait are deferred instead of being dropped.

``TelegramFrontend`` takes an ``agent(chat_id, text) -> str`` callable, so it
stays decoupled from the CLI and is easy to test with a fake API.
"""

import json
import re
import time
import urllib.parse
import urllib.request

API_BASE = "https://api.telegram.org"
MAX_MESSAGE = 4096

HELP_TEXT = (
    "🤖 <b>ORION</b> is ready.\n\n"
    "Send a message to chat. Slash commands (e.g. <code>/help</code>) and "
    "<code>@file</code> mentions work as in the terminal.\n"
    "Sensitive commands ask for confirmation with buttons; type /start to see "
    "this again."
)

_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


class TelegramAPI:
    """Thin wrapper over the Telegram Bot API using stdlib HTTP."""

    def __init__(self, token: str, base_url: str = API_BASE, timeout: float = 40.0):
        self.token = token
        self.base_url = (base_url or API_BASE).rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, params: dict, timeout: float | None = None):
        url = f"{self.base_url}/bot{self.token}/{method}"
        encoded = {}
        for key, value in params.items():
            if value is None:
                continue
            encoded[key] = json.dumps(value) if isinstance(value, (dict, list)) else value
        data = urllib.parse.urlencode(encoded).encode()
        request = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(request, timeout=timeout or self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram API error"))
        return payload.get("result")

    def get_updates(self, offset=None, timeout: int = 30) -> list:
        return (
            self._call(
                "getUpdates",
                {"offset": offset, "timeout": timeout},
                timeout=timeout + 15,
            )
            or []
        )

    def send_message(
        self,
        chat_id,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict | None = None,
    ):
        return self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": reply_markup,
                "link_preview_options": {"is_disabled": True},
            },
        )

    def answer_callback_query(self, callback_query_id: str, text: str = ""):
        return self._call(
            "answerCallbackQuery",
            {"callback_query_id": callback_query_id, "text": text},
        )


# --- formatting helpers ----------------------------------------------------


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    text = escape_html(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)
    return text


def to_telegram_html(text: str) -> str:
    """Convert light Markdown to Telegram-safe HTML (fenced code + bold)."""
    out = []
    last = 0
    for match in _FENCE.finditer(text):
        out.append(_inline(text[last : match.start()]))
        out.append("<pre>" + escape_html(match.group(1)) + "</pre>")
        last = match.end()
    out.append(_inline(text[last:]))
    return "".join(out)


def split_message(text: str, limit: int = MAX_MESSAGE) -> list[str]:
    """Split text into Telegram-sized chunks, preferring line boundaries."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)
    return chunks


def parse_allowed_ids(raw) -> set[int]:
    """Parse ``TELEGRAM_ALLOWED_CHAT_IDS`` ("123, 456") into a set of ints."""
    if isinstance(raw, (set, list, tuple)):
        items = raw
    else:
        items = str(raw or "").replace(",", " ").split()
    out: set[int] = set()
    for item in items:
        try:
            out.add(int(item))
        except (TypeError, ValueError):
            continue
    return out


def permission_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Allow", "callback_data": "allow"},
                {"text": "🚫 Deny", "callback_data": "deny"},
                {"text": "♾ Always", "callback_data": "always"},
            ]
        ]
    }


# --- front-end -------------------------------------------------------------


class TelegramFrontend:
    """Poll updates and hand text messages to an ``agent(chat_id, text)``."""

    def __init__(self, api, agent=None, allowed_ids=None, sleep=time.sleep):
        self.api = api
        self.agent = agent
        self.allowed_ids = set(allowed_ids or [])
        self.sleep = sleep
        self._offset = None
        self._deferred: list = []

    def allowed(self, chat_id) -> bool:
        return not self.allowed_ids or chat_id in self.allowed_ids

    def _next_updates(self, timeout: int = 30) -> list:
        if self._deferred:
            updates, self._deferred = self._deferred, []
            return updates
        updates = self.api.get_updates(offset=self._offset, timeout=timeout)
        for update in updates:
            self._offset = update["update_id"] + 1
        return updates

    def confirm(self, chat_id, label: str, session) -> bool:
        """Ask for permission via an inline keyboard; block until answered."""
        self.api.send_message(
            chat_id,
            f"⚡ <b>Allow?</b>\n<code>{escape_html(label)}</code>",
            reply_markup=permission_keyboard(),
        )
        while True:
            for update in self._next_updates():
                callback = update.get("callback_query")
                if callback and callback["message"]["chat"]["id"] == chat_id:
                    self.api.answer_callback_query(callback["id"])
                    choice = callback.get("data", "")
                    if choice == "always":
                        session.bypass = True
                        return True
                    return choice == "allow"
                message = update.get("message")
                if message and message["chat"]["id"] == chat_id:
                    answer = (message.get("text") or "").strip().lower()
                    if answer in ("y", "yes", "ha", "allow"):
                        return True
                    if answer in ("n", "no", "deny", "yo'q"):
                        return False
                self._deferred.append(update)

    def handle_update(self, update):
        """Handle one update; returns the answer text for messages, else None."""
        callback = update.get("callback_query")
        if callback:
            self.api.answer_callback_query(callback["id"])
            return None

        message = update.get("message")
        if not message:
            return None
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if not text:
            return None

        if not self.allowed(chat_id):
            self.api.send_message(chat_id, "⛔ You are not authorised to use this bot.")
            return None

        if text in ("/start", "/help"):
            self.api.send_message(chat_id, HELP_TEXT)
            return None

        try:
            answer = (self.agent(chat_id, text) if self.agent else "") or ""
        except Exception as err:  # noqa: BLE001
            self.api.send_message(chat_id, f"❌ {escape_html(str(err))}")
            return None

        answer = answer.strip() or "…"
        for chunk in split_message(to_telegram_html(answer)):
            self.api.send_message(chat_id, chunk)
        return answer

    def run(self, max_polls=None) -> int:
        """Long-poll forever (or ``max_polls`` times, for tests)."""
        polls = 0
        while max_polls is None or polls < max_polls:
            for update in self._next_updates():
                self.handle_update(update)
            polls += 1
        return polls
