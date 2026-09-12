from types import SimpleNamespace

from orion.llm import chat_stream


class _FakeCompletions:
    def create(self, **kwargs):
        return CHUNKS


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


def _delta(content=None, reasoning=None, tool_calls=None):
    return SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=tool_calls)


CHUNKS = [
    SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(delta=_delta(reasoning="Let me"), finish_reason=None)],
    ),
    SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(delta=_delta(content="Hello"), finish_reason=None)],
    ),
    SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                delta=_delta(
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id="c1",
                            function=SimpleNamespace(name="run_command", arguments='{"c'),
                        )
                    ]
                ),
                finish_reason=None,
            )
        ],
    ),
    SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                delta=_delta(
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id=None,
                            function=SimpleNamespace(name=None, arguments='ommand":"ls"}'),
                        )
                    ]
                ),
                finish_reason="tool_calls",
            )
        ],
    ),
    SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2), choices=[]),
]


def test_chat_stream_collects_reasoning_text_and_tools():
    seen_reasoning: list[str] = []
    text, tool_calls, finish, usage, reasoning = chat_stream(
        _FakeClient(),
        "deepseek-reasoner",
        [],
        None,
        on_text=lambda _t: None,
        on_reasoning=seen_reasoning.append,
    )

    assert text == "Hello"
    assert reasoning == "Let me"
    assert seen_reasoning == ["Let me"]
    assert finish == "tool_calls"
    assert usage.prompt_tokens == 1
    assert tool_calls == [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "run_command", "arguments": '{"command":"ls"}'},
        }
    ]


def test_chat_stream_plain_model_has_no_reasoning():
    chunks = [
        SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(delta=_delta(content="Hi"), finish_reason="stop")],
        ),
        SimpleNamespace(usage=None, choices=[]),
    ]

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return chunks

    text, tool_calls, finish, _usage, reasoning = chat_stream(_Client(), "m", [], None)
    assert text == "Hi"
    assert reasoning == ""
    assert tool_calls == []
    assert finish == "stop"
