import asyncio
import json
import unittest

from app.agent import AgentService
from app.llm import FakeLLMClient
from app.memory import InMemoryMemoryStore
from app.tools import GetOrderStatusTool, ToolRegistry


def make_agent() -> tuple[AgentService, InMemoryMemoryStore]:
    memory = InMemoryMemoryStore()
    tools = ToolRegistry()
    order_status_tool = GetOrderStatusTool()
    tools.register(order_status_tool.name, order_status_tool)
    llm = FakeLLMClient(
        responses=[
            {
                "type": "tool_call",
                "tool_call": {
                    "id": "call_order_status_1",
                    "name": "get_order_status",
                    "arguments": {"order_id": "ORD001"},
                },
            },
            {
                "type": "final",
                "content": "ORD001 has shipped and is expected on September 25.",
            },
        ]
    )
    return AgentService(llm=llm, memory=memory, tools=tools), memory


class OrderAuthorizationTests(unittest.TestCase):
    def test_order_owner_can_retrieve_status(self) -> None:
        agent, memory = make_agent()

        response = asyncio.run(
            agent.chat(
                session_id="owner-session",
                user_id="USER001",
                message="Where is ORD001?",
            )
        )
        history = asyncio.run(memory.get("USER001", "owner-session"))

        self.assertEqual(
            response.message,
            "ORD001 has shipped and is expected on September 25.",
        )
        tool_result = next(message for message in history if message.role == "tool")
        self.assertEqual(
            json.loads(tool_result.content),
            {
                "order_id": "ORD001",
                "status": "shipped",
                "estimated_delivery": "2026-09-25",
            },
        )

    def test_non_owner_gets_generic_denial_without_order_data(self) -> None:
        agent, memory = make_agent()

        response = asyncio.run(
            agent.chat(
                session_id="non-owner-session",
                user_id="USER002",
                message="Where is ORD001?",
            )
        )
        history = asyncio.run(memory.get("USER002", "non-owner-session"))

        self.assertEqual(
            response.message,
            "I can’t provide information for that order.",
        )
        self.assertFalse(any(message.role == "tool" for message in history))
        self.assertNotIn("shipped", response.message)


if __name__ == "__main__":
    unittest.main()
