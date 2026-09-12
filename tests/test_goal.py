"""Tests for the goal-seeded plan engine (3-bosqich, slice 1).

Covers ``Plan.failed`` status, ``Plan.mark``/``reset`` helpers and the
``/goal`` slash command that seeds a plan from a ``;``-separated string.
"""

import pytest

from orion import i18n, ui
from orion.agent import FAILED, VALID_STATUSES, Plan
from orion.main import cmd_goal


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")


def _ctx(args=None):
    return {"args": args or [], "plan": Plan()}


def test_plan_accepts_failed_status():
    plan = Plan()
    plan.update([{"title": "a"}, {"title": "b", "status": "failed"}])
    assert plan.steps[0]["status"] == "pending"
    assert plan.steps[1]["status"] == "failed"
    assert FAILED in VALID_STATUSES


def test_plan_mark_done_and_failed():
    plan = Plan()
    plan.update([{"title": "a"}, {"title": "b"}, {"title": "c"}])
    plan.mark(0, "done")
    plan.mark(1, "failed")
    assert [s["status"] for s in plan.steps] == ["done", "failed", "pending"]


def test_plan_mark_invalid_status_raises():
    plan = Plan()
    plan.update([{"title": "a"}])
    with pytest.raises(ValueError):
        plan.mark(0, "bogus")


def test_plan_mark_out_of_range_raises():
    plan = Plan()
    plan.update([{"title": "a"}])
    with pytest.raises(IndexError):
        plan.mark(5, "done")


def test_plan_reset_clears():
    plan = Plan()
    plan.update([{"title": "a"}, {"title": "b"}])
    plan.reset()
    assert plan.steps == []


def test_cmd_goal_splits_on_semicolon():
    ctx = _ctx(["write tests; run lints; commit"])
    with ui.console.capture() as cap:
        cmd_goal(ctx)
    assert "Plan seeded with 3" in cap.get()
    steps = ctx["plan"].steps
    assert len(steps) == 3
    assert steps[0] == {"title": "write tests", "status": "in_progress"}
    assert steps[1] == {"title": "run lints", "status": "pending"}
    assert steps[2]["title"] == "commit"


def test_cmd_goal_no_args_prints_empty():
    ctx = _ctx([])
    with ui.console.capture() as cap:
        cmd_goal(ctx)
    assert "Usage" in cap.get()
    assert ctx["plan"].steps == []
