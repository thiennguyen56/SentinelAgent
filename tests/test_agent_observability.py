import asyncio
import unittest

from app.agent import AgentService
from app.llm import FakeLLMClient, LLMCallMetadata
from app.memory import InMemoryMemoryStore
from app.tools import GetOrderStatusTool, ToolRegistry


class RecordingObserver:
    def __init__(self) -> None:
        self.metadata: list[LLMCallMetadata] = []

    def record(self, metadata: LLMCallMetadata) -> None:
        self.metadata.append(metadata)


class FailingObserver:
    def record(self, metadata: LLMCallMetadata) -> None:
        raise RuntimeError("monitoring backend unavailable")


def make_agent(
    responses: list[dict], observer: RecordingObserver | FailingObserver
) -> AgentService:
    tools = ToolRegistry()
    order_status_tool = GetOrderStatusTool()
    tools.register(order_status_tool.name, order_status_tool)

    return AgentService(
        llm=FakeLLMClient(responses=responses),
        memory=InMemoryMemoryStore(),
        tools=tools,
        observer=observer,
    )


class AgentObservabilityTests(unittest.TestCase):
    def test_observer_records_metadata_for_each_llm_call(self) -> None:
        observer = RecordingObserver()
        agent = make_agent(
            responses=[
                {
                    "type": "tool_call",
                    "tool_call": {
                        "id": "call_order_status_1",
                        "name": "get_order_status",
                        "arguments": {"order_id": "ORD001"},
                    },
                },
                {"type": "final", "content": "ORD001 has shipped."},
            ],
            observer=observer,
        )

        response = asyncio.run(
            agent.chat(
                session_id="observability-session",
                user_id="USER001",
                message="Where is ORD001?",
            )
        )

        self.assertEqual(response.message, "ORD001 has shipped.")
        self.assertEqual(
            observer.metadata,
            [
                LLMCallMetadata(
                    model="",
                    provider_response_id="",
                    duration_ms=0.0,
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                ),
                LLMCallMetadata(
                    model="",
                    provider_response_id="",
                    duration_ms=0.0,
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                ),
            ],
        )

    def test_observer_failure_does_not_fail_chat(self) -> None:
        agent = make_agent(
            responses=[{"type": "final", "content": "I can help with that."}],
            observer=FailingObserver(),
        )

        response = asyncio.run(
            agent.chat(
                session_id="observer-failure-session",
                user_id="USER001",
                message="Hello",
            )
        )

        self.assertEqual(response.message, "I can help with that.")


if __name__ == "__main__":
    unittest.main()
