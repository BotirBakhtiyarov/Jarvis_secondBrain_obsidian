# JARVIS — Second Brain + Coding Assistant

A personal AI assistant powered by DeepSeek and Obsidian. It decides on its
own which parts of your conversations are worth saving to Obsidian, and it
can read, write and improve the projects on your computer — all from a
Claude Code-style terminal interface.

## Installation

```bash
pip install -e ".[dev]"
```

Create a `.env` file (copy from `.env.example`):

```bash
DEEPSEEK_API_KEY=sk-...
OBSIDIAN_VAULT=/home/you/Work/SecondBrain
# WORKSPACE (optional; defaults to the current terminal directory)
# WORKSPACE=/home/you/Projects
```

**Workspace** is the root folder JARVIS uses to work with your projects. By
default it is detected automatically as the directory your terminal is in.
For example, `cd ~/my-project && jarvis` uses `~/my-project` as the
workspace. To use a different location, set `WORKSPACE=...` in `.env` or
pass the `jarvis --workspace /path` flag.

## Usage

```bash
jarvis                 # interactive session
jarvis -c              # continue the most recent session
jarvis -r <id>         # resume a session by ID
jarvis -p "query"      # non-interactive (prints the answer and exits)
jarvis "query"         # interactive session with an initial prompt
jarvis --model deepseek-chat --workspace /path/to/projects
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
| `/init` | create a JARVIS.md project instructions file |
| `/permissions` | view or change the permission mode |
| `/resume [id]` | list sessions or resume one |
| `/tools` | list available tools with descriptions |
| `/exit` | exit JARVIS |

- `@file` — include a file's content in your prompt (e.g. `@src/app.py`).
- `↑/↓` — prompt history.
- Commands (`run_command`) ask for permission before running; disable with
  `--dangerously-skip-permissions` or `/permissions bypass`.
- `JARVIS.md` is read automatically at the start of each session (like
  `CLAUDE.md` in Claude Code).

## Features

- Obsidian memory: search, read, create, update, append.
- **Smart memory**: JARVIS decides what to save to Obsidian and what to
  skip, via the `save_memory` tool.
- Project work: `list_files`, `read_file`, `write_file`, `edit_file`,
  `run_command`.
- Streaming responses and session persistence (`jarvis -c` to resume).
- Automatic backups on updates (`.jarvis_backups/`).
- Token and cost tracking (`/cost`).

## Adding a new tool (e.g. Telegram bot, Gmail)

Drop a new `.py` file into `jarvis/plugins/` — it is loaded automatically.
The shape is:

```python
from jarvis.tools import Tool


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
| `save_memory` | store important information — JARVIS decides what to save and what to skip |

### Project work (workspace)

| Tool | What it is for |
|---|---|
| `list_files` | list folders and files in a project |
| `read_file` | read a file (optionally a line range) |
| `write_file` | create a file or overwrite an existing one |
| `edit_file` | edit a file by replacing an exact text snippet |
| `run_command` | run tests, builds, git and other shell commands |

`/tools` shows this list with short descriptions in the terminal.

## Tests

```bash
pytest
```
