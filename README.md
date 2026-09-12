# ORION

**Operational Reasoning, Intelligence & Orchestration Network** — a terminal AI assistant that gives DeepSeek a long-term memory in Obsidian and hands to work in your code projects.

[![CI](https://github.com/BotirBakhtiyarov/orion-second-brain/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BotirBakhtiyarov/orion-second-brain/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.12.0-blue)](https://github.com/BotirBakhtiyarov/orion-second-brain/releases)

## What is ORION?

ORION is a personal AI assistant that lives in your terminal and works with two
worlds at once:

- **An Obsidian vault** — your long-term memory and knowledge base. ORION
  decides on its own which parts of a conversation are worth keeping, writes
  them as Markdown notes, links related notes together, and keeps the vault
  organized.
- **A workspace** — the folder with your code and files. ORION can read, edit,
  run and improve your projects, with a permission prompt before anything
  sensitive happens.

Unlike a plain chat window, ORION remembers across sessions, is honest about
what it does, and can actually take action on your machine.

## Who is it for?

- **Developers who live in the terminal.** You want an agent that reads, edits
  and runs your project — with a permission prompt before anything sensitive —
  rather than another browser tab.
- **Obsidian users who want the second brain to fill itself.** ORION turns
  conversations into linked Markdown notes, so your vault grows while you work.
- **People who care about local, plain-text data.** Memory is Markdown in a
  vault *you* own: no proprietary store, no vendor lock-in, diffable with git.
- **Anyone who does not want to be locked to one model.** DeepSeek by default;
  Anthropic, OpenAI, Gemini or a local Ollama model on request.
- **Contributors.** Small, readable Python, a documented layout, and a
  [good first issues](docs/good-first-issues.md) list of beginner-friendly
  tasks.

**Probably not for you if** you want a GUI app, a hosted service, or an agent
that acts on your machine without asking. ORION is deliberately a permissioned
terminal tool.

## Features

- **Smart memory** — ORION autonomously decides what to persist to Obsidian and
  what to skip, via the `save_memory` tool and explicit rules in the system
  prompt.
- **Agent mode** — for multi-step tasks ORION records a plan (the `plan` tool),
  executes steps one by one, and shows progress in the terminal.
  Start a goal with `/goal <description>` and ORION seeds a plan and works
  toward it; use `/plan` to inspect or advance steps manually.
- **Multi‑language** — English interface by default; switch to Uzbek, Russian
  or Turkish with `ORION_LANG`, or use `ORION_LANG=auto` and ORION follows the
  language you write in. The assistant always replies in your language.
- **Terminal UI** — you type directly inside a green input box, answers stream
  as rendered Markdown (no raw `##`/`**` noise), and model thinking plus long
  tool output collapse to one-line summaries you can expand with `/think` and
  `/show` (see [docs/terminal-ui.md](docs/terminal-ui.md)).
- **Multi-provider** — DeepSeek, Anthropic Claude, OpenAI, Google Gemini and
  local Ollama behind one OpenAI-compatible interface; switch live with
  `/model <provider>:<model>`, with per-provider cost defaults.
- **Context management** — long chats are automatically trimmed to
  `ORION_MAX_HISTORY` messages (default 50) so you stay inside the model's
  context window without losing recent decisions.
- **Obsidian toolkit** — search, read, create, update, append, list, two-way
  backlinks, pretty notes (YAML frontmatter + `[[wikilinks]]`), daily notes and
  Inbox triage.
- **Project work** — `list_files`, `read_file`, `write_file`, `edit_file`,
  `run_command` inside a sandboxed workspace (path-traversal protected).
- **Git integration** — `git_status`, `git_diff` (with colorized output),
  `git_log`, `git_commit`, `git_create_pr`.
- **Web search** — `web_search` via Tavily (set `TAVILY_API_KEY`) or a
  key-less DuckDuckGo fallback.
- **System tools** — open URLs/apps, notifications, clipboard, screenshots,
  current time.
- **MCP support** — connect any [Model Context Protocol](https://modelcontextprotocol.io)
  server (Gmail, Slack, fetch, time, …). Servers are closed cleanly on exit.
- **Semantic search (optional)** — vector search with `fastembed`, blended with
  keyword search. The model is only downloaded during an explicit `reindex` —
  search never hangs on a hidden download.
- **Streaming responses**, token/cost tracking, session persistence
  (`orion -c` to resume), and automatic backups on note updates.
- **Auto-memory** — on exit ORION can summarize the session and extract
  important facts into Obsidian.

## Why not just use Claude Code (or another agent)?

Claude Code, Cursor and friends are excellent coding agents — ORION is not
trying to replace them. It aims at a slightly different job: a **personal
second brain with an agent attached**, on whichever model you choose, reachable
from wherever you already work.

| | ORION | Typical coding agents |
|---|---|---|
| Long-term memory | An Obsidian vault: linked Markdown notes, frontmatter, backlinks, daily notes | Project-scoped memory / context files |
| Model | DeepSeek by default; Anthropic, OpenAI, Gemini or local Ollama | Usually a single vendor |
| Reach | Terminal, Telegram bot, and `orion schedule` background jobs | Terminal and/or IDE plugin |
| Interface language | English, Uzbek, Russian, Turkish | Usually English only |
| Your data | Plain Markdown in a vault you own | Vendor-hosted context |
| Scope | Code **and** notes, tasks, research | Mostly code |

**Where the others win:** IDE integration (inline diffs, editor context),
ecosystem size, and model quality. ORION speaks MCP too, but its tool set is
much smaller, and it delegates model quality to whichever provider you pick
with `/model`.

Pick ORION if you want your assistant's memory to be a vault of Markdown you
own, running on whichever model you like — and you enjoy small, hackable tools.

## Multi-language

ORION's interface is **English by default** and can be switched in two ways:

```bash
ORION_LANG=en    # English (default)
ORION_LANG=uz    # Uzbek UI (menus, help, prompts)
ORION_LANG=ru    # Russian UI
ORION_LANG=tr    # Turkish UI
ORION_LANG=auto  # follow the language you write in
```

- **`auto` mode** detects the language of each message you send (English,
  Uzbek, Russian or Turkish) and switches the UI to match.
- **Replies always follow you**: the system prompt instructs the model to
  answer in the language you write in, regardless of the interface language —
  so you can keep a Uzbek UI while the assistant answers in English, or vice
  versa.
- Adding a new language means adding one dictionary to `orion/i18n.py` and
  opening a PR. Tool descriptions and the system prompt intentionally stay in
  English — models produce more reliable tool calls against a single, crisp
  schema.

## Demo

### Workflow

![ORION's workflow: a question, tool calls, and a note saved to the vault](img/demo.gif)

_A rendered preview of the terminal UI, generated by
[`scripts/make-demo-gif.py`](scripts/make-demo-gif.py) from
[`docs/demo-transcript.txt`](docs/demo-transcript.txt), so it can be
regenerated offline. Prefer a real recording? See
[good first issue #7](docs/good-first-issues.md)._

### Terminal

![ORION running in the terminal](img/demo.png)

### Second brain in Obsidian

![ORION's notes organized in an Obsidian vault](img/obsidian.png)

ORION runs entirely in the terminal. On startup it prints this banner:

```text
  ___  ____  ___ ___  _   _
 / _ \|  _ \|_ _/ _ \| \ | |
| | | | |_) || | | | |  \| |
| |_| |  _ < | | |_| | |\  |
 \___/|_| \_\___\___/|_| \_|
```

You type directly inside a green input box; the answer streams below it as
rendered Markdown. Model thinking and long tool output collapse to one-line
summaries — expand them any time with `/think` and `/show`
(see [docs/terminal-ui.md](docs/terminal-ui.md)).

## Quick Start

```bash
# 1. Clone
git clone https://github.com/BotirBakhtiyarov/orion-second-brain.git
cd orion-second-brain

# 2. Install (uv recommended)
uv sync                      # pip: pip install -e ".[dev]"

# 3. Configure
cp .env.example .env         # then fill in DEEPSEEK_API_KEY + OBSIDIAN_VAULT

# 4. Run
uv run orion
```

If you don't use `uv`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # add extras: `[mcp]` and/or `[semantic]`
orion
```

### Install as a standalone tool

You don't have to clone the repo — install the `orion` command straight from
Git (requires Python ≥ 3.11):

```bash
# with uv (recommended)
uv tool install "orion-second-brain[mcp,semantic] @ git+https://github.com/BotirBakhtiyarov/orion-second-brain"

# or with pipx
pipx install "orion-second-brain[mcp,semantic] @ git+https://github.com/BotirBakhtiyarov/orion-second-brain"
```

Drop `[mcp,semantic]` if you don't want those optional features. Either way you
get an `orion` command on your `PATH`; run `orion config --init` once to create
`.env`, then `orion`. Upgrade later with `uv tool upgrade orion-second-brain`
(or `pipx upgrade orion-second-brain`).

You do **not** need a real API key to develop ORION itself — the test suite
never touches the network (except one explicitly `network`-marked test).

## Configuration

All configuration comes from `.env` (project-local) or `~/.orion/.env`
(global). Project values win; the global file fills in gaps.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ORION_PROVIDER` | no | `deepseek` | `deepseek` \| `anthropic` \| `openai` \| `gemini` \| `ollama` |
| `DEEPSEEK_API_KEY` | provider | — | DeepSeek API key |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | provider | — | Key for the matching provider |
| `OLLAMA_API_KEY` | no | `ollama` | Any value; a local Ollama server needs no real key |
| `ORION_MODEL` / `ORION_BASE_URL` | no | provider default | Model / base URL override for any provider |
| `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL` | no | — | Legacy overrides (deepseek only) |
| `OBSIDIAN_VAULT` | **yes** | — | Path to your Obsidian vault |
| `OBSIDIAN_TRANSPORT` | no | `file` | `file` (direct disk) \| `rest` (Local REST API, with file fallback) |
| `OBSIDIAN_API_URL` | no | `https://127.0.0.1:27124` | Local REST API base URL |
| `OBSIDIAN_API_KEY` | for `rest` | — | API key from the Local REST API plugin |
| `OBSIDIAN_API_VERIFY` | no | `0` | Verify the plugin's TLS certificate (`1` = verify) |
| `TELEGRAM_BOT_TOKEN` | for `telegram` | — | Bot token from @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | no | — | Comma-separated chat IDs allowed to use the bot |
| `WORKSPACE` | no | current directory | Root for file operations |
| `ORION_LANG` | no | `en` | Interface language: `en`, `uz`, `ru`, `tr` or `auto` |
| `ORION_COLLAPSE` | no | `1` | `1` = collapse long output/thinking (`/show`, `/think` to expand); `0` = show everything |
| `TAVILY_API_KEY` | no | — | Enables Tavily web search; empty → DuckDuckGo |
| `ORION_HISTORY` | no | `~/.orion/history.json` | Session history location |
| `ORION_MAX_HISTORY` | no | `50` | Max messages kept in context (auto-trim) |
| `ORION_INPUT_PRICE` / `ORION_OUTPUT_PRICE` | no | provider default | USD per 1M tokens (cost estimate) |
| `DEEPSEEK_INPUT_PRICE` / `DEEPSEEK_OUTPUT_PRICE` | no | `0.27` / `1.10` | Legacy price overrides (deepseek only) |

## Providers

ORION talks to every provider through one OpenAI-compatible client: DeepSeek
natively, Anthropic and Google Gemini through their official OpenAI
compatibility layers, and Ollama through its built-in `/v1` server — no extra
SDKs are installed.

Pick the provider in `.env`:

```bash
ORION_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

| Provider | Default model | Cost defaults ($/M in/out) |
|---|---|---|
| `deepseek` | `deepseek-chat` | 0.27 / 1.10 |
| `anthropic` | `claude-sonnet-4-5` | 3.00 / 15.00 |
| `openai` | `gpt-4o-mini` | 0.15 / 0.60 |
| `gemini` | `gemini-2.0-flash` | 0.10 / 0.40 |
| `ollama` | `llama3.2` | 0 / 0 (local) |

Switch live with `/model`:

```text
/model                     # providers table + current model
/model deepseek-reasoner   # switch model on the current provider
/model openai:gpt-4o-mini  # switch provider and model (key must be set)
```

Cost defaults are approximate and change over time — override them with
`ORION_INPUT_PRICE` / `ORION_OUTPUT_PRICE` in `.env`.

## Obsidian transport

By default ORION reads and writes your vault directly on disk. To route reads
and writes through Obsidian's *Local REST API* plugin instead (useful while
Obsidian is open), install the plugin and set:

```bash
OBSIDIAN_TRANSPORT=rest
OBSIDIAN_API_URL=https://127.0.0.1:27124
OBSIDIAN_API_KEY=<key from the plugin settings>
```

If the plugin's server is unreachable, ORION transparently falls back to direct
disk access for that operation — a stopped Obsidian never blocks you.

## Usage

### CLI

```bash
orion                                        # interactive session
orion -p "summarize this repo"               # one-shot, prints the answer
orion -c                                     # continue the most recent session
orion -r <id>                                # resume a session by ID
orion --workspace /path/to/projects          # point at a different workspace
orion config --init                          # create .env from .env.example
orion config edit                            # open .env in $EDITOR
orion config                                 # show current configuration
orion schedule                               # list scheduled vault tasks
orion telegram                               # run as a Telegram bot
orion --telegram                             # same, as a flag
orion -v                                     # version
```

### Scheduled tasks

ORION has a tiny built-in scheduler for recurring vault chores. There is no
OS-level daemon — jobs only run while you ask them to (or while `--loop` is up):

```bash
orion schedule tasks                          # list available tasks
orion schedule add morning daily_note 08:00   # add/replace a job
orion schedule run                            # run whatever is due right now
orion schedule run --loop                     # keep checking (Ctrl+C to stop)
orion schedule remove morning                 # delete a job
```

Jobs live in `~/.orion/schedule.json`. Built-in tasks are deterministic vault
operations (no model calls, no API key): `daily_note` creates today's note,
`vault_tidy` reports Inbox leftovers.

### Telegram bot

Chat with ORION from your phone. Create a bot with
[@BotFather](https://t.me/BotFather), then set:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC...        # from @BotFather
TELEGRAM_ALLOWED_CHAT_IDS=123456789     # only these chats may use the bot
```

```bash
orion telegram        # or: orion --telegram
```

It long-polls the Telegram Bot API (no extra dependency, no public URL needed).
Sensitive tools still ask for confirmation — the prompt arrives as an inline
keyboard (Allow / Deny / Always). Lock the bot to your own chat with
`TELEGRAM_ALLOWED_CHAT_IDS`; without it, anyone who finds the bot can use it.

### In-session slash commands

| Command | What it does |
|---|---|
| `/help` | Show this help |
| `/clear` | Clear the conversation context |
| `/model [name\|provider:name]` | Show providers; switch model or provider live |
| `/cost` | Show tokens and cost so far |
| `/status` | Show current configuration (incl. language) |
| `/memory` | Recent notes in Obsidian |
| `/compact` | Summarize the chat to save context |
| `/add-dir <path>` | Change the workspace folder |
| `/review` | Git status/diff in the workspace |
| `/init` | Create an `ORION.md` instructions file |
| `/permissions [on\|bypass]` | Change the permission mode |
| `/resume [id]` | List or resume saved sessions |
| `/tools` | List every available tool with a description |
| `/show` | Expand the last collapsed output (command output, search results…) |
| `/think` | Show the model's last reasoning in full |
| `/exit` | Quit (also `q`, `quit`) |

Tips: `@file` anywhere in your prompt includes that file's content from the
workspace; `@` with autocomplete lists files.

## Repository layout

```text
orion/
├── main.py          # CLI, session loop, slash commands
├── config.py        # .env-driven configuration
├── providers.py     # Model providers (DeepSeek/Claude/OpenAI/Gemini/Ollama)
├── tools.py         # Tool base class + ToolRegistry
├── prompts.py       # System prompt (memory / coding / agent rules)
├── i18n.py          # Multi-language UI strings (English default, auto-detect)
├── memory.py        # Session save / resume / list
├── obsidian.py      # Vault: notes, search, frontmatter, backlinks
├── obsidian_transport.py  # Vault transports: file | Local REST API (+fallback)
├── workspace.py     # Workspace: sandboxed file operations
├── semantic.py      # Optional vector search (fastembed)
├── mcp.py           # MCP client manager (clean shutdown)
├── scheduler.py     # Local scheduler for recurring vault tasks
├── telegram.py      # Telegram bot front-end (long polling)
├── ui.py            # Rich rendering helpers + user-message box
├── agent.py         # Plan, PlanTool + SubAgent (agent mode)
└── plugins/         # Auto-loaded tools
    ├── obsidian_plugin.py
    ├── memory_plugin.py
    ├── code_plugin.py
    ├── git_plugin.py
    ├── web_plugin.py
    ├── system_plugin.py
    ├── subagent_plugin.py
    ├── knowledge_plugin.py
    └── mcp_plugin.py
├── tests/           # pytest suite
├── docs/            # additional documentation
├── scripts/         # dev utilities (demo GIF, label sync)
├── img/             # README assets (screenshots, demo.gif)
├── .github/         # CI, release automation, issue templates, labels.yml
├── pyproject.toml   # project + tooling config
├── .env.example     # configuration template
└── README.md
```

## MCP support

ORION speaks the Model Context Protocol, so it can use the same servers as
Claude Code. Install the extra and create `~/.orion/mcp.json`:

```bash
pip install -e ".[mcp]"   # or: uv sync (mcp is in the default groups)
```

```json
{
  "mcpServers": {
    "time": { "command": "uvx", "args": ["mcp-server-time"] },
    "fetch": { "command": "uvx", "args": ["mcp-server-fetch"] }
  }
}
```

Each MCP tool appears as `mcp__<server>__<tool>`. If `mcp` is not installed or
the config is missing, ORION runs normally without it. On exit, all servers are
shut down cleanly.

## Testing

```bash
uv run pytest            # everything (the network test self-skips if offline)
uv run pytest -m "not network"   # skip tests that download models
uv run ruff check .      # lint
uv run ruff format --check .     # formatting
```

Some tests need the optional extras: `tests/test_mcp.py` requires `mcp`, and
`tests/test_semantic.py` requires `fastembed` (both skip automatically when the
extra is missing).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
setup, coding conventions and the pull request process. All participants are
expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

New here? Browse the
[`good first issue`](https://github.com/BotirBakhtiyarov/orion-second-brain/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
and
[`help wanted`](https://github.com/BotirBakhtiyarov/orion-second-brain/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
labels, or the curated [task list](docs/good-first-issues.md) — every task
lists its difficulty, the steps, and the files involved.

## License

This project is licensed under the [MIT License](LICENSE).

## Roadmap

Shipped since v0.11 — see the [changelog](#changelog) below:

- ✅ Obsidian Local REST API transport (`OBSIDIAN_TRANSPORT=rest`).
- ✅ Autonomous background tasks (`orion schedule`).
- ✅ Telegram bot mode (`orion telegram`).
- ✅ RAG over code and notes together (`search_knowledge`).
- ✅ Russian and Turkish, in addition to English and Uzbek.

Still open:

- A web UI / graph view over the vault.
- Discord bot mode.
- An `orion doctor` command (tracked as a
  [good first issue](docs/good-first-issues.md)).
- More interface languages in `orion/i18n.py`.

## Changelog

### v0.12.0 — 2026-09-12

- **Obsidian Local REST API transport** (`OBSIDIAN_TRANSPORT=rest`) with a
  transparent filesystem fallback (`orion/obsidian_transport.py`).
- **`orion schedule`** — a small local scheduler for recurring vault chores
  (`daily_note`, `vault_tidy`); jobs are stored as JSON in `~/.orion/`.
- **`orion telegram`** — Telegram bot front-end (stdlib long polling, no new
  dependency) with inline-keyboard permission prompts.
- **Russian and Turkish** interface languages; `detect_language` now also
  recognises Turkish.
- **`search_knowledge`** — one RAG tool over notes *and* workspace code.
- Packaging: complete metadata, a metadata-derived `orion --version`,
  standalone `uv tool` / `pipx` install instructions, and packaging tests.
- Repo health: `.github/labels.yml` + `scripts/sync-labels.py`, a refreshed
  [good first issues](docs/good-first-issues.md) list, and a demo GIF.

### v0.11.0 — 2026-09-12

- **Plan tools** — the `plan` tool gained `mark` / `reset` actions and JSON
  serialization; `/plan` inspects and advances steps.
- **Sub-agents and parallel tools** — `SubAgent` for delegating research, and
  independent read-only tools run concurrently.
- **Self-verification** — the agent is nudged to verify its own work.

### v0.10.0 — 2026-09-12

- **Terminal UI overhaul**: answers stream as rendered Markdown (Rich `Live`),
  model thinking collapses to a one-line summary (`/think` to expand), long
  tool output collapses with a preview (`/show` to expand).
- **Multi-provider support**: DeepSeek, Anthropic, OpenAI, Google Gemini and
  Ollama behind one OpenAI-compatible client (`orion/providers.py`);
  `ORION_PROVIDER` in `.env` and `/model <provider>:<model>` at runtime, with
  per-provider cost defaults. Legacy `DEEPSEEK_*` variables keep working.
- **Green input box**: you type directly inside the box — no duplicate echo of
  your message after Enter.
- `ORION_COLLAPSE=0` disables collapsing for a fully verbose session.
- System prompt now instructs concise, terminal-friendly Markdown replies.
- `chat_stream` also collects `reasoning_content` (DeepSeek reasoner models).

### v0.9.0 — 2026-09-12

- **Multi-language UI**: English default, Uzbek (`ORION_LANG=uz`), and `auto`
  detection that follows the user's language via `ORION_LANG`. New `orion/i18n.py`.
- **User messages shown in a green box**, clearly separated from AI output.
- **Fixed `git_create_pr`** — it now invokes `gh` directly instead of routing
  it through `git` (previously it always failed).
- **Context auto-trim**: `ORION_MAX_HISTORY` (default 50) now trims long chats
  without ever splitting a tool-call chain.
- **Colorized `git_diff` output** in the terminal.
- **Clean MCP shutdown** on exit (`close()` / `close_all()`).
- All Uzbek user-facing strings made English (default UI language) or moved
  into the `orion/i18n.py` translation table.