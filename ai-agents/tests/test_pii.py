
from unittest.mock import patch

from shared.security.pii import anonymize_text, check_pii_leak

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentlib.config import Settings
from agentlib.llm_agent import LLMAgent


EMAIL = "test@example.com"
PHONE = "+380671234567"


# ===== БАЗОВІ ТЕСТИ =====

def test_email():
    text = f"Contact: {EMAIL}"
    result = anonymize_text(text)
    assert EMAIL not in result


def test_phone():
    text = f"Phone: {PHONE}"
    result = anonymize_text(text)
    assert PHONE not in result


def test_safe_text():
    text = "Show all available books"
    assert anonymize_text(text) == text


def test_pii_detection():
    assert check_pii_leak(EMAIL)
    assert not check_pii_leak("List books")


# ===== ДОДАТКОВІ ТЕСТИ =====

def test_input_anonymization():
    prompt = f"Find books for {EMAIL}"
    result = anonymize_text(prompt)

    assert EMAIL not in result
    assert "Find books" in result


def test_tool_result_anonymization():
    from agentlib.guardrails import render_tool_result

    envelope = {
        "ok": True,
        "result": {
            "email": EMAIL,
            "phone": PHONE,
        },
    }

    content, findings = render_tool_result(
        "get_user",
        envelope,
        max_chars=4000,
    )

    safe_content = anonymize_text(content)

    assert EMAIL not in safe_content
    assert PHONE not in safe_content


def test_output_anonymization():
    response = f"Contact: {EMAIL}"
    result = anonymize_text(response)

    assert EMAIL not in result


def test_trace_anonymization():
    arguments = f'{{"email": "{EMAIL}"}}'

    safe_arguments = anonymize_text(arguments)
    trace = f"-> create_user({safe_arguments}) = ok"

    assert EMAIL not in trace


def test_llm_output_guard_integration():
    from agentlib.llm_agent import LLMAgent

    agent = object.__new__(LLMAgent)
    agent.system_prompt = "You are a library assistant."

    class Settings:
        llm_api_key = "dummy"
        max_output_chars = 4000

    agent.s = Settings()
    agent.on_event = None

    with patch.dict("os.environ", {}, clear=False):
        result = agent._guard_output(
            f"Email: {EMAIL}",
            [],
            [],
        )

    assert EMAIL not in result


def test_llm_run_anonymizes_input_and_output():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from agentlib.config import Settings
    from agentlib.llm_agent import LLMAgent

    email = "test@example.com"

    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=f"Contact: {email}",
                    tool_calls=None,
                )
            )
        ],
        usage=SimpleNamespace(total_tokens=10),
    )

    create_mock = AsyncMock(return_value=fake_response)

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_mock)
        )
    )

    agent = LLMAgent(
        client=client,
        tools=[],
        settings=Settings(llm_api_key="test-key"),
    )

    result = asyncio.run(
        agent.run(f"Find books for {email}")
    )

    assert create_mock.await_count == 1

    sent_messages = create_mock.await_args.kwargs["messages"]

    user_message = next(
        msg["content"]
        for msg in sent_messages
        if msg["role"] == "user"
    )

    assert email not in user_message
    assert "[PII_REDACTED]" in user_message
    assert email not in result.answer
    assert email not in "\n".join(result.trace)
    assert result.stop_reason == "final"


def test_llm_tool_result_anonymization():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    from agentlib.config import Settings
    from agentlib.llm_agent import LLMAgent

    email = "test@example.com"
    phone = "+380671234567"

    fake_call = SimpleNamespace(
        id="call_test_1",
        function=SimpleNamespace(
            name="test_tool",
            arguments='{"query": "books"}',
        ),
        model_dump=lambda exclude_none=True: {
            "id": "call_test_1",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{"query": "books"}',
            },
        },
    )

    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[fake_call],
                )
            )
        ],
        usage=SimpleNamespace(total_tokens=10),
    )

    second_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="Done",
                    tool_calls=None,
                )
            )
        ],
        usage=SimpleNamespace(total_tokens=10),
    )

    create_mock = AsyncMock(
        side_effect=[first_response, second_response]
    )

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_mock)
        )
    )

    agent = LLMAgent(
        client=client,
        tools=[],
        settings=Settings(llm_api_key="test-key"),
    )

    async def fake_safe_call(tool, args):
        return {
            "ok": True,
            "result": {
                "email": email,
                "phone": phone,
            },
        }

    fake_tool = SimpleNamespace(
        name="test_tool",
        is_write=False,
    )
    agent.registry["test_tool"] = fake_tool

    with patch(
        "agentlib.llm_agent.safe_call",
        new=fake_safe_call,
    ):
        result = asyncio.run(
            agent.run("Find available books")
        )

    assert create_mock.await_count == 2

    second_messages = create_mock.await_args_list[1].kwargs["messages"]

    tool_messages = [
        message["content"]
        for message in second_messages
        if message["role"] == "tool"
    ]

    assert len(tool_messages) == 1

    assert email not in tool_messages[0]
    assert phone not in tool_messages[0]

    assert email not in "\n".join(result.trace)
    assert phone not in "\n".join(result.trace)

    assert result.stop_reason == "final"
    assert result.tool_calls == 1


def make_pii_tool_agent(
    arguments='{"email": "test@example.com"}',
    tool_result=None,
    on_event=None,
):
    if tool_result is None:
        tool_result = {"ok": True, "result": {"status": "ok"}}

    fake_call = SimpleNamespace(
        id="call_pii_1",
        function=SimpleNamespace(
            name="test_tool",
            arguments=arguments,
        ),
        model_dump=lambda exclude_none=True: {
            "id": "call_pii_1",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": arguments,
            },
        },
    )

    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[fake_call],
                )
            )
        ],
        usage=SimpleNamespace(total_tokens=10),
    )

    second_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="Done",
                    tool_calls=None,
                )
            )
        ],
        usage=SimpleNamespace(total_tokens=10),
    )

    create_mock = AsyncMock(
        side_effect=[first_response, second_response]
    )

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_mock)
        )
    )

    agent = LLMAgent(
        client=client,
        tools=[],
        settings=Settings(llm_api_key="test-key"),
        on_event=on_event,
    )

    fake_tool = SimpleNamespace(
        name="test_tool",
        is_write=False,
    )
    agent.registry["test_tool"] = fake_tool

    async def fake_safe_call(tool, args):
        return tool_result

    return agent, create_mock, fake_safe_call


def run_pii_tool_agent(
    monkeypatch,
    arguments='{"email": "test@example.com"}',
    tool_result=None,
    on_event=None,
):
    agent, create_mock, fake_safe_call = make_pii_tool_agent(
        arguments=arguments,
        tool_result=tool_result,
        on_event=on_event,
    )

    monkeypatch.setattr(
        "agentlib.llm_agent.safe_call",
        fake_safe_call,
    )

    result = asyncio.run(agent.run("Find available books"))

    assert create_mock.await_count == 2

    messages = create_mock.await_args_list[1].kwargs["messages"]

    return result, messages


def test_tool_calls_history_pii(monkeypatch):
    result, messages = run_pii_tool_agent(monkeypatch)

    assistant_messages = [
        msg for msg in messages
        if msg["role"] == "assistant"
    ]

    assert len(assistant_messages) == 1

    tool_calls = assistant_messages[0]["tool_calls"]

    serialized = json.dumps(tool_calls, ensure_ascii=False)

    assert "test@example.com" not in serialized


def test_tool_call_trace_pii(monkeypatch):
    result, messages = run_pii_tool_agent(monkeypatch)

    trace = "\n".join(result.trace)

    assert "test@example.com" not in trace


def test_tool_call_event_pii(monkeypatch):
    events = []

    result, messages = run_pii_tool_agent(
        monkeypatch,
        on_event=events.append,
    )

    assert events
    assert "test@example.com" not in "\n".join(events)


def test_tool_result_phone_pii(monkeypatch):
    result, messages = run_pii_tool_agent(
        monkeypatch,
        arguments='{"query": "books"}',
        tool_result={
            "ok": True,
            "result": {
                "phone": "+380671234567",
            },
        },
    )

    tool_messages = [
        msg["content"]
        for msg in messages
        if msg["role"] == "tool"
    ]

    assert len(tool_messages) == 1
    assert "+380671234567" not in tool_messages[0]


def test_tool_call_json_validity(monkeypatch):
    result, messages = run_pii_tool_agent(monkeypatch)

    assistant_messages = [
        msg for msg in messages
        if msg["role"] == "assistant"
    ]

    tool_calls = assistant_messages[0]["tool_calls"]

    for call in tool_calls:
        arguments = call["function"]["arguments"]
        parsed = json.loads(arguments)

        assert isinstance(parsed, dict)

