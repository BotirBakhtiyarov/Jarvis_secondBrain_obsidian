"""Tiny local scheduler for recurring vault tasks.

Jobs live in ``~/.orion/schedule.json`` and only run while ORION is open:
``orion schedule run`` runs whatever is due, and ``orion schedule run --loop``
keeps checking in the foreground. There is no OS-level daemon by design —
nothing runs behind your back.

The built-in tasks are deterministic vault operations (no model calls), so a
scheduled run never spends tokens or needs an API key.
"""

import json
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

DEFAULT_PATH = Path.home() / ".orion" / "schedule.json"


@dataclass
class Job:
    name: str
    task: str
    at: str = "20:00"
    enabled: bool = True
    last_run: str = ""

    def due(self, now: datetime) -> bool:
        """True when the job should run at ``now`` (at most once per day)."""
        if not self.enabled:
            return False
        if self.last_run == now.date().isoformat():
            return False
        try:
            hour, minute = (int(part) for part in self.at.split(":"))
        except (ValueError, AttributeError):
            return False
        return (now.hour, now.minute) >= (hour, minute)


def load_jobs(path: Path | None = None) -> list[Job]:
    """Read the job list; a missing or broken file yields an empty list."""
    path = Path(path) if path else DEFAULT_PATH
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    jobs: list[Job] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        fields = {k: v for k, v in item.items() if k in Job.__dataclass_fields__}
        if "name" in fields and "task" in fields:
            jobs.append(Job(**fields))
    return jobs


def save_jobs(jobs: list[Job], path: Path | None = None) -> Path:
    path = Path(path) if path else DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(j) for j in jobs], indent=2), encoding="utf-8")
    return path


# --- built-in tasks (deterministic, no model calls) ------------------------


def task_daily_note(vault) -> str:
    """Create today's daily note if it does not exist yet."""
    today = date.today().isoformat()
    rel = f"Daily/{today}.md"
    if vault.transport.exists(rel):
        return f"daily note already exists: {rel}"
    vault.create(rel, vault.build_frontmatter(f"Daily {today}", ["daily"]))
    return f"created {rel}"


def task_vault_tidy(vault) -> str:
    """Report notes waiting in the Inbox (non-destructive)."""
    inbox = vault.list_notes("Inbox")
    return f"inbox has {inbox['total']} note(s) to triage"


TASKS = {
    "daily_note": task_daily_note,
    "vault_tidy": task_vault_tidy,
}

TASK_DESCRIPTIONS = {
    "daily_note": "create today's daily note (Daily/YYYY-MM-DD.md) if missing",
    "vault_tidy": "report notes sitting in Inbox/ (non-destructive)",
}


def run_job(job: Job, vault) -> str:
    func = TASKS.get(job.task)
    if func is None:
        return f"unknown task: {job.task}"
    return func(vault)


def run_due(jobs: list[Job], vault, now: datetime | None = None) -> list[tuple[str, str]]:
    """Run every due job once, mark it run, and return ``(name, result)``."""
    now = now or datetime.now()
    ran: list[tuple[str, str]] = []
    for job in jobs:
        if job.due(now):
            result = run_job(job, vault)
            job.last_run = now.date().isoformat()
            ran.append((job.name, result))
    return ran


def loop(
    jobs: list[Job],
    vault,
    interval: int = 60,
    on_run=None,
    max_ticks: int | None = None,
) -> None:
    """Poll for due jobs (forever, or ``max_ticks`` times for tests)."""
    ticks = 0
    while max_ticks is None or ticks < max_ticks:
        for name, result in run_due(jobs, vault):
            save_jobs(jobs)
            if on_run:
                on_run(name, result)
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            break
        time.sleep(interval)
