"""Tests for the local scheduler (job timing, persistence, built-in tasks)."""

from datetime import datetime

from orion import scheduler
from orion.obsidian import Vault


def test_due_respects_time():
    job = scheduler.Job(name="n", task="daily_note", at="20:00")
    assert job.due(datetime(2026, 1, 1, 19, 59)) is False
    assert job.due(datetime(2026, 1, 1, 20, 0)) is True
    assert job.due(datetime(2026, 1, 1, 23, 30)) is True


def test_due_skips_when_run_today_or_disabled():
    ran = scheduler.Job(name="n", task="daily_note", at="08:00", last_run="2026-01-01")
    assert ran.due(datetime(2026, 1, 1, 9, 0)) is False
    off = scheduler.Job(name="n", task="daily_note", at="08:00", enabled=False)
    assert off.due(datetime(2026, 1, 1, 9, 0)) is False


def test_due_with_bad_time_is_false():
    job = scheduler.Job(name="n", task="daily_note", at="oops")
    assert job.due(datetime(2026, 1, 1, 9, 0)) is False


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "schedule.json"
    jobs = [
        scheduler.Job(name="morning", task="daily_note", at="08:00"),
        scheduler.Job(name="evening", task="vault_tidy", at="20:00", enabled=False),
    ]
    scheduler.save_jobs(jobs, path)
    assert scheduler.load_jobs(path) == jobs


def test_load_missing_or_broken_is_empty(tmp_path):
    assert scheduler.load_jobs(tmp_path / "none.json") == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert scheduler.load_jobs(bad) == []


def test_daily_note_task_is_idempotent(tmp_path):
    vault = Vault(tmp_path)
    first = scheduler.task_daily_note(vault)
    assert first.startswith("created")
    assert scheduler.task_daily_note(vault).startswith("daily note already exists")


def test_vault_tidy_reports_inbox(tmp_path):
    vault = Vault(tmp_path)
    vault.create("Inbox/note.md", "hi")
    assert "1 note" in scheduler.task_vault_tidy(vault)


def test_run_due_marks_last_run_and_is_once_per_day(tmp_path):
    vault = Vault(tmp_path)
    job = scheduler.Job(name="d", task="daily_note", at="00:00")

    ran = scheduler.run_due([job], vault, now=datetime(2026, 1, 2, 10, 0))
    assert ran and ran[0][0] == "d"
    assert job.last_run == "2026-01-02"

    assert scheduler.run_due([job], vault, now=datetime(2026, 1, 2, 11, 0)) == []
    assert scheduler.run_due([job], vault, now=datetime(2026, 1, 3, 10, 0))


def test_run_job_unknown_task_is_reported(tmp_path):
    vault = Vault(tmp_path)
    job = scheduler.Job(name="x", task="does_not_exist", at="00:00")
    assert "unknown task" in scheduler.run_job(job, vault)


def test_loop_runs_due_jobs(tmp_path):
    vault = Vault(tmp_path)
    jobs = [scheduler.Job(name="d", task="daily_note", at="00:00")]
    seen: list[tuple[str, str]] = []

    scheduler.loop(
        jobs,
        vault,
        interval=0,
        on_run=lambda name, result: seen.append((name, result)),
        max_ticks=1,
    )

    assert seen and seen[0][0] == "d"
