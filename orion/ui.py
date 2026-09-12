import json
import os
import shutil
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from orion import i18n

console = Console()

_BANNER = r"""[bold cyan]
  ___  ____  ___ ___  _   _
 / _ \|  _ \|_ _/ _ \| \ | |
| | | | |_) || | | | |  \| |
| |_| |  _ < | | |_| | |\  |
 \___/|_| \_\___\___/|_| \_|
[/bold cyan]"""

_TAGLINE = "[dim]Operational Reasoning, Intelligence & Orchestration Network[/dim]"


def print_banner(version: str):
    console.print()
    console.print(_BANNER)
    console.print(
        Panel.fit(f"[bold cyan]ORION {version}[/bold cyan]  {_TAGLINE}", border_style="cyan")
    )
    console.print()


# --- User input box --------------------------------------------------------


def user_box_parts(width: int | None = None) -> tuple[str, str, str]:
    """(top border, input prefix, bottom border) of the green input box."""
    label = i18n.t("user_title")
    if width is None:
        width = shutil.get_terminal_size().columns - 2
    width = max(20, min(width, 72))
    inner = width - 2
    header = f"─ {label} "
    top = "╭" + header + "─" * max(1, inner - len(header)) + "╮"
    prefix = "│ "
    bottom = "╰" + "─" * inner + "╯"
    return top, prefix, bottom


def print_user_box(text: str) -> None:
    """Draw the full green box around a user message (e.g. the initial query)."""
    top, prefix, bottom = user_box_parts()
    console.print(f"[green]{top}[/green]")
    for line in text.splitlines() or [""]:
        console.print(f"[green]{prefix}[/green]{line}")
    console.print(f"[green]{bottom}[/green]")


# --- Collapsed (dropdown-style) output --------------------------------------


_REMEMBERED: dict[str, str] = {"label": "", "text": ""}
_LAST_THINKING = ""
_COLLAPSE_LINES = 12


def _collapse_enabled() -> bool:
    return os.environ.get("ORION_COLLAPSE", "1") != "0"


def remember(label: str, text: str) -> None:
    """Store the last collapsed output so ``/show`` can expand it."""
    _REMEMBERED["label"] = label
    _REMEMBERED["text"] = text


def remember_thinking(text: str) -> None:
    global _LAST_THINKING
    _LAST_THINKING = text


def show_remembered() -> None:
    """``/show`` — print the last collapsed output in full."""
    if not _REMEMBERED["text"]:
        console.print(f"[dim]{i18n.t('nothing_to_show')}[/dim]")
        return
    console.print(
        Panel(
            Text(_REMEMBERED["text"]),
            title=_REMEMBERED["label"] or None,
            title_align="left",
            border_style="cyan",
        )
    )


def show_thinking() -> None:
    """``/think`` — print the model's last reasoning in full."""
    if not _LAST_THINKING:
        console.print(f"[dim]{i18n.t('nothing_to_show')}[/dim]")
        return
    console.print(
        Panel(
            Text(_LAST_THINKING),
            title=i18n.t("thinking_title"),
            title_align="left",
            border_style="dim",
        )
    )


def collapsed_preview(label: str, lines: list[str], max_lines: int = 4) -> None:
    """Print a short preview; the full text stays available via ``/show``."""
    remember(label, "\n".join(lines))
    for line in lines[:max_lines]:
        console.print(f"  {line}", style="dim", markup=False, highlight=False)
    hidden = len(lines) - max_lines
    if hidden > 0:
        console.print(f"  [cyan]▸[/cyan] [dim]{i18n.t('more_lines', n=hidden)}[/dim]")


def print_answer(text: str) -> None:
    """Render a final answer as terminal Markdown (no raw ``##``/``**``)."""
    if text.strip():
        console.print(Markdown(text))


class TurnView:
    """Render one model turn.

    - Reasoning streams into a transient counter line and collapses to a
      one-line summary (full text via ``/think``).
    - The answer streams as live Markdown and stays rendered afterwards.
    - Nothing else is printed: long tool output is collapsed elsewhere.
    """

    def __init__(self, interactive: bool):
        self.interactive = interactive
        self._spinner = None
        self._live: Live | None = None
        self._kind = ""  # "" | "thinking" | "answer"
        self._buf: list[str] = []
        self._thinking: list[str] = []
        self._chars = 0
        self._last_update = 0.0

    def attach_spinner(self, spinner) -> None:
        self._spinner = spinner

    def _drop_spinner(self) -> None:
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None

    def _close_live(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        self._kind = ""

    def reasoning_delta(self, chunk: str) -> None:
        if not chunk:
            return
        self._drop_spinner()
        self._thinking.append(chunk)
        if not self.interactive or not console.is_terminal:
            return
        if self._kind != "thinking":
            self._close_live()
            self._live = Live(console=console, refresh_per_second=12, transient=True)
            self._live.start()
            self._kind = "thinking"
            self._chars = 0
        self._chars += len(chunk)
        self._live.update(Text(f"⏺ {i18n.t('thinking')} {self._chars:,}", style="dim"))

    def text_delta(self, chunk: str) -> None:
        if not chunk:
            return
        self._drop_spinner()
        self._buf.append(chunk)
        if self._kind == "thinking":
            self._finish_thinking()
        if not self.interactive or not console.is_terminal:
            return
        if self._live is None:
            self._live = Live(console=console, refresh_per_second=10)
            self._live.start()
            self._kind = "answer"
        now = time.monotonic()
        if now - self._last_update >= 0.08:
            self._last_update = now
            self._live.update(Markdown("".join(self._buf)))

    def _finish_thinking(self) -> None:
        reasoning = "".join(self._thinking)
        self._thinking = []
        self._close_live()
        if reasoning.strip() and self.interactive:
            remember_thinking(reasoning)
            console.print(
                f"[cyan]▸[/cyan] [dim]{i18n.t('thinking_done', n=format_number(len(reasoning)))}[/dim]"
            )

    def cleanup(self) -> None:
        """Stop the spinner/live without printing anything (error paths)."""
        self._drop_spinner()
        self._close_live()

    def end_turn(self) -> None:
        """Finish the stream: collapse thinking, keep the rendered answer."""
        self._drop_spinner()
        text = "".join(self._buf)
        if self._kind == "thinking" or self._thinking:
            self._finish_thinking()
        if self._live is not None:
            self._live.update(Markdown(text))
            self._live.stop()
            self._live = None
            self._kind = ""
        elif text.strip() and (not self.interactive or not console.is_terminal):
            print_answer(text)
        self._buf = []


def print_tool_call(name: str, arguments: dict):
    if name == "run_command" and isinstance(arguments, dict) and arguments.get("command"):
        console.print(f"[cyan]⏺[/cyan] [bold]run_command[/bold] [dim]{arguments['command']}[/dim]")
        return
    args = json.dumps(arguments, ensure_ascii=False) if arguments else ""
    if len(args) > 120:
        args = args[:117] + "…"
    console.print(f"[cyan]⏺[/cyan] [bold]{name}[/bold] [dim]{args}[/dim]")


def print_tool_result(result: dict):
    if not isinstance(result, dict):
        console.print(f"[dim]{result}[/dim]")
        return

    if result.get("error"):
        console.print(f"[red]  ✗ {result['error']}[/red]")
        return

    if "exit_code" in result:
        command = (result.get("command") or "").strip()
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()
        out = "\n".join(part for part in (stdout, stderr) if part)
        lines = out.splitlines() if out else []
        header = f"exit {result['exit_code']} · {len(lines)} lines"
        if not lines:
            console.print(f"[dim]  {header}[/dim]")
            return
        if _collapse_enabled() and len(lines) > _COLLAPSE_LINES:
            body = (f"$ {command}\n" if command else "") + out
            remember("output", body)
            console.print(f"[cyan]  ▸[/cyan] [dim]{header} — {i18n.t('expand_show')}[/dim]")
            return
        console.print(f"[dim]  {header}[/dim]")
        for line in lines[:40]:
            console.print(f"  {line}", markup=False, highlight=False)
        if len(lines) > 40:
            console.print(f"  [dim]… {i18n.t('more_lines', n=len(lines) - 40)}[/dim]")
        return

    if "diff" in result:
        render_diff(result.get("diff") or "")
        return

    if "moved" in result:
        n = len(result.get("moved") or [])
        console.print(f"[green]  ✓ moved {n} notes[/green] [dim]→ {result.get('to', '')}[/dim]")
        return

    if "action" in result:
        if result["action"] == "reindex":
            console.print(f"[green]  ✓ indexed {result.get('notes', '?')} notes[/green]")
            return
        if result["action"] == "commit":
            console.print(
                f"[green]  ✓ committed[/green] [dim]{result.get('message', '')[:80]}[/dim]"
            )
            return
        console.print(f"[green]  ✓ {result['action']}[/green] [dim]{result.get('path', '')}[/dim]")
        if result.get("backup"):
            console.print(f"[dim]  backup: {result['backup']}[/dim]")
        if result.get("backlinks"):
            for b in result["backlinks"]:
                console.print(f"[dim]  ⇄ {b}[/dim]")
        return

    if "results" in result:
        results = result["results"]
        if not results:
            console.print("[dim]  (no results)[/dim]")
            return
        rendered = []
        for r in results[:10]:
            if "title" in r:
                rendered.append(r["title"])
                rendered.append(f"  {r.get('url', '')}")
                snippet = (r.get("snippet") or "").replace("\n", " ")
                if snippet:
                    rendered.append(f"  {snippet[:160]}")
            else:
                rendered.append(f"{r['path']} (score {r['score']})")
        if _collapse_enabled() and len(rendered) > 8:
            collapsed_preview("results", rendered)
            return
        for line in rendered:
            console.print(f"  {line}")
        return

    if "notes" in result and "total" in result:
        lines = [f"{result['total']} notes", *(str(n) for n in result["notes"])]
        if _collapse_enabled() and len(lines) > 8:
            collapsed_preview("notes", lines)
            return
        for line in lines[:20]:
            console.print(f"  [dim]{line}[/dim]")
        return

    if "entries" in result:
        lines = [
            f"{e['path']}  [{'dir' if e['type'] == 'dir' else 'file'}]" for e in result["entries"]
        ]
        if _collapse_enabled() and len(lines) > 8:
            collapsed_preview("files", lines)
            return
        for line in lines[:40]:
            console.print(f"  {line}")
        return

    if "content" in result and "path" in result:
        console.print(
            f"[dim]  read {result['path']} ({result.get('total_lines', '?')} lines)[/dim]"
        )
        return

    console.print(json.dumps(result, ensure_ascii=False, default=str))


def render_diff(diff_text: str):
    """Print a unified diff with color: + green, - red, @@ blue, headers dim."""
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")):
            console.print(f"[dim]{line}[/dim]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]")
        else:
            console.print(line)


def format_number(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}k"
    return f"{n:.0f}"


_STATUS_ICONS = {
    "done": "[green]✓ done[/green]",
    "in_progress": "[yellow]▶ in progress[/yellow]",
    "pending": "[dim]· pending[/dim]",
    "failed": "[red]✗ failed[/red]",
}


def print_plan(steps: list):
    if not steps:
        return

    table = Table(title="Plan", border_style="cyan", show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Step")
    table.add_column("Status")

    for i, step in enumerate(steps, 1):
        status = step.get("status", "pending") if isinstance(step, dict) else "pending"
        title = step.get("title", "") if isinstance(step, dict) else str(step)
        table.add_row(str(i), title, _STATUS_ICONS.get(status, status))

    console.print(table)


def print_key_value(rows: list[tuple[str, str]], title: str = ""):
    table = Table(title=title or None, border_style="cyan", show_header=False)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value")
    for k, v in rows:
        table.add_row(k, v)
    console.print(table)
