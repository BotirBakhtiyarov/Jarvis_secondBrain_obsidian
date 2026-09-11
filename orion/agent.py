"""Agent mode: multi-step plans.

``Plan`` holds the current plan; ``PlanTool`` lets the model create and
update it step by step. The UI renders it as a table.
"""

from orion.tools import Tool

VALID_STATUSES = ("pending", "in_progress", "done")


class Plan:
    def __init__(self):
        self.steps: list[dict] = []

    def update(self, steps) -> list[dict]:
        clean = []
        for step in steps:
            if isinstance(step, dict):
                clean.append(
                    {
                        "title": str(step.get("title", "")).strip(),
                        "status": step.get("status", "pending")
                        if step.get("status") in VALID_STATUSES
                        else "pending",
                    }
                )
            else:
                clean.append({"title": str(step).strip(), "status": "pending"})
        self.steps = clean
        return self.steps


class PlanTool(Tool):
    def __init__(self, plan: Plan):
        super().__init__(
            name="plan",
            description=(
                "Create or update a step-by-step plan for a complex, "
                "multi-step task. Call this BEFORE starting a big task, "
                "then call it again after each step to mark it done and the "
                "next one in_progress. Each step has a short title and a "
                "status: pending, in_progress or done. Keep plans small "
                "(3-8 steps)."
            ),
            parameters={
                "steps": {
                    "type": "array",
                    "description": "Ordered list of steps",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Short step title"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "done"],
                            },
                        },
                        "required": ["title"],
                    },
                }
            },
            required=["steps"],
        )
        self.plan = plan

    def execute(self, steps):
        return {"plan": self.plan.update(steps)}
