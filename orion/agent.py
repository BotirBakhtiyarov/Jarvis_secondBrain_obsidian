"""Agent mode: multi-step plans.

``Plan`` holds the current plan; ``PlanTool`` lets the model create and
update it step by step. The UI renders it as a table.
"""

from orion.tools import Tool

VALID_STATUSES = ("pending", "in_progress", "done", "failed")
FAILED = "failed"


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

    def reset(self) -> None:
        """Drop every step (starts a new plan)."""
        self.steps = []

    def mark(self, index: int, status: str) -> str:
        """Mark a single step by position; raises on bad index/status."""
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        if not 0 <= index < len(self.steps):
            raise IndexError(f"step #{index} out of range (0..{len(self.steps) - 1})")
        self.steps[index]["status"] = status
        return status

    # --- (de)serialization for session persistence ---
    def to_dict(self) -> list[dict]:
        """Return a JSON-safe copy of the steps."""
        return [dict(s) for s in self.steps]

    def from_dict(self, data: list[dict]) -> None:
        """Restore steps from a list of dicts (no validation)."""
        self.steps = [
            {
                "title": str(s.get("title", "")).strip(),
                "status": s.get("status", "pending")
                if s.get("status") in VALID_STATUSES
                else "pending",
            }
            for s in data
        ]


class PlanTool(Tool):
    def __init__(self, plan: Plan):
        super().__init__(
            name="plan",
            description=(
                "Create or update a step-by-step plan for a complex, "
                "multi-step task. Call this BEFORE starting a big task, "
                "then call it again after each step to mark it done and the "
                "next one in_progress. Each step has a short title and a "
                "status: pending, in_progress, done or failed. Mark a step "
                "failed if it hit an error, then retry and set it done on "
                "success. Keep plans small (3-8 steps)."
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
                                "enum": list(VALID_STATUSES),
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
