import asyncio
import json
import unittest
from unittest.mock import patch

from app.agent import AgentService
from app.llm import FakeLLMClient
from app.memory import InMemoryMemoryStore
from app.tools import GetOrderStatusTool, ToolRegistry


def make_agent(
    final_reply: str = "ORD001 has shipped and is expected on September 25.",
) -> tuple[AgentService, InMemoryMemoryStore]:
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
                "content": final_reply,
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
        self.assertEqual(
            [message.role for message in history],
            ["user", "assistant", "tool", "assistant"],
        )
        tool_call = history[1].tool_calls[0]
        tool_result = history[2]
        self.assertEqual(tool_result.tool_call_id, tool_call.id)
        self.assertEqual(tool_result.name, tool_call.name)
        self.assertEqual(
            json.loads(tool_result.content), {"error": "order_not_available"}
        )
        self.assertNotIn("shipped", response.message)

    def test_follow_up_receives_complete_history_after_denial(self) -> None:
        agent, _ = make_agent(
            final_reply="Please provide an order number for your account."
        )

        async def conversation() -> None:
            with patch.object(
                agent.llm, "generate", wraps=agent.llm.generate
            ) as generate:
                first = await agent.chat(
                    session_id="denied-follow-up",
                    user_id="USER002",
                    message="Where is ORD001?",
                )
                self.assertEqual(
                    first.message, "I can’t provide information for that order."
                )
                self.assertEqual(generate.call_count, 1)

                second = await agent.chat(
                    session_id="denied-follow-up",
                    user_id="USER002",
                    message="Can you help with one of my orders?",
                )
                self.assertEqual(generate.call_count, 2)

                # Verify the history actually supplied to the next LLM call.
                next_history = generate.call_args_list[1].args[0]
                self.assertEqual(
                    [message.role for message in next_history],
                    ["user", "assistant", "tool", "assistant", "user"],
                )
                tool_call = next_history[1].tool_calls[0]
                tool_result = next_history[2]
                self.assertEqual(tool_result.tool_call_id, tool_call.id)
                self.assertEqual(tool_result.name, tool_call.name)
                self.assertEqual(
                    json.loads(tool_result.content), {"error": "order_not_available"}
                )
                self.assertEqual(
                    second.message,
                    "Please provide an order number for your account.",
                )

        asyncio.run(conversation())


if __name__ == "__main__":
    unittest.main()
