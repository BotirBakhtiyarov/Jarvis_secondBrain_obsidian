"""Lightweight i18n for ORION's user-facing strings.

Default interface language is **English**. Set ``ORION_LANG`` (e.g. ``uv run
orion`` reads ``.env`` → ``ORION_LANG=uz``) to switch to another language, or
use ``ORION_LANG=auto`` to pick the language from the user's latest message
(``detect_language`` heuristic).

Only CLI-facing strings are translated. Tool descriptions and the system prompt
stay in English on purpose — models work better with a single, well-written
English schema, and ORION is instructed to *reply* in whatever language the
user writes in.
"""

import re

DEFAULT_LANGUAGE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "language": "Language",
        "status_title": "Status",
        "thinking": "Thinking…",
        "user_title": "You",
        "allow": "⚡ Allow?",
        "confirm_hint": "(y/n/always)",
        "denied": "User denied permission",
        "error_prefix": "❌ Error: {msg}",
        "interrupted": "(interrupted)",
        "goodbye": "ORION: Goodbye! 👋",
        "version": "orion {version}",
        "banner_line": "Model {model} · Workspace {workspace}",
        "banner_hint": "Type /help for commands · @file to include a file",
        "permission_mode": "Permission mode",
        "perm_bypass": "bypass (skip prompts)",
        "perm_ask": "ask for commands",
        "help_title": "Slash commands",
        "help.help": "show this help",
        "help.clear": "clear the conversation context",
        "help.model": "show or switch the model",
        "help.cost": "show tokens and cost",
        "help.status": "show current configuration",
        "help.memory": "recent notes in Obsidian memory",
        "help.compact": "summarize the chat to save context",
        "help.add_dir": "change the workspace folder",
        "help.review": "git status/diff in the workspace",
        "help.init": "create the ORION.md instructions file",
        "help.config": "view or edit configuration",
        "help.permissions": "view/change permission mode",
        "help.resume": "list or resume saved sessions",
        "help.tools": "list all tools with descriptions",
        "help.exit": "exit",
        "help.version": "show version",
        "help.hint": "@file — include a file's content. ↑/↓ — history.",
        "clear_done": "✓ Context cleared.",
        "model_is": "Model: {model}",
        "model_set": "✓ Model: {model}",
        "models_available": "Available: deepseek-chat, deepseek-reasoner",
        "tokens_line": "Tokens: in {i} · out {o} · total {t}",
        "cost_line": "Cost: ${c}",
        "cost_rates": "(in ${i}/M · out ${o}/M)",
        "recent_notes": "Recent notes ({n} total):",
        "memory_rules": (
            "Memory rules: important facts are saved via save_memory; plain chat is not saved."
        ),
        "nothing_to_compact": "Nothing to compact.",
        "compacting": "Compacting…",
        "compacted": "✓ Compacted.",
        "usage_add_dir": "Usage: /add-dir <path>",
        "not_a_directory": "Not a directory: {path}",
        "workspace_set": "✓ Workspace: {path}",
        "not_git_repo": "Not a git repository: {path}",
        "git_status": "git status:",
        "git_clean": "(clean)",
        "git_diff_stat": "git diff --stat:",
        "no_changes": "(no changes)",
        "already_exists": "Already exists: {path}",
        "created": "✓ Created {path}",
        "no_saved_sessions": "No saved sessions.",
        "session_not_found": "Session not found.",
        "resumed": "✓ Resumed.",
        "saved_sessions": "Saved sessions:",
        "resume_hint": "Resume: /resume <id>",
        "available_tools": "Available tools",
        "config_title": "Configuration",
        "env_exists": ".env already exists: {path}",
        "no_env_example": "No .env.example found to copy from.",
        "created_from": "✓ Created {path} (from {name})",
        "fill_env": "Fill in DEEPSEEK_API_KEY and OBSIDIAN_VAULT.",
        "env_not_found": ".env not found. Run: orion config --init",
        "opening_env": "Opening {path} with {editor}…",
        "vault_not_set": "OBSIDIAN_VAULT is not set yet — run: orion config --init",
        "unknown_command": "Unknown command: /{name}. Type /help",
        "no_previous": "No previous session — starting fresh.",
        "session_not_found_id": "Session '{id}' not found.",
        "session_summary_saved": "🧠 Session summary → {path}",
        "cost_summary": "Tokens: {t} · Cost: ${c}",
        "thinking_done": "Thinking ({n} chars) — /think to view",
        "more_lines": "… {n} more lines — /show to expand",
        "nothing_to_show": "Nothing collapsed yet.",
        "thinking_title": "Thinking",
        "help.show": "expand the last collapsed output (/show)",
        "help.think": "show the model's last reasoning (/think)",
    },
    "uz": {
        "language": "Til",
        "status_title": "Holat",
        "thinking": "O'ylamoqda…",
        "user_title": "Siz",
        "allow": "⚡ Ruxsat berasizmi?",
        "confirm_hint": "(ha/yo'q/doim)",
        "denied": "Foydalanuvchi ruxsat bermadi",
        "error_prefix": "❌ Xato: {msg}",
        "interrupted": "(to'xtatildi)",
        "goodbye": "ORION: Xayr! 👋",
        "version": "orion {version}",
        "banner_line": "Model {model} · Workspace {workspace}",
        "banner_hint": "Yordam uchun /help · fayl qo'shish uchun @file",
        "permission_mode": "Ruxsat rejimi",
        "perm_bypass": "bypass (so'rovlarni o'tkazib yuborish)",
        "perm_ask": "buyruqlar uchun so'rash",
        "help_title": "Slash buyruqlar",
        "help.help": "yordamni ko'rsatish",
        "help.clear": "suhbat kontekstini tozalash",
        "help.model": "modelni ko'rsatish yoki almashtirish",
        "help.cost": "token va xarajatni ko'rsatish",
        "help.status": "joriy konfiguratsiyani ko'rsatish",
        "help.memory": "Obsidian xotirasidagi so'nggi notalar",
        "help.compact": "suhbatni qisqartirib kontekstni tejash",
        "help.add_dir": "workspace papkasini almashtirish",
        "help.review": "workspace'dagi git status/diff",
        "help.init": "ORION.md ko'rsatmalar faylini yaratish",
        "help.config": "konfiguratsiyani ko'rish yoki sozlash",
        "help.permissions": "ruxsat rejimini ko'rish/o'zgartirish",
        "help.resume": "sessiyalarni ko'rish yoki davom ettirish",
        "help.tools": "mavjud tool'larni tavsifi bilan ko'rsatish",
        "help.exit": "chiqish",
        "help.version": "versiyani ko'rsatish",
        "help.hint": "@file — fayl kontentini so'rovga qo'shish. ↑/↓ — tarix.",
        "clear_done": "✓ Kontekst tozalandi.",
        "model_is": "Model: {model}",
        "model_set": "✓ Model: {model}",
        "models_available": "Mavjud: deepseek-chat, deepseek-reasoner",
        "tokens_line": "Tokenlar: kirish {i} · chiqish {o} · jami {t}",
        "cost_line": "Xarajat: ${c}",
        "cost_rates": "(kirish ${i}/M · chiqish ${o}/M)",
        "recent_notes": "So'nggi notalar ({n} ta):",
        "memory_rules": (
            "Xotira qoidalari: muhim ma'lumot save_memory orqali saqlanadi; oddiy chat saqlanmaydi."
        ),
        "nothing_to_compact": "Qisqartiradigan narsa yo'q.",
        "compacting": "Qisqartirilmoqda…",
        "compacted": "✓ Qisqartirildi.",
        "usage_add_dir": "Ishlatilishi: /add-dir <path>",
        "not_a_directory": "Papka emas: {path}",
        "workspace_set": "✓ Workspace: {path}",
        "not_git_repo": "Git repozitoriy emas: {path}",
        "git_status": "git status:",
        "git_clean": "(toza)",
        "git_diff_stat": "git diff --stat:",
        "no_changes": "(o'zgarishlar yo'q)",
        "already_exists": "Mavjud: {path}",
        "created": "✓ Yaratildi {path}",
        "no_saved_sessions": "Saqlangan sessiyalar yo'q.",
        "session_not_found": "Sessiya topilmadi.",
        "resumed": "✓ Davom ettirildi.",
        "saved_sessions": "Saqlangan sessiyalar:",
        "resume_hint": "Davom ettirish: /resume <id>",
        "available_tools": "Mavjud tool'lar",
        "config_title": "Konfiguratsiya",
        "env_exists": ".env allaqachon mavjud: {path}",
        "no_env_example": ".env.example topilmadi.",
        "created_from": "✓ Yaratildi {path} ({name} dan)",
        "fill_env": "DEEPSEEK_API_KEY va OBSIDIAN_VAULT ni to'ldiring.",
        "env_not_found": ".env topilmadi. Ishlating: orion config --init",
        "opening_env": "{path} {editor} bilan ochilmoqda…",
        "vault_not_set": "OBSIDIAN_VAULT hali o'rnatilmagan — ishlating: orion config --init",
        "unknown_command": "Noma'lum buyruq: /{name}. /help yozing",
        "no_previous": "Oldingi sessiya yo'q — yangidan boshlanmoqda.",
        "session_not_found_id": "Sessiya '{id}' topilmadi.",
        "session_summary_saved": "🧠 Sessiya xulosasi → {path}",
        "cost_summary": "Tokenlar: {t} · Xarajat: ${c}",
        "thinking_done": "O'ylash ({n} belgi) — /think bilan ko'rish",
        "more_lines": "… yana {n} qator — /show bilan ochish",
        "nothing_to_show": "Hali yig'ilgan chiqish yo'q.",
        "thinking_title": "O'ylash",
        "help.show": "oxirgi yig'ilgan chiqishni ochish (/show)",
        "help.think": "modelning oxirgi mulohazalarini ko'rish (/think)",
    },
}

RUSSIAN_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
# Uzbek uses the Latin apostrophe inside words: o', g', O', G'
UZBEK_APOSTROPHE = re.compile(r"""(?i)(?:^|[\s"'(])([oOgG])\s*['ʻ\u2018\u2019]\s*[a-z]""")
# A few unmistakably-Uzbek words that almost never appear in English text.
UZBEK_WORDS = re.compile(r"(?i)\b(mana|shunday|bilan|uchun|emas|qilib|yozing|sizning|buni|meni)\b")


def languages() -> list[str]:
    """Return the list of supported interface language codes."""
    return list(TRANSLATIONS)


def set_language(lang: str) -> str:
    """Switch the interface language; unknown codes fall back to English.

    Returns the effective language code.
    """
    global _current
    _current = lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE
    return _current


def get_language() -> str:
    return _current


def t(key: str, **fmt) -> str:
    """Translate a key using the current language, falling back to English.

    Unknown keys render as their key name, so a missing translation fails
    loudly instead of silently hiding.
    """
    table = TRANSLATIONS.get(_current) or TRANSLATIONS[DEFAULT_LANGUAGE]
    text = table.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    if fmt:
        return text.format(**fmt)
    return text


def detect_language(text: str) -> str | None:
    """Guess the language of a user message: ``'uz'``, ``'ru'`` or ``'en'``.

    Heuristic — designed to be *safe* (never misclassifying English as Uzbek
    if avoidable) rather than perfect. Uzbek and Russian are only detected on
    strong signals (Cyrillic for Russian, ``o'``/``g'`` apostrophes or common
    Uzbek particles for Uzbek).
    """
    if not text or not text.strip():
        return None

    if RUSSIAN_CYRILLIC.search(text):
        return "ru"
    if UZBEK_APOSTROPHE.search(text) or UZBEK_WORDS.search(text):
        return "uz"
    return "en"


_current = DEFAULT_LANGUAGE
