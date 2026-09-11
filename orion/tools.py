from dataclasses import dataclass, field


@dataclass
class Tool:
    """Base class for ORION tools: subclass and implement ``execute``.

    See ``orion/plugins/`` for examples.
    """

    name: str
    description: str
    parameters: dict = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def execute(self, **kwargs) -> dict:
        raise NotImplementedError(f"Tool '{self.name}' does not implement execute()")

    def to_schema(self) -> dict:
        """Return the OpenAI/DeepSeek function-calling schema."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


class ToolRegistry:
    """Holds all tools and handles lookup and safe execution."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[tuple[str, str]]:
        """Return a (name, one-line summary) pair for every tool."""

        pairs = []
        for name in sorted(self._tools):
            desc = self._tools[name].description
            first_line = next(
                (line.strip() for line in desc.splitlines() if line.strip()),
                "",
            )
            pairs.append((name, first_line))
        return pairs

    def schema(self) -> list[dict]:
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool: {name}"}

        try:
            return tool.execute(**arguments)
        except TypeError as err:
            return {"error": f"Invalid arguments: {err}"}
        except Exception as err:  # noqa: BLE001
            return {"error": f"{type(err).__name__}: {err}"}
