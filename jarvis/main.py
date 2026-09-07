import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from openai import OpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory

from jarvis import ui
from jarvis.config import load_config
from jarvis.llm import chat_once, chat_stream
from jarvis.memory import (
    list_sessions,
    load_latest,
    load_session,
    save_session,
)
from jarvis.obsidian import Vault
from jarvis.plugins import load_plugins
from jarvis.prompts import SYSTEM_PROMPT
from jarvis.tools import ToolRegistry
from jarvis.ui import console

VERSION = "0.5.0"

EXIT_COMMANDS = {"exit", "quit", "q", "/exit", "/quit"}

SLASH_COMMANDS = [
    "help", "clear", "model", "cost", "status", "memory", "compact",
    "add-dir", "review", "init", "permissions", "resume", "tools",
    "exit", "version",
]

JARVIS_MD_TEMPLATE = """# JARVIS.md

Bu fayl JARVIS uchun loyiha ko'rsatmalari. Sessiya boshida avtomatik o'qiladi.

## Loyiha haqida
<!-- Loyihangiz nima ekanini qisqa tasvirlang -->

## Kodlash standartlari
<!-- Afzal ko'rgan uslub, konvensiyalar, cheklovlar -->

## Buyruqlar
<!-- test/build ishga tushirish buyruqlari -->
"""


class Session:
    """Joriy sessiya holati: tokenlar, narx va permission rejimi."""

    def __init__(self, config):
        self.input_tokens = 0
        self.output_tokens = 0
        self.bypass = False
        self.started = time.time()

    def add_usage(self, usage):
        if usage is None:
            return
        self.input_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.output_tokens += getattr(usage, "completion_tokens", 0) or 0

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    def cost(self, config):
        return (
            self.input_tokens / 1e6 * config.input_price
            + self.output_tokens / 1e6 * config.output_price
        )


class JarvisCompleter(Completer):
    """`/` buyruqlar va `@` fayl yo'llari uchun avtomatik to'ldirish."""

    def __init__(self):
        self.workspace = None

    def set_workspace(self, ws):
        self.workspace = ws

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/"):
            word = text[1:]
            for c in SLASH_COMMANDS:
                if c.startswith(word):
                    yield Completion("/" + c, start_position=-len(word))
            return

        if "@" in text and self.workspace:
            prefix = text.rsplit("@", 1)[-1]
            yield from self._paths(prefix)

    def _paths(self, prefix):
        base = self.workspace
        try:
            if "/" in prefix:
                folder, stem = prefix.rsplit("/", 1)
                search = base / folder
            else:
                folder, stem = "", prefix
                search = base

            if not search.exists():
                return

            for p in sorted(search.iterdir()):
                if p.name.startswith(stem):
                    rel = str(p.relative_to(base))
                    if p.is_dir():
                        rel += "/"
                    yield Completion(rel, start_position=-len(stem))
        except OSError:
            return


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — Second Brain + Coding Assistant",
    )
    parser.add_argument(
        "query", nargs="*", help="Boshlang'ich so'rov (interaktiv sessiya boshlaydi)"
    )
    parser.add_argument(
        "-p", "--print", action="store_true",
        help="Javobni chiqarib chiqish (non-interaktiv)",
    )
    parser.add_argument(
        "-c", "--continue", dest="resume_last", action="store_true",
        help="Eng oxirgi sessiyani davom ettirish",
    )
    parser.add_argument(
        "-r", "--resume", metavar="ID", help="ID bo'yicha sessiyani davom ettirish",
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Versiyani ko'rsatish",
    )
    parser.add_argument("--model", help="DeepSeek modelini almashtirish")
    parser.add_argument("--vault", help="Obsidian vault path'ni almashtirish")
    parser.add_argument("--workspace", help="Workspace (loyihalar) root'ini almashtirish")
    parser.add_argument(
        "--dangerously-skip-permissions", action="store_true",
        help="Buyruqlar uchun ruxsat so'rovlarini o'tkazib yuborish",
    )
    return parser.parse_args(argv)


def build_system(config: "Config") -> str:
    system = SYSTEM_PROMPT
    jarvis_md = config.workspace / "JARVIS.md"
    if jarvis_md.exists():
        try:
            content = jarvis_md.read_text(encoding="utf-8", errors="ignore")
            system += "\n\n=== PROJECT INSTRUCTIONS (JARVIS.md) ===\n" + content
        except OSError:
            pass
    return system


def expand_mentions(text: str, workspace: Path) -> str:
    """`@path` ni fayl kontenti bilan almashtiradi (mavjud fayl bo'lsa)."""

    def repl(match):
        rel = match.group(1)
        p = (workspace / rel).resolve()
        try:
            if p.is_file() and (workspace in p.parents or p == workspace):
                content = p.read_text(encoding="utf-8", errors="ignore")
                return f"\n<file path=\"{rel}\">\n{content}\n</file>\n"
        except OSError:
            pass
        return match.group(0)

    return re.sub(r"@([^\s@]+)", repl, text)


def confirm_command(command: str, session: Session) -> bool:
    console.print(f"[yellow]⚡ Run command?[/yellow] [bold]{command}[/bold]")
    while True:
        ans = console.input("[dim]  (y/n/always) [/dim]").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        if ans in ("always", "a"):
            session.bypass = True
            return True


def run_turn(client, config, registry, messages, session, interactive=True):
    while True:
        first = {"v": True}

        def on_text(chunk):
            if interactive:
                if first["v"]:
                    console.print()
                    first["v"] = False
                console.file.write(chunk)
                console.file.flush()
            else:
                if first["v"]:
                    first["v"] = False
                sys.stdout.write(chunk)
                sys.stdout.flush()

        text, tool_calls, _, usage = chat_stream(
            client, config.model, messages, registry.schema(), on_text=on_text
        )
        session.add_usage(usage)

        if interactive and first["v"]:
            console.print()

        if not tool_calls:
            messages.append({"role": "assistant", "content": text})
            if interactive:
                console.print()
            return

        messages.append(
            {
                "role": "assistant",
                "content": text or None,
                "tool_calls": tool_calls,
            }
        )

        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                arguments = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}

            if interactive:
                ui.print_tool_call(name, arguments)
            else:
                print(f"⏺ {name} {json.dumps(arguments, ensure_ascii=False)}")

            if name == "run_command" and interactive and not session.bypass:
                if not confirm_command(arguments.get("command", ""), session):
                    result = {"error": "User denied permission to run command"}
                else:
                    result = registry.execute(name, arguments)
            else:
                result = registry.execute(name, arguments)

            if interactive:
                ui.print_tool_result(result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )


# ----------------------------------------------------------------------
# Slash command handlers
# ----------------------------------------------------------------------

def cmd_help(ctx):
    console.print("\n[bold cyan]Slash commands:[/bold cyan]")
    for c, desc in [
        ("/help", "bu yordamni ko'rsatish"),
        ("/clear", "suhbat kontekstini tozalash"),
        ("/model [name]", "modelni ko'rsatish yoki almashtirish"),
        ("/cost", "token va xarajatni ko'rsatish"),
        ("/status", "joriy konfiguratsiyani ko'rsatish"),
        ("/memory", "Obsidian xotirasidagi so'nggi notalar"),
        ("/compact", "suhbatni qisqartirib kontekstni tejash"),
        ("/add-dir <path>", "workspace papkasini almashtirish"),
        ("/review", "workspace'dagi git status/diff"),
        ("/init", "JARVIS.md ko'rsatmalar faylini yaratish"),
        ("/permissions [on|bypass]", "ruxsat rejimini ko'rish/o'zgartirish"),
        ("/resume [id]", "sessiyalarni ko'rish yoki davom ettirish"),
        ("/tools", "mavjud tool'larni tavsifi bilan ko'rsatish"),
        ("/exit", "chiqish"),
        ("/version", "versiyani ko'rsatish"),
    ]:
        console.print(f"  [green]{c}[/green]  {desc}")
    console.print("\n[dim]@file — fayl kontentini so'rovga qo'shish. ↑/↓ — tarix.[/dim]")


def cmd_clear(ctx):
    ctx["messages"][:] = [ctx["messages"][0]]
    console.print("[green]✓ Context cleared.[/green]")


def cmd_model(ctx):
    args = ctx["args"]
    if args:
        ctx["config"].model = args[0]
        console.print(f"[green]✓ Model:[/green] {ctx['config'].model}")
    else:
        console.print(f"[cyan]Model:[/cyan] {ctx['config'].model}")
        console.print("[dim]Available: deepseek-chat, deepseek-reasoner[/dim]")


def cmd_cost(ctx):
    s = ctx["session"]
    c = ctx["config"]
    console.print(
        f"[cyan]Tokens:[/cyan] in {ui.format_number(s.input_tokens)} · "
        f"out {ui.format_number(s.output_tokens)} · "
        f"total {ui.format_number(s.total_tokens)}"
    )
    console.print(
        f"[cyan]Cost:[/cyan] ${s.cost(c):.4f} "
        f"[dim](in ${c.input_price}/M · out ${c.output_price}/M)[/dim]"
    )


def cmd_status(ctx):
    c = ctx["config"]
    r = ctx["registry"]
    mode = "bypass (skip prompts)" if ctx["session"].bypass else "ask for commands"
    console.print(f"[cyan]Model:[/cyan] {c.model}")
    console.print(f"[cyan]Vault:[/cyan] {c.obsidian_vault}")
    console.print(f"[cyan]Workspace:[/cyan] {c.workspace}")
    console.print(f"[cyan]Tools:[/cyan] {', '.join(r.names())}")
    console.print(f"[cyan]Permission mode:[/cyan] {mode}")


def cmd_memory(ctx):
    c = ctx["config"]
    vault = Vault(c.obsidian_vault)
    res = vault.list_notes(limit=15)
    if "error" in res:
        console.print(f"[red]{res['error']}[/red]")
        return
    console.print(f"[cyan]Recent notes ({res['total']} total):[/cyan]")
    for n in res["notes"]:
        console.print(f"  [dim]{n}[/dim]")
    console.print(
        "[dim]Memory rules: muhim ma'lumot save_memory orqali saqlanadi; oddiy chat saqlanmaydi.[/dim]"
    )


def cmd_compact(ctx):
    c = ctx["config"]
    messages = ctx["messages"]
    if len(messages) <= 3:
        console.print("[dim]Nothing to compact.[/dim]")
        return

    with console.status("[cyan]Compacting…[/cyan]"):
        summary, _ = chat_once(
            ctx["client"],
            c.model,
            [
                {
                    "role": "system",
                    "content": (
                        "Summarize this conversation concisely, preserving key "
                        "facts, decisions and the user's preferences. Reply in "
                        "the user's language."
                    ),
                },
                *messages[1:],
            ],
        )

    messages[:] = [
        messages[0],
        {"role": "user", "content": "[Conversation summary]\n" + (summary or "")},
    ]
    console.print("[green]✓ Compacted.[/green]")


def cmd_add_dir(ctx):
    c = ctx["config"]
    if not ctx["args"]:
        console.print("[red]Usage: /add-dir <path>[/red]")
        return
    path = Path(ctx["args"][0]).expanduser().resolve()
    if not path.is_dir():
        console.print(f"[red]Not a directory: {path}[/red]")
        return
    c.workspace = path
    ctx["registry"] = rebuild_registry(c)
    ctx["completer"].set_workspace(path)
    console.print(f"[green]✓ Workspace:[/green] {path}")


def cmd_review(ctx):
    ws = ctx["config"].workspace
    if not (ws / ".git").exists():
        console.print(f"[yellow]Not a git repository:[/yellow] {ws}")
        return

    status = subprocess.run(
        ["git", "status", "--short"], cwd=str(ws), capture_output=True, text=True
    )
    diff = subprocess.run(
        ["git", "diff", "--stat"], cwd=str(ws), capture_output=True, text=True
    )
    console.print("[cyan]git status:[/cyan]")
    console.print(status.stdout or "(clean)", markup=False)
    console.print("[cyan]git diff --stat:[/cyan]")
    console.print(diff.stdout or "(no changes)", markup=False)


def cmd_init(ctx):
    path = ctx["config"].workspace / "JARVIS.md"
    if path.exists():
        console.print(f"[dim]Already exists: {path}[/dim]")
        return
    path.write_text(JARVIS_MD_TEMPLATE, encoding="utf-8")
    console.print(f"[green]✓ Created[/green] {path}")


def cmd_permissions(ctx):
    s = ctx["session"]
    if ctx["args"] and ctx["args"][0] in ("bypass", "skip", "off"):
        s.bypass = True
    elif ctx["args"] and ctx["args"][0] in ("on", "ask", "default"):
        s.bypass = False
    mode = "bypass (skip prompts)" if s.bypass else "ask for commands"
    console.print(f"[cyan]Permission mode:[/cyan] {mode}")


def cmd_resume(ctx):
    sessions = list_sessions(ctx["config"].history_path)
    if not sessions:
        console.print("[dim]No saved sessions.[/dim]")
        return

    if ctx["args"]:
        hist = load_session(ctx["config"].history_path, ctx["args"][0])
        if hist is None:
            console.print("[red]Session not found.[/red]")
            return
        ctx["messages"][:] = [ctx["messages"][0], *hist]
        console.print("[green]✓ Resumed.[/green]")
        return

    console.print("[cyan]Saved sessions:[/cyan]")
    for s in sessions:
        console.print(
            f"  [green]{s['id']}[/green]  {s['first']}  [dim]({s['messages']} msgs)[/dim]"
        )
    console.print("[dim]Resume: /resume <id>[/dim]")


def cmd_tools(ctx):
    console.print("\n[bold cyan]Available tools:[/bold cyan]")
    for name, summary in ctx["registry"].describe():
        console.print(f"  [green]{name}[/green] — {summary}")


def cmd_version(ctx):
    console.print(f"jarvis {VERSION}")


COMMAND_HANDLERS = {
    "help": cmd_help,
    "clear": cmd_clear,
    "model": cmd_model,
    "cost": cmd_cost,
    "status": cmd_status,
    "memory": cmd_memory,
    "compact": cmd_compact,
    "add-dir": cmd_add_dir,
    "review": cmd_review,
    "init": cmd_init,
    "permissions": cmd_permissions,
    "resume": cmd_resume,
    "tools": cmd_tools,
    "version": cmd_version,
}


def handle_slash(line: str, ctx: dict):
    parts = line.split()
    name = parts[0][1:]
    ctx["args"] = parts[1:]

    handler = COMMAND_HANDLERS.get(name)
    if handler:
        handler(ctx)
    else:
        console.print(f"[yellow]Unknown command: /{name}. Type /help[/yellow]")


def rebuild_registry(config):
    registry = ToolRegistry()
    load_plugins(registry, config)
    return registry


def print_cost_summary(session: Session, config):
    console.print(
        f"[dim]Tokens: {ui.format_number(session.total_tokens)} · "
        f"Cost: ${session.cost(config):.4f}[/dim]"
    )


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.version:
        print(f"jarvis {VERSION}")
        return

    try:
        config = load_config(
            {"model": args.model, "vault": args.vault, "workspace": args.workspace}
        )
    except ValueError as err:
        console.print(f"[bold red]❌ {err}[/bold red]")
        raise SystemExit(1)

    if not config.api_key:
        console.print(
            "[bold red]❌ DEEPSEEK_API_KEY not found! Check your .env file.[/bold red]"
        )
        raise SystemExit(1)

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    registry = ToolRegistry()
    load_plugins(registry, config)

    session = Session(config)
    session.bypass = args.dangerously_skip_permissions

    messages = [{"role": "system", "content": build_system(config)}]

    if args.resume:
        hist = load_session(config.history_path, args.resume)
        if hist is None:
            console.print(f"[red]Session '{args.resume}' not found.[/red]")
            raise SystemExit(1)
        messages.extend(hist)
    elif args.resume_last:
        hist = load_latest(config.history_path)
        if hist:
            messages.extend(hist)
        else:
            console.print("[dim]No previous session — starting fresh.[/dim]")

    initial_query = " ".join(args.query).strip()

    if args.print and not initial_query and not sys.stdin.isatty():
        initial_query = sys.stdin.read().strip()

    # Non-interaktiv rejim
    if args.print:
        if initial_query:
            messages.append({"role": "user", "content": initial_query})
        try:
            run_turn(client, config, registry, messages, session, interactive=False)
        except KeyboardInterrupt:
            pass
        except Exception as err:  # noqa: BLE001
            console.print(f"[red]Error: {err}[/red]")
        save_session(config.history_path, messages)
        return

    # Interaktiv rejim
    ui.print_banner(VERSION)
    console.print(f"[dim]Model {config.model} · Workspace {config.workspace}[/dim]")
    console.print("[dim]Type /help for commands · @file to include a file[/dim]")

    completer = JarvisCompleter()
    completer.set_workspace(config.workspace)
    input_history = Path(config.history_path).parent / "input_history.txt"
    input_history.parent.mkdir(parents=True, exist_ok=True)
    prompt_session = PromptSession(
        history=FileHistory(str(input_history)),
        completer=completer,
    )

    ctx = {
        "config": config,
        "client": client,
        "registry": registry,
        "session": session,
        "messages": messages,
        "completer": completer,
    }

    if initial_query:
        messages.append({"role": "user", "content": initial_query})
        try:
            run_turn(client, config, ctx["registry"], messages, session, interactive=True)
        except Exception as err:  # noqa: BLE001
            console.print(f"\n[red]❌ Error: {err}[/red]")

    try:
        while True:
            try:
                line = prompt_session.prompt("> ").strip()
            except KeyboardInterrupt:
                console.print()
                continue
            except EOFError:
                break

            if not line:
                continue
            if line.lower() in EXIT_COMMANDS:
                break
            if line.startswith("/"):
                handle_slash(line, ctx)
                continue

            line = expand_mentions(line, config.workspace)
            messages.append({"role": "user", "content": line})

            try:
                run_turn(
                    client, config, ctx["registry"], messages, session, interactive=True
                )
            except KeyboardInterrupt:
                console.print("\n[dim](interrupted)[/dim]")
                if messages and messages[-1].get("role") == "user":
                    messages.pop()
            except Exception as err:  # noqa: BLE001
                console.print(f"\n[red]❌ Error: {err}[/red]")
                if messages and messages[-1].get("role") == "user":
                    messages.pop()

    finally:
        save_session(config.history_path, messages)

    console.print()
    print_cost_summary(session, config)
    console.print("[cyan]JARVIS: Goodbye! 👋[/cyan]")


if __name__ == "__main__":
    main()
