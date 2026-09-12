from openai import OpenAI


def chat_stream(
    client: OpenAI,
    model: str,
    messages: list,
    tools: list | None,
    on_text=None,
    on_reasoning=None,
):
    """Streamed chat.

    Text chunks go through ``on_text``; reasoning chunks (``deepseek-reasoner``)
    through ``on_reasoning``. Returns ``(text, tool_calls, finish_reason,
    usage, reasoning)``.
    """

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    stream = client.chat.completions.create(**kwargs)

    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: dict[int, dict] = {}
    finish_reason = None
    usage = None

    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage

        if not chunk.choices:
            continue

        choice = chunk.choices[0]
        delta = choice.delta

        reasoning = getattr(delta, "reasoning_content", None) if delta else None
        if reasoning:
            reasoning_parts.append(reasoning)
            if on_reasoning:
                on_reasoning(reasoning)

        if delta and delta.content:
            text_parts.append(delta.content)
            if on_text:
                on_text(delta.content)

        if delta and delta.tool_calls:
            for tc in delta.tool_calls:
                entry = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    entry["id"] = tc.id
                if tc.function:
                    if tc.function.name and not entry["name"]:
                        entry["name"] = tc.function.name
                    if tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

        if choice.finish_reason:
            finish_reason = choice.finish_reason

    final_tool_calls = [
        {
            "id": tool_calls[i]["id"],
            "type": "function",
            "function": {
                "name": tool_calls[i]["name"],
                "arguments": tool_calls[i]["arguments"],
            },
        }
        for i in sorted(tool_calls)
    ]

    return (
        "".join(text_parts),
        final_tool_calls,
        finish_reason,
        usage,
        "".join(reasoning_parts),
    )


def chat_once(client: OpenAI, model: str, messages: list):
    """One-shot (non-streaming) chat, e.g. for /compact."""

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    message = response.choices[0].message
    return message.content, response.usage
