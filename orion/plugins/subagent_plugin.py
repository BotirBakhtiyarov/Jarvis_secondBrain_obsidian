"""Delegate a focused sub-task to a sub-agent with a restricted tool set."""

from orion.agent import SubAgent
from orion.tools import Tool


def register(registry, config):
    registry.register(DelegateTaskTool(config))


class DelegateTaskTool(Tool):
    """Spawn a sub-agent to handle a focused sub-task in isolation.

    The sub-agent gets its own fresh conversation (no access to the main
    history), runs a short loop with only the tools you allow, and returns
    a concise summary. Use this to keep the main context clean when a task
    needs many tool calls (e.g. "investigate this bug", "refactor that module").
    """

    def __init__(self, config):
        super().__init__(
            name="delegate_task",
            description=(
                "Delegate a focused sub-task to a sub-agent that runs in "
                "isolation with its own fresh conversation. Returns a concise "
                "summary of what it accomplished. Use for tasks that need many "
                "tool calls and would clutter the main context.\n\n"
                "The sub-agent can only use the tools you list in `tools`."
            ),
            parameters={
                "task": {
                    "type": "string",
                    "description": "What the sub-agent should do (imperative).",
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Tool names the sub-agent may use, e.g. "
                        '["read_file", "list_files", "run_command"].'
                    ),
                },
            },
            required=["task", "tools"],
        )
        self.config = config

    def execute(self, task, tools=None):
        tools = tools or []
        client = self.config.client
        registry = self.config.registry
        sub = SubAgent(client, self.config, registry)
        summary = sub.run(task, allowed_tools=tools)
        return {"summary": summary, "task": task, "tools_used": tools}
