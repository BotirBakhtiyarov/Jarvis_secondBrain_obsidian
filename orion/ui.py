import json

from rich.console import Console
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


def print_user_message(text: str):
    """Show the user's message in a green panel, distinct from AI output."""
    label = i18n.t("user_title")
    console.print(Panel(Text(text), title=label, title_align="left", border_style="green"))


def print_tool_call(name: str, arguments: dict):
    args = json.dumps(arguments, ensure_ascii=False) if arguments else ""
    console.print(f"[cyan]⏺[/cyan] [bold]{name}[/bold] [dim]{args}[/dim]")


def print_tool_result(result: dict):
    if not isinstance(result, dict):
        console.print(f"[dim]{result}[/dim]")
        return

    if result.get("error"):
        console.print(f"[red]  ✗ {result['error']}[/red]")
        return

    if "exit_code" in result:
        console.print(f"[dim]  exit code: {result['exit_code']}[/dim]")
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()
        if stdout:
            for line in stdout.splitlines()[:40]:
                console.print(f"  {line}", markup=False, highlight=False)
        if stderr:
            console.print(f"[yellow]  {stderr}[/yellow]", markup=False, highlight=False)
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
        for r in results[:10]:
            if "title" in r:
                console.print(f"  [bold]{r['title']}[/bold]")
                console.print(f"    [cyan]{r.get('url', '')}[/cyan]")
                snippet = (r.get("snippet") or "").replace("\n", " ")
                if snippet:
                    console.print(f"    [dim]{snippet[:160]}[/dim]")
            else:
                console.print(f"  [bold]{r['path']}[/bold] [dim](score {r['score']})[/dim]")
        return

    if "notes" in result and "total" in result:
        console.print(f"[dim]  {result['total']} notes[/dim]")
        for n in result["notes"][:20]:
            console.print(f"  [dim]{n}[/dim]")
        return

    if "entries" in result:
        for e in result["entries"][:40]:
            kind = "[cyan]dir[/cyan]" if e["type"] == "dir" else "file"
            console.print(f"  {e['path']}  [{kind}]")
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
