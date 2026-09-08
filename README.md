# ORION — Operational Reasoning, Intelligence & Orchestration Network

A personal AI assistant powered by DeepSeek and Obsidian. It decides on its
own which parts of your conversations are worth saving to Obsidian, and it
can read, write and improve the projects on your computer — all from a
Claude Code-style terminal interface.

## Installation

With uv (recommended — installs everything including tests, semantic search
and MCP):

```bash
uv sync
uv run orion
```

Or with pip:

```bash
pip install -e ".[dev]"
```

To install ORION globally so you can run `orion` from any directory:

```bash
cd ~/orion            # or wherever the project lives
uv tool install --editable .
# to also enable semantic search and MCP in the global install:
uv tool install --editable --with "fastembed" --with "mcp<2" .
```

Create a `.env` file (copy from `.env.example`):

```bash
DEEPSEEK_API_KEY=sk-...
OBSIDIAN_VAULT=/home/you/Work/SecondBrain
# WORKSPACE (optional; defaults to the current terminal directory)
# WORKSPACE=/home/you/Projects
```

You can also run `orion config --init` to generate the `.env` file.
ORION reads `.env` from the current directory first, then from
`~/.orion/.env` — put your keys in `~/.orion/.env` when using the global
install.

**Workspace** is the root folder ORION uses to work with your projects. By
default it is detected automatically as the directory your terminal is in.
For example, `cd ~/my-project && orion` uses `~/my-project` as the
workspace. To use a different location, set `WORKSPACE=...` in `.env` or
pass the `orion --workspace /path` flag.

## Usage

```bash
orion                 # interactive session
orion -c              # continue the most recent session
orion -r <id>         # resume a session by ID
orion -p "query"      # non-interactive (prints the answer and exits)
orion "query"         # interactive session with an initial prompt
orion --model deepseek-chat --workspace /path/to/projects
orion config          # show configuration
orion config --init   # create .env from .env.example
orion config --edit   # open .env in $EDITOR
```

## Commands (Claude Code style)

| Command | What it does |
|---|---|
| `/help` | show all commands |
| `/clear` | clear the conversation context |
| `/model [name]` | show or switch the model |
| `/cost` | show token usage and cost |
| `/status` | show current configuration |
| `/memory` | show recent notes in Obsidian |
| `/compact` | summarize the conversation to save context |
| `/add-dir <path>` | switch the workspace directory |
| `/review` | show git status/diff in the workspace |
| `/init` | create an ORION.md project instructions file |
| `/config [init\|edit]` | view or initialize configuration |
| `/permissions` | view or change the permission mode |
| `/resume [id]` | list sessions or resume one |
| `/tools` | list available tools with descriptions |
| `/exit` | exit ORION |

- `@file` — include a file's content in your prompt (e.g. `@src/app.py`).
- `↑/↓` — prompt history.
- Sensitive commands (`run_command`, `git_commit`, `git_create_pr`, ...)
  ask for permission before running; disable with
  `--dangerously-skip-permissions` or `/permissions bypass`.
- `ORION.md` is read automatically at the start of each session (like
  `CLAUDE.md` in Claude Code).

## Features

- Obsidian memory: search, read, create, update, append.
- **Smart memory**: ORION decides what to save to Obsidian and what to
  skip, via the `save_memory` tool.
- **Agent mode**: for multi-step tasks ORION records a plan (via the `plan`
  tool), executes step by step, and shows progress in the terminal.
- Project work: `list_files`, `read_file`, `write_file`, `edit_file`,
  `run_command`.
- **Git integration**: `git_status`, `git_diff`, `git_log`, `git_commit`,
  `git_create_pr`.
- **Web search**: `web_search` via Tavily (set `TAVILY_API_KEY`) or
  DuckDuckGo fallback (no key needed).
- Streaming responses and session persistence (`orion -c` to resume).
- Automatic backups on updates (`.orion_backups/`).
- Token and cost tracking (`/cost`).
- **Pretty notes**: `save_memory` adds YAML frontmatter, tags and
  `[[wikilinks]]` to related notes, so the Obsidian graph view stays tidy.
- **Backlinks**: `link_notes` (and `save_memory`) add two-way links —
  related notes get a `## Backlinks` section pointing back.
- **Terminal system tools**: open URLs/apps, notifications, clipboard, screenshots.
- **MCP support**: connect any MCP server (Gmail, Slack, ...) via config.
- **Daily notes + Inbox triage**: `daily_note` creates/links daily notes,
  `triage_inbox` archives the Inbox into `Archive/YYYY/MM/`.
- **Auto-memory**: on exit, ORION summarizes the session and extracts
  important facts into Obsidian (`ORION_AUTO_MEMORY=0` to disable).
- **Semantic search**: optional vector search (fastembed) blended with
  keyword search — `pip install -e ".[semantic]"`, then run `reindex` once.
  Search never downloads models on its own; the model is only fetched during
  an explicit `reindex`, which prevents hangs.

## Adding a new tool (e.g. Telegram bot, Gmail)

Drop a new `.py` file into `orion/plugins/` — it is loaded automatically.
The shape is:

```python
from orion.tools import Tool


def register(registry, config):
    registry.register(MyTool())


class MyTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="What this tool does and when to use it",
            parameters={
                "arg1": {"type": "string", "description": "..."},
            },
            required=["arg1"],
        )

    def execute(self, arg1):
        # the actual work happens here
        return {"result": arg1}
```

Every plugin file must define a `register(registry, config)` function. Use
`config` to reach settings from `.env` (`config.obsidian_vault`,
`config.workspace`, ...).

## Tools and what they are for

### Obsidian memory (Second Brain)

| Tool | What it is for |
|---|---|
| `search_notes` | find notes matching a query, ranked by relevance |
| `read_note` | read a single note in full |
| `create_note` | create a new note |
| `update_note` | update an existing note (with automatic backup) |
| `append_to_note` | append new information to an existing note |
| `list_notes` | show the vault structure (list of notes) |
| `save_memory` | store important information — ORION decides what to save and what to skip |
| `link_notes` | add two-way `[[wikilinks]]` between related notes |
| `daily_note` | get or create today's daily note (linked to yesterday's) |
| `triage_inbox` | archive all Inbox notes into `Archive/YYYY/MM/` |
| `reindex` | build the semantic search index (run once) |

### Project work (workspace)

| Tool | What it is for |
|---|---|
| `list_files` | list folders and files in a project |
| `read_file` | read a file (optionally a line range) |
| `write_file` | create a file or overwrite an existing one |
| `edit_file` | edit a file by replacing an exact text snippet |
| `run_command` | run tests, builds, git and other shell commands |

### Git

| Tool | What it is for |
|---|---|
| `git_status` | show working tree status and current branch |
| `git_diff` | show unstaged (or staged) changes |
| `git_log` | show recent commit history |
| `git_commit` | stage files and commit with a message (asks permission) |
| `git_create_pr` | create a pull request via the `gh` CLI (asks permission) |

### Web

| Tool | What it is for |
|---|---|
| `web_search` | search the web for up-to-date information (Tavily or DuckDuckGo) |

### Agent

| Tool | What it is for |
|---|---|
| `plan` | create/update a step-by-step plan for a complex task |

### System (terminal)

| Tool | What it is for |
|---|---|
| `open_url` | open a URL in the default browser |
| `open_app` | launch an application |
| `notify` | send a desktop notification |
| `clipboard_copy` | copy text to the clipboard |
| `clipboard_read` | read text from the clipboard |
| `screenshot` | capture the screen (asks for permission) |

`/tools` shows this list with short descriptions in the terminal.

## MCP support

ORION can connect to MCP (Model Context Protocol) servers — the same
standard Claude Code uses — to reach external services like Gmail, Slack,
or any of the hundreds of available MCP servers.

```bash
pip install -e ".[mcp]"
```

Create `~/.orion/mcp.json`:

```json
{
  "mcpServers": {
    "time": { "command": "uvx", "args": ["mcp-server-time"] },
    "fetch": { "command": "uvx", "args": ["mcp-server-fetch"] }
  }
}
```

Each MCP tool appears as `mcp__<server>__<tool>` in ORION. If `mcp` is not
installed or the config is missing, ORION silently runs without it.

## Roadmap

- Obsidian Local REST API transport (alternative to direct file access).
- Web UI / 3D graph (Obsidian-style graph view).
- Autonomous bots (e.g. end-of-day vault tidy).
- Telegram / Discord bot mode.
- Self-updating: suggest new tools and prompts.
- RAG over code + notes together.

## Tests

```bash
pytest
```

## License

[MIT](LICENSE)
