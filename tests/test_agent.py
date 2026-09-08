from orion.agent import Plan, PlanTool


def test_plan_tool_updates_steps():
    plan = Plan()
    tool = PlanTool(plan)

    res = tool.execute(
        [
            {"title": "step one", "status": "done"},
            {"title": "step two", "status": "in_progress"},
            {"title": "step three", "status": "pending"},
        ]
    )

    assert res["plan"][0] == {"title": "step one", "status": "done"}
    assert len(plan.steps) == 3
    assert plan.steps[1]["status"] == "in_progress"


def test_plan_drops_invalid_status():
    plan = Plan()
    plan.update([{"title": "x", "status": "not-a-real-status"}])
    assert plan.steps[0]["status"] == "pending"


def test_plan_accepts_plain_strings():
    plan = Plan()
    plan.update(["do a thing", "do another"])
    assert plan.steps == [
        {"title": "do a thing", "status": "pending"},
        {"title": "do another", "status": "pending"},
    ]
