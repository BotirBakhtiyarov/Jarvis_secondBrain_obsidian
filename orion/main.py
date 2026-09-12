import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PromptStyle
from rich.table import Table

from orion import i18n, ui
from orion.agent import Plan, PlanTool
from orion.config import Config, load_config
from orion.llm import chat_once, chat_stream
from orion.mcp import close_all as mcp_close_all
from orion.memory import (
    list_sessions,
    load_latest,
    load_session,
    save_session,
)
from orion.obsidian import open_vault
from orion.plugins import load_plugins
from orion.prompts import SYSTEM_PROMPT
from orion.providers import PROVIDERS, get_provider, resolve_api_key
from orion.tools import ToolRegistry
from orion.ui import console

VERSION = "0.10.0"

EXIT_COMMANDS = {"exit", "quit", "q", "/exit", "/quit"}

SENSITIVE_TOOLS = {"run_command", "screenshot", "git_commit", "git_create_pr"}

SLASH_COMMANDS = [
    "help",
    "clear",
    "model",
    "goal",
    "plan",
    "cost",
    "status",
    "memory",
    "compact",
    "add-dir",
    "review",
    "init",
    "permissions",
    "resume",
    "tools",
    "show",
    "think",
    "config",
    "exit",
    "version",
]

ORION_MD_TEMPLATE = """# ORION.md

This file holds project instructions for ORION. It is read automatically at
the start of every session.

## About this project
<!-- Briefly describe what this project does -->

## Coding standards
<!-- Preferred style, conventions and constraints -->

## Commands
<!-- How to run tests / builds -->
"""


def trim_history(messages: list[dict], max_history: int) -> list[dict]:
    """Trim to the last ``max_history`` messages, keeping system messages.

    Never splits a tool-call chain: if the cut lands on a ``tool`` message,
    it moves back to the start of the assistant ``tool_calls`` block.
    """

    if max_history <= 0 or len(messages) <= max_history + 1:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    tail = messages[len(system_msgs) :]
    if len(tail) <= max_history:
        return messages

    cut = len(tail) - max_history
    while cut > 0 and tail[cut].get("role") == "tool":
        cut -= 1
    return system_msgs + tail[cut:]


class Session:
    """Current session state: tokens, cost and permission mode."""

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
    """``/`` commands and ``@`` file paths autocomplete."""

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
    argv = list(argv)

    # `config` is parsed manually — a subparser would swallow the positional query.
    command = None
    config_init = False
    config_edit = False
    if argv and argv[0] == "config":
        command = "config"
        argv = argv[1:]
        config_init = "--init" in argv
        config_edit = "--edit" in argv
        argv = [a for a in argv if a not in ("--init", "--edit")]

    parser = argparse.ArgumentParser(
        prog="orion",
        description="ORION — Operational Reasoning, Intelligence & Orchestration Network",
    )
    parser.add_argument("query", nargs="*", help="initial query (starts an interactive session)")
    parser.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="print the answer and exit (non-interactive)",
    )
    parser.add_argument(
        "-c",
        "--continue",
        dest="resume_last",
        action="store_true",
        help="continue the latest session",
    )
    parser.add_argument(
        "-r",
        "--resume",
        metavar="ID",
        help="resume a session by id",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="show version",
    )
    parser.add_argument("--model", help="override the DeepSeek model")
    parser.add_argument("--vault", help="override the Obsidian vault path")
    parser.add_argument("--workspace", help="override the workspace (projects) root")
    parser.add_argument(
        "--dangerously-skip-permissions",
        action="store_true",
        help="skip permission prompts for commands",
    )

    args = parser.parse_args(argv)
    args.command = command
    args.config_init = config_init
    args.config_edit = config_edit
    return args


def build_system(config: Config) -> str:
    system = SYSTEM_PROMPT

    now = datetime.now().astimezone()
    system += (
        "\n\nCurrent date and time: "
        f"{now.strftime('%Y-%m-%d (%A) %H:%M:%S')} "
        f"(UTC{now.strftime('%z')}, {now.tzname()})\n"
        "For any date- or time-sensitive task, call the `get_time` tool "
        "to obtain the precise current time instead of guessing.\n"
    )

    system += (
        f"\nInterface language: {i18n.get_language()}. "
        "Reply in the language the user writes in — it may differ from the "
        "interface language.\n"
    )

    orion_md = config.workspace / "ORION.md"
    if orion_md.exists():
        try:
            content = orion_md.read_text(encoding="utf-8", errors="ignore")
            system += "\n\n=== PROJECT INSTRUCTIONS (ORION.md) ===\n" + content
        except OSError:
            pass
    return system


def expand_mentions(text: str, workspace: Path) -> str:
    """Replace ``@path`` mentions with the file's content (if it exists)."""

    def repl(match):
        rel = match.group(1)
        p = (workspace / rel).resolve()
        try:
            if p.is_file() and (workspace in p.parents or p == workspace):
                content = p.read_text(encoding="utf-8", errors="ignore")
                return f'\n<file path="{rel}">\n{content}\n</file>\n'
        except OSError:
            pass
        return match.group(0)

    return re.sub(r"@([^\s@]+)", repl, text)


def confirm_command(label: str, session: Session) -> bool:
    console.print(f"[yellow]{i18n.t('allow')}[/yellow] [bold]{label}[/bold]")
    while True:
        ans = console.input(f"[dim]  {i18n.t('confirm_hint')} [/dim]").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        if ans in ("always", "a"):
            session.bypass = True
            return True


def run_turn(client, config, registry, messages, session, interactive=True):
    for _ in range(25):
        view = ui.TurnView(interactive)
        if interactive:
            spinner = console.status(i18n.t("thinking"), spinner="dots")
            spinner.start()
            view.attach_spinner(spinner)

        try:
            text, tool_calls, _, usage, _reasoning = chat_stream(
                client,
                config.model,
                trim_history(messages, config.max_history),
                registry.schema(),
                on_text=view.text_delta,
                on_reasoning=view.reasoning_delta,
            )
        except BaseException:
            view.cleanup()
            raise

        view.end_turn()
        session.add_usage(usage)

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

        # --- Parallel tool execution ---
        results = _execute_tools_parallel(tool_calls, registry, session, interactive)

        for tc, result in zip(tool_calls, results, strict=True):
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )


def _execute_tools_parallel(tool_calls, registry, session, interactive):
    """Execute tool calls, running independent ones in parallel.

    Sensitive tools (run_command, git_commit, ...) always run sequentially
    and require confirmation. Read-only tools run in parallel via a thread
    pool for speed.
    """

    from concurrent.futures import ThreadPoolExecutor, as_completed

    sensitive = SENSITIVE_TOOLS
    ordered_results: list[dict | None] = [None] * len(tool_calls)

    def _run_one(idx, name, arguments):
        if interactive:
            ui.print_tool_call(name, arguments)
        else:
            print(f"⏺ {name} {json.dumps(arguments, ensure_ascii=False)}")
        if name in sensitive and interactive and not session.bypass:
            label = (
                arguments.get("command", "")
                if name == "run_command"
                else json.dumps(arguments, ensure_ascii=False)
            )
            if not confirm_command(label, session):
                return idx, {"error": i18n.t("denied")}
        return idx, registry.execute(name, arguments)

    # First pass: run sensitive tools sequentially, collect parallel candidates.
    parallel_jobs = []
    for idx, tc in enumerate(tool_calls):
        name = tc["function"]["name"]
        try:
            arguments = json.loads(tc["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            arguments = {}
        if name in sensitive:
            _, result = _run_one(idx, name, arguments)
            ordered_results[idx] = result
            if interactive:
                ui.print_tool_result(result)
        else:
            parallel_jobs.append((idx, name, arguments))

    # Second pass: run read-only tools in parallel.
    if parallel_jobs:
        with ThreadPoolExecutor(max_workers=min(4, len(parallel_jobs))) as pool:
            futures = {
                pool.submit(_run_one, idx, name, arguments): idx
                for idx, name, arguments in parallel_jobs
            }
            for future in as_completed(futures):
                idx, result = future.result()
                ordered_results[idx] = result
                if interactive:
                    ui.print_tool_result(result)

    return ordered_results


# Slash command handlers


def cmd_help(ctx):
    from rich.table import Table

    console.print()
    table = Table(title=i18n.t("help_title"), border_style="cyan")
    table.add_column("Command", style="green", no_wrap=True)
    table.add_column("What it does")

    for c, key in [
        ("/help", "help.help"),
        ("/clear", "help.clear"),
        ("/model [name]", "help.model"),
        ("/cost", "help.cost"),
        ("/status", "help.status"),
        ("/memory", "help.memory"),
        ("/compact", "help.compact"),
        ("/add-dir <path>", "help.add_dir"),
        ("/review", "help.review"),
        ("/init", "help.init"),
        ("/config [init|edit]", "help.config"),
        ("/permissions [on|bypass]", "help.permissions"),
        ("/resume [id]", "help.resume"),
        ("/tools", "help.tools"),
        ("/show", "help.show"),
        ("/think", "help.think"),
        ("/exit", "help.exit"),
        ("/version", "help.version"),
    ]:
        table.add_row(c, i18n.t(key))

    console.print(table)
    console.print(f"[dim]{i18n.t('help.hint')}[/dim]\n")


def cmd_clear(ctx):
    ctx["messages"][:] = [ctx["messages"][0]]
    console.print(f"[green]{i18n.t('clear_done')}[/green]")


def cmd_model(ctx):
    """Show the provider/model table, or switch model and/or provider.

    ``/model <name>`` switches the model on the current provider;
    ``/model <provider>:<name>`` switches both (the provider key must be set).
    """
    args = ctx["args"]
    config = ctx["config"]

    if args:
        provider_name, model = _split_model_arg(args[0])
        if provider_name is not None and provider_name != config.provider:
            try:
                prov = get_provider(provider_name)
            except ValueError as err:
                console.print(f"[red]{err}[/red]")
                return
            key = resolve_api_key(prov)
            if not key:
                console.print(
                    f"[red]{i18n.t('provider_key_missing', env=prov.key_env, provider=prov.name)}[/red]"
                )
                return
            config.provider = prov.name
            config.base_url = prov.base_url
            config.api_key = key
            config.input_price = prov.input_price
            config.output_price = prov.output_price
            ctx["client"] = OpenAI(api_key=key, base_url=prov.base_url)
            console.print(f"[green]{i18n.t('provider_set', name=prov.name)}[/green]")
        config.model = model
        console.print(f"[green]{i18n.t('model_set', model=config.model)}[/green]")
        return

    console.print(f"[cyan]{i18n.t('model_is', model=config.model)}[/cyan]")
    table = Table(title=i18n.t("providers_title"), border_style="cyan")
    table.add_column(i18n.t("provider"), style="green", no_wrap=True)
    table.add_column("Default model")
    table.add_column("Cost $/M (in/out)")
    table.add_column("Key")
    for name, prov in PROVIDERS.items():
        marker = f" {i18n.t('current')}" if name == config.provider else ""
        key_state = i18n.t("local") if prov.local else ("set" if resolve_api_key(prov) else "—")
        table.add_row(
            name + marker, prov.default_model, f"{prov.input_price}/{prov.output_price}", key_state
        )
    console.print(table)
    console.print(f"[dim]{i18n.t('model_switch_hint')}[/dim]")


def _split_model_arg(arg: str) -> tuple[str | None, str]:
    """Split ``<provider>:<model>``; plain model names return (None, arg)."""
    if ":" in arg:
        provider, _, rest = arg.partition(":")
        if provider.lower() in PROVIDERS:
            return provider.lower(), rest
    return None, arg


def cmd_goal(ctx):
    """Seed a plan from a natural-language goal.

    ``/goal step one; step two; step three`` splits on ``;`` so a multi-step
    plan can be drafted instantly; the model then refines it with the ``plan``
    tool as it makes progress.
    """
    args = ctx.get("args") or []
    text = " ".join(args).strip()
    if not text:
        console.print(f"[yellow]{i18n.t('goal_empty')}[/yellow]")
        return

    steps = []
    for part in re.split(r"\s*;\s*", text):
        part = part.strip()
        if not part:
            continue
        status = "in_progress" if not steps else "pending"
        steps.append({"title": part, "status": status})

    if not steps:
        console.print(f"[yellow]{i18n.t('goal_empty')}[/yellow]")
        return

    ctx["plan"].update(steps)
    console.print(f"[green]{i18n.t('goal_seeded', n=len(steps))}[/green]")
    ui.print_plan(ctx["plan"].steps)


def cmd_plan(ctx):
    """Inspect or edit the current plan.

    * ``/plan``            -- print the plan
    * ``/plan mark <i> <s>`` -- set step #i to status <s>
    * ``/plan reset``       -- start a fresh plan
    """
    plan: Plan = ctx["plan"]
    args = (ctx.get("args") or [])[1:]

    if not args:
        ui.print_plan(plan.steps)
        return

    sub = args[0]
    if sub == "reset":
        plan.reset()
        console.print("[green]✓ Plan reset.[/green]")
        return

    if sub == "mark" and len(args) >= 3:
        try:
            idx = int(args[1])
        except ValueError:
            console.print("[yellow]Usage: /plan mark <index> <status>[/yellow]")
            return
        try:
            plan.mark(idx, args[2])
        except (ValueError, IndexError) as err:
            console.print(f"[yellow]{err}[/yellow]")
            return
        ui.print_plan(plan.steps)
        return

    console.print("[yellow]Usage: /plan [-- mark <i> <status> | reset][/yellow]")


def cmd_cost(ctx):
    s = ctx["session"]
    c = ctx["config"]
    console.print(
        f"[cyan]{i18n.t('tokens_line', i=ui.format_number(s.input_tokens), o=ui.format_number(s.output_tokens), t=ui.format_number(s.total_tokens))}[/cyan]"
    )
    cost = f"{s.cost(c):.4f}"
    console.print(
        f"[cyan]{i18n.t('cost_line', c=cost)}[/cyan] "
        f"[dim]{i18n.t('cost_rates', i=c.input_price, o=c.output_price)}[/dim]"
    )


def cmd_status(ctx):
    c = ctx["config"]
    r = ctx["registry"]
    mode = i18n.t("perm_bypass") if ctx["session"].bypass else i18n.t("perm_ask")
    ui.print_key_value(
        [
            ("Provider", c.provider),
            ("Model", c.model),
            ("Vault", str(c.obsidian_vault)),
            ("Workspace", str(c.workspace)),
            ("History", str(c.history_path)),
            (i18n.t("language"), i18n.get_language()),
            ("Tools", ", ".join(r.names())),
            (i18n.t("permission_mode"), mode),
        ],
        title=i18n.t("status_title"),
    )


def cmd_memory(ctx):
    c = ctx["config"]
    vault = open_vault(c)
    res = vault.list_notes(limit=15)
    if "error" in res:
        console.print(f"[red]{res['error']}[/red]")
        return
    console.print(f"[cyan]{i18n.t('recent_notes', n=res['total'])}[/cyan]")
    for n in res["notes"]:
        console.print(f"  [dim]{n}[/dim]")
    console.print(f"[dim]{i18n.t('memory_rules')}[/dim]")


def cmd_compact(ctx):
    c = ctx["config"]
    messages = ctx["messages"]
    if len(messages) <= 3:
        console.print(f"[dim]{i18n.t('nothing_to_compact')}[/dim]")
        return

    with console.status(f"[cyan]{i18n.t('compacting')}[/cyan]"):
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
    console.print(f"[green]{i18n.t('compacted')}[/green]")


def cmd_add_dir(ctx):
    c = ctx["config"]
    if not ctx["args"]:
        console.print(f"[red]{i18n.t('usage_add_dir')}[/red]")
        return
    path = Path(ctx["args"][0]).expanduser().resolve()
    if not path.is_dir():
        console.print(f"[red]{i18n.t('not_a_directory', path=path)}[/red]")
        return
    c.workspace = path
    ctx["registry"] = rebuild_registry(c)
    ctx["completer"].set_workspace(path)
    console.print(f"[green]{i18n.t('workspace_set', path=path)}[/green]")


def cmd_review(ctx):
    ws = ctx["config"].workspace
    if not (ws / ".git").exists():
        console.print(f"[yellow]{i18n.t('not_git_repo', path=ws)}[/yellow]")
        return

    status = subprocess.run(
        ["git", "status", "--short"], cwd=str(ws), capture_output=True, text=True
    )
    diff = subprocess.run(["git", "diff", "--stat"], cwd=str(ws), capture_output=True, text=True)
    console.print(f"[cyan]{i18n.t('git_status')}[/cyan]")
    console.print(status.stdout or f"({i18n.t('git_clean')})", markup=False)
    console.print(f"[cyan]{i18n.t('git_diff_stat')}[/cyan]")
    console.print(diff.stdout or f"({i18n.t('no_changes')})", markup=False)


def cmd_init(ctx):
    path = ctx["config"].workspace / "ORION.md"
    if path.exists():
        console.print(f"[dim]{i18n.t('already_exists', path=path)}[/dim]")
        return
    path.write_text(ORION_MD_TEMPLATE, encoding="utf-8")
    console.print(f"[green]{i18n.t('created', path=path)}[/green]")


def cmd_permissions(ctx):
    s = ctx["session"]
    if ctx["args"] and ctx["args"][0] in ("bypass", "skip", "off"):
        s.bypass = True
    elif ctx["args"] and ctx["args"][0] in ("on", "ask", "default"):
        s.bypass = False
    mode = i18n.t("perm_bypass") if s.bypass else i18n.t("perm_ask")
    console.print(f"[cyan]{i18n.t('permission_mode')}:[/cyan] {mode}")


def cmd_resume(ctx):
    sessions = list_sessions(ctx["config"].history_path)
    if not sessions:
        console.print(f"[dim]{i18n.t('no_saved_sessions')}[/dim]")
        return

    if ctx["args"]:
        hist = load_session(ctx["config"].history_path, ctx["args"][0])
        if hist is None:
            console.print(f"[red]{i18n.t('session_not_found')}[/red]")
            return
        ctx["messages"][:] = [ctx["messages"][0], *hist]
        console.print(f"[green]{i18n.t('resumed')}[/green]")
        return

    console.print(f"[cyan]{i18n.t('saved_sessions')}[/cyan]")
    for s in sessions:
        console.print(
            f"  [green]{s['id']}[/green]  {s['first']}  [dim]({s['messages']} msgs)[/dim]"
        )
    console.print(f"[dim]{i18n.t('resume_hint')}[/dim]")


def cmd_tools(ctx):
    from rich.table import Table

    console.print()
    table = Table(title=i18n.t("available_tools"), border_style="cyan")
    table.add_column("Tool", style="green", no_wrap=True)
    table.add_column("Description")
    for name, summary in ctx["registry"].describe():
        table.add_row(name, summary)
    console.print(table)
    console.print()


def cmd_version(ctx):
    console.print(i18n.t("version", version=VERSION))


def cmd_show(ctx):
    ui.show_remembered()


def cmd_think(ctx):
    ui.show_thinking()


# Config command (slash + `orion config` CLI)


def _find_env_example() -> Path | None:
    candidates = [
        Path.cwd() / ".env.example",
        Path(__file__).resolve().parent.parent / ".env.example",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def show_config_table(config):
    # CLI calls also set the interface language.
    i18n.set_language(config.language)

    ui.print_key_value(
        [
            ("Provider", config.provider),
            ("Model", config.model),
            ("Base URL", config.base_url),
            ("Vault", str(config.obsidian_vault)),
            ("Workspace", str(config.workspace)),
            ("History", str(config.history_path)),
            ("Max history", str(config.max_history)),
            (i18n.t("language"), i18n.get_language()),
            ("Input price", f"${config.input_price}/M"),
            ("Output price", f"${config.output_price}/M"),
            ("DeepSeek key", "set" if config.api_key else "MISSING"),
            ("Tavily key", "set" if config.tavily_api_key else "not set"),
        ],
        title=i18n.t("config_title"),
    )


def run_config_init():
    env = Path.cwd() / ".env"
    if env.exists():
        console.print(f"[yellow]{i18n.t('env_exists', path=env)}[/yellow]")
        return

    template = _find_env_example()
    if template is None:
        console.print(f"[red]{i18n.t('no_env_example')}[/red]")
        return

    env.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]{i18n.t('created_from', path=env, name=template.name)}[/green]")
    console.print(f"[dim]{i18n.t('fill_env')}[/dim]")


def run_config_edit():
    env = Path.cwd() / ".env"
    if not env.exists():
        console.print(f"[yellow]{i18n.t('env_not_found')}[/yellow]")
        return

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    console.print(f"[dim]{i18n.t('opening_env', path=env, editor=editor)}[/dim]")
    subprocess.call([editor, str(env)])


def run_config_command(args):
    if getattr(args, "config_init", False):
        run_config_init()
    elif getattr(args, "config_edit", False):
        run_config_edit()
    else:
        try:
            config = load_config({})
        except ValueError:
            config = None
        if config is None:
            console.print(f"[yellow]{i18n.t('vault_not_set')}[/yellow]")
            return
        show_config_table(config)


def cmd_config(ctx):
    args = ctx["args"]
    if args and args[0] in ("init", "--init"):
        run_config_init()
    elif args and args[0] in ("edit", "--edit"):
        run_config_edit()
    else:
        show_config_table(ctx["config"])


COMMAND_HANDLERS = {
    "help": cmd_help,
    "clear": cmd_clear,
    "model": cmd_model,
    "goal": cmd_goal,
    "plan": cmd_plan,
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
    "show": cmd_show,
    "think": cmd_think,
    "config": cmd_config,
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
        console.print(f"[yellow]{i18n.t('unknown_command', name=name)}[/yellow]")


def rebuild_registry(config):
    registry = ToolRegistry()
    load_plugins(registry, config)
    return registry


def print_cost_summary(session: Session, config):
    cost = f"{session.cost(config):.4f}"
    console.print(
        f"[dim]{i18n.t('cost_summary', t=ui.format_number(session.total_tokens), c=cost)}[/dim]"
    )


def auto_memory(client, config, session, messages):
    """Summarize the session at exit and store key facts in Obsidian."""

    if not any(m.get("role") == "assistant" and m.get("content") for m in messages):
        return None

    transcript = []
    for m in messages[-20:]:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if role == "tool":
            content = content[:200]
        if not content:
            continue
        transcript.append(f"{role.upper()}: {content[:800]}")

    if not transcript:
        return None

    prompt = (
        "You are a memory assistant. Summarize the conversation and extract "
        "durable, important facts (user preferences, decisions, goals, tasks, "
        "things learned). Ignore small talk and never include secrets.\n\n"
        "Return ONLY Markdown with exactly two sections:\n"
        "## Summary\n2-4 sentences.\n\n## Facts\n- one fact per bullet.\n\n"
        "Conversation:\n" + "\n\n".join(transcript)
    )

    try:
        text, usage = chat_once(client, config.model, [{"role": "system", "content": prompt}])
    except Exception:  # noqa: BLE001
        return None

    session.add_usage(usage)
    if not text or not text.strip():
        return None

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    note_path = f"Sessions/{stamp}.md"
    vault = open_vault(config)
    body = vault.build_frontmatter(f"Session {stamp}", ["session"])
    body += text.strip() + "\n"

    res = vault.create(note_path, body)
    if not res.get("success"):
        return None
    return note_path


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.version:
        print(i18n.t("version", version=VERSION))
        return

    if args.command == "config":
        run_config_command(args)
        return

    try:
        config = load_config(
            {"model": args.model, "vault": args.vault, "workspace": args.workspace}
        )
    except ValueError as err:
        console.print(f"[bold red]{i18n.t('error_prefix', msg=err)}[/bold red]")
        raise SystemExit(1) from err

    if not config.api_key:
        prov = get_provider(config.provider)
        console.print(
            f"[bold red]❌ {i18n.t('provider_key_missing', env=prov.key_env, provider=prov.name)}[/bold red]"
        )
        raise SystemExit(1)

    # English by default; ORION_LANG=auto follows the user's language.
    i18n.set_language(config.language)

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    registry = ToolRegistry()
    load_plugins(registry, config)

    config.client = client
    config.registry = registry

    plan = Plan()
    registry.register(PlanTool(plan))

    session = Session(config)
    session.bypass = args.dangerously_skip_permissions

    initial_query = " ".join(args.query or []).strip()

    if args.print and not initial_query and not sys.stdin.isatty():
        initial_query = sys.stdin.read().strip()

    if config.language == "auto" and initial_query:
        detected = i18n.detect_language(initial_query)
        if detected:
            i18n.set_language(detected)

    messages = [{"role": "system", "content": build_system(config)}]

    if args.resume:
        hist = load_session(config.history_path, args.resume)
        if hist is None:
            console.print(f"[red]{i18n.t('session_not_found_id', id=args.resume)}[/red]")
            raise SystemExit(1)
        messages.extend(hist)
    elif args.resume_last:
        hist = load_latest(config.history_path)
        if hist:
            messages.extend(hist)
        else:
            console.print(f"[dim]{i18n.t('no_previous')}[/dim]")

    if args.print:
        if initial_query:
            messages.append({"role": "user", "content": initial_query})
        try:
            run_turn(client, config, registry, messages, session, interactive=False)
        except KeyboardInterrupt:
            pass
        except Exception as err:  # noqa: BLE001
            console.print(f"[red]{err}[/red]")
        save_session(config.history_path, messages)
        mcp_close_all()
        return

    ui.print_banner(VERSION)
    console.print(
        f"[dim]{i18n.t('banner_line', model=config.model, workspace=config.workspace)}[/dim]"
    )
    console.print(f"[dim]{i18n.t('banner_hint')}[/dim]")

    completer = JarvisCompleter()
    completer.set_workspace(config.workspace)
    input_history = Path(config.history_path).parent / "input_history.txt"
    input_history.parent.mkdir(parents=True, exist_ok=True)
    prompt_session = PromptSession(
        history=FileHistory(str(input_history)),
        completer=completer,
        style=PromptStyle.from_dict({"box": "ansibrightgreen"}),
    )

    ctx = {
        "config": config,
        "client": client,
        "registry": registry,
        "session": session,
        "messages": messages,
        "completer": completer,
        "plan": plan,
    }

    if initial_query:
        messages.append({"role": "user", "content": initial_query})
        ui.print_user_box(initial_query)
        try:
            run_turn(ctx["client"], config, ctx["registry"], messages, session, interactive=True)
        except Exception as err:  # noqa: BLE001
            console.print(f"\n[red]{i18n.t('error_prefix', msg=err)}[/red]")
        if plan.steps:
            ui.print_plan(plan.steps)

    try:
        while True:
            top, prefix, bottom = ui.user_box_parts()
            try:
                line = prompt_session.prompt([("class:box", top + "\n" + prefix)]).strip()
            except KeyboardInterrupt:
                console.print()
                continue
            except EOFError:
                console.print(f"[green]{bottom}[/green]")
                break
            console.print(f"[green]{bottom}[/green]")

            if not line:
                continue
            if line.lower() in EXIT_COMMANDS:
                break
            if line.startswith("/"):
                handle_slash(line, ctx)
                continue

            line = expand_mentions(line, config.workspace)

            # In auto mode, follow the user's language.
            if config.language == "auto":
                detected = i18n.detect_language(line)
                if detected:
                    i18n.set_language(detected)

            messages.append({"role": "user", "content": line})

            try:
                run_turn(
                    ctx["client"], config, ctx["registry"], messages, session, interactive=True
                )
            except KeyboardInterrupt:
                console.print(f"\n[dim]{i18n.t('interrupted')}[/dim]")
                if messages and messages[-1].get("role") == "user":
                    messages.pop()
            except Exception as err:  # noqa: BLE001
                console.print(f"\n[red]{i18n.t('error_prefix', msg=err)}[/red]")
                if messages and messages[-1].get("role") == "user":
                    messages.pop()
            if plan.steps:
                ui.print_plan(plan.steps)

    finally:
        save_session(config.history_path, messages)
        mcp_close_all()
        if os.environ.get("ORION_AUTO_MEMORY", "1") != "0":
            try:
                saved = auto_memory(client, config, session, messages)
                if saved:
                    console.print(f"[dim]{i18n.t('session_summary_saved', path=saved)}[/dim]")
            except Exception:  # noqa: BLE001
                pass

    console.print()
    print_cost_summary(session, config)
    console.print(f"[cyan]{i18n.t('goodbye')}[/cyan]")


if __name__ == "__main__":
    main()
