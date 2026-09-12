"""Agent mode: multi-step plans.

``Plan`` holds the current plan; ``PlanTool`` lets the model create and
update it step by step. The UI renders it as a table.
"""

import json

from orion.llm import chat_stream
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


class SubAgent:
    """Run a focused sub-task in an isolated message history.

    The sub-agent gets its own fresh message list (no access to the main
    conversation), runs a short agent loop with a restricted tool set, and
    returns a concise summary the main agent can use.
    """

    def __init__(self, client, config, registry, max_turns: int = 6):
        self.client = client
        self.config = config
        self.registry = registry
        self.max_turns = max_turns

    def run(self, task: str, allowed_tools: list[str] | None = None) -> str:
        """Execute ``task`` and return a plain-text summary of the result."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a focused sub-agent. Complete the given task using "
                    "the available tools. Be concise and direct. When done, "
                    "reply with a short summary of what you accomplished and "
                    "any relevant output. Do NOT continue past the task."
                ),
            },
            {"role": "user", "content": task},
        ]

        registry = self.registry
        if allowed_tools:
            registry = _ToolFilter(self.registry, allowed_tools)

        for _ in range(self.max_turns):
            text, tool_calls, _, usage, _ = chat_stream(
                self.client,
                self.config.model,
                messages,
                registry.schema(),
            )
            if not tool_calls:
                return (text or "(no output)").strip()

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
                result = registry.execute(name, arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
        return "(sub-agent reached turn limit without finishing)"


class _ToolFilter:
    """Proxy registry that exposes only a subset of tools."""

    def __init__(self, registry, allowed: list[str]):
        self._registry = registry
        self._allowed = set(allowed)

    def schema(self) -> list[dict]:
        return [s for s in self._registry.schema() if s["function"]["name"] in self._allowed]

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in self._allowed:
            return {"error": f"tool '{name}' is not allowed in this sub-agent"}
        return self._registry.execute(name, arguments)


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
