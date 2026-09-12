# ORION

**Operational Reasoning, Intelligence & Orchestration Network** — a terminal AI assistant that gives DeepSeek a long-term memory in Obsidian and hands to work in your code projects.

[![CI](https://github.com/BotirBakhtiyarov/orion-second-brain/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BotirBakhtiyarov/orion-second-brain/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.10.0-blue)](https://github.com/BotirBakhtiyarov/orion-second-brain/releases)

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

**Who is it for?** Developers and Obsidian users who want an agentic assistant
with durable, plain-text, local memory — and a Claude Code-style workflow that
reads like a real tool, not a toy.

## Features

- **Smart memory** — ORION autonomously decides what to persist to Obsidian and
  what to skip, via the `save_memory` tool and explicit rules in the system
  prompt.
- **Agent mode** — for multi-step tasks ORION records a plan (the `plan` tool),
  executes steps one by one, and shows progress in the terminal.
- **Multi‑language** — English interface by default; switch to Uzbek with
  `ORION_LANG=uz`, or use `ORION_LANG=auto` and ORION follows the language you
  write in. The assistant always replies in your language.
- **Terminal UI** — you type directly inside a green input box, answers stream
  as rendered Markdown (no raw `##`/`**` noise), and model thinking plus long
  tool output collapse to one-line summaries you can expand with `/think` and
  `/show` (see [docs/terminal-ui.md](docs/terminal-ui.md)).
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

## Multi-language

ORION's interface is **English by default** and can be switched in two ways:

```bash
ORION_LANG=en    # English (default)
ORION_LANG=uz    # Uzbek UI (menus, help, prompts)
ORION_LANG=auto  # follow the language you write in
```

- **`auto` mode** detects the language of each message you send (English,
  Uzbek or Russian) and switches the UI to match.
- **Replies always follow you**: the system prompt instructs the model to
  answer in the language you write in, regardless of the interface language —
  so you can keep a Uzbek UI while the assistant answers in English, or vice
  versa.
- Adding a new language means adding one dictionary to `orion/i18n.py` and
  opening a PR. Tool descriptions and the system prompt intentionally stay in
  English — models produce more reliable tool calls against a single, crisp
  schema.

## Demo

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

You do **not** need a real API key to develop ORION itself — the test suite
never touches the network (except one explicitly `network`-marked test).

## Configuration

All configuration comes from `.env` (project-local) or `~/.orion/.env`
(global). Project values win; the global file fills in gaps.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | **yes** | — | DeepSeek API key |
| `DEEPSEEK_BASE_URL` | no | `https://api.deepseek.com` | API base URL |
| `DEEPSEEK_MODEL` | no | `deepseek-chat` | Model: `deepseek-chat` or `deepseek-reasoner` |
| `OBSIDIAN_VAULT` | **yes** | — | Path to your Obsidian vault |
| `WORKSPACE` | no | current directory | Root for file operations |
| `ORION_LANG` | no | `en` | Interface language: `en`, `uz` or `auto` |
| `ORION_COLLAPSE` | no | `1` | `1` = collapse long output/thinking (`/show`, `/think` to expand); `0` = show everything |
| `TAVILY_API_KEY` | no | — | Enables Tavily web search; empty → DuckDuckGo |
| `ORION_HISTORY` | no | `~/.orion/history.json` | Session history location |
| `ORION_MAX_HISTORY` | no | `50` | Max messages kept in context (auto-trim) |
| `DEEPSEEK_INPUT_PRICE` | no | `0.27` | USD per 1M input tokens (cost estimate) |
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
orion -v                                     # version
```

### In-session slash commands

| Command | What it does |
|---|---|
| `/help` | Show this help |
| `/clear` | Clear the conversation context |
| `/model [name]` | Show or switch the model (`deepseek-chat` / `deepseek-reasoner`) |
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
├── tools.py         # Tool base class + ToolRegistry
├── prompts.py       # System prompt (memory / coding / agent rules)
├── i18n.py          # Multi-language UI strings (English default, auto-detect)
├── memory.py        # Session save / resume / list
├── obsidian.py      # Vault: notes, search, frontmatter, backlinks
├── workspace.py     # Workspace: sandboxed file operations
├── semantic.py      # Optional vector search (fastembed)
├── mcp.py           # MCP client manager (clean shutdown)
├── ui.py            # Rich rendering helpers + user-message box
├── agent.py         # Plan + PlanTool (agent mode)
└── plugins/         # Auto-loaded tools
    ├── obsidian_plugin.py
    ├── memory_plugin.py
    ├── code_plugin.py
    ├── git_plugin.py
    ├── web_plugin.py
    ├── system_plugin.py
    └── mcp_plugin.py
├── tests/           # pytest suite
├── docs/            # additional documentation
├── .github/workflows/  # CI and release automation
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
expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md). New here? Check
the [good first issues](docs/good-first-issues.md).

## License

This project is licensed under the [MIT License](LICENSE).

## Roadmap

Planned or desired improvements:

- Obsidian Local REST API transport as an alternative to direct file access.
- A web UI / graph view over the vault.
- Autonomous background tasks (e.g. an end-of-day vault tidy).
- Telegram / Discord bot mode.
- RAG over code and notes together.
- More interface languages in `orion/i18n.py`.

## Changelog

### v0.10.0 — 2026-09-12

- **Terminal UI overhaul**: answers stream as rendered Markdown (Rich `Live`),
  model thinking collapses to a one-line summary (`/think` to expand), long
  tool output collapses with a preview (`/show` to expand).
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