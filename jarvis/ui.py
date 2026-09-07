import difflib
import json

from rich.console import Console
from rich.panel import Panel

console = Console()


def print_banner(version: str):
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]JARVIS {version}[/bold cyan]  "
            "[dim]Second Brain + Coding Assistant[/dim]",
            border_style="cyan",
        )
    )


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

    if "action" in result:
        console.print(
            f"[green]  ✓ {result['action']}[/green] [dim]{result.get('path', '')}[/dim]"
        )
        if result.get("backup"):
            console.print(f"[dim]  backup: {result['backup']}[/dim]")
        return

    if "results" in result:
        results = result["results"]
        if not results:
            console.print("[dim]  (no results)[/dim]")
            return
        for r in results[:10]:
            console.print(
                f"  [bold]{r['path']}[/bold] [dim](score {r['score']})[/dim]"
            )
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
            f"[dim]  read {result['path']} "
            f"({result.get('total_lines', '?')} lines)[/dim]"
        )
        return

    console.print(json.dumps(result, ensure_ascii=False, default=str))


def render_diff(old: str, new: str, path: str):
    diff = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    for line in diff:
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
