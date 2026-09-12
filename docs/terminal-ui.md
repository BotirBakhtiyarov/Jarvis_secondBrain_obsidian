# Terminal UI

How ORION renders a session in the terminal.

## Green input box

You type directly inside the box — no duplicated echo after Enter:

```text
╭─ You ─────────────────────────────╮
│ fix the failing test in src/app.py
╰───────────────────────────────────╯
```

The box uses `prompt_toolkit`, so history (↑/↓), autocomplete (`/` commands,
`@file` mentions) all keep working inside it. After Enter the bottom border
closes the box and the answer starts below it.

## Rendered Markdown answers

Answers stream through Rich `Live` and are rendered as terminal Markdown:
headings become bold titles, code blocks get syntax highlighting, lists are
aligned. Raw `##`, `**` or ``` fences are never printed. The system prompt
also instructs the model to keep answers concise and terminal-friendly.

## Collapsible output

Long content collapses to a one-line summary so the important stuff stays
visible:

| What | Default view | Expand |
|---|---|---|
| Model thinking (`deepseek-reasoner`) | `⏺ Thinking (1.3k chars) — /think to view` | `/think` |
| `run_command` output | exit code + line count + first 4 lines | `/show` |
| `list_files`, `search_notes`, `web_search` results | first 4 lines | `/show` |

`/show` and `/think` print the last collapsed section in full. Set
`ORION_COLLAPSE=0` to disable collapsing entirely (everything is printed
verbosely, capped as before).
