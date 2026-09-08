from orion.tools import Tool, ToolRegistry


class EchoTool(Tool):
    def __init__(self):
        super().__init__(
            name="echo",
            description="Echo back text",
            parameters={"text": {"type": "string"}},
            required=["text"],
        )

    def execute(self, text):
        return {"echo": text}


def test_registry_execute():
    reg = ToolRegistry()
    reg.register(EchoTool())
    assert reg.execute("echo", {"text": "hi"}) == {"echo": "hi"}


def test_registry_unknown_tool():
    reg = ToolRegistry()
    res = reg.execute("nope", {})
    assert "Unknown tool" in res["error"]


def test_registry_catches_errors():
    reg = ToolRegistry()
    reg.register(EchoTool())
    res = reg.execute("echo", {"wrong_arg": 1})
    assert "error" in res


def test_schema_shape():
    reg = ToolRegistry()
    reg.register(EchoTool())
    schema = reg.schema()
    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == "echo"
    assert schema[0]["function"]["parameters"]["required"] == ["text"]
