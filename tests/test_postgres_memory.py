import os
import unittest
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database import create_database_engine, create_session_factory
from app.memory import PostgresMemoryStore
from app.model import Message, ToolCall


@pytest.mark.integration
class PostgresMemoryStoreIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        database_url = os.getenv("TEST_DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest(
                "Set TEST_DATABASE_URL to a dedicated, migrated PostgreSQL test database"
            )

        self.engine: AsyncEngine = create_database_engine(database_url)
        self.session_factory = create_session_factory(self.engine)
        self.store = PostgresMemoryStore(self.session_factory)
        self.user_id = f"test-user-{uuid4()}"
        self.session_id = f"test-session-{uuid4()}"
        self.other_user_id = f"test-user-{uuid4()}"
        self.other_session_id = f"test-session-{uuid4()}"

    async def asyncTearDown(self) -> None:
        if not hasattr(self, "session_factory"):
            return

        async with self.session_factory() as session, session.begin():
            await session.execute(
                text(
                    """
                        DELETE FROM conversation_messages
                        WHERE (user_id = :user_id AND session_id IN (
                            :session_id, :other_session_id
                        )) OR (user_id = :other_user_id AND session_id = :session_id)
                        """
                ),
                {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "other_user_id": self.other_user_id,
                    "other_session_id": self.other_session_id,
                },
            )
        await self.engine.dispose()

    async def test_appended_messages_round_trip_in_chronological_order(self) -> None:
        expected = [
            Message(role="user", content="Where is my order?"),
            Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="get_order_status",
                        arguments={"order_id": "ORD001"},
                    )
                ],
            ),
            Message(
                role="tool",
                name="get_order_status",
                tool_call_id="call-1",
                content='{"status":"shipped"}',
            ),
        ]

        for message in expected:
            await self.store.append(self.user_id, self.session_id, message)

        self.assertEqual(await self.store.get(self.user_id, self.session_id), expected)

    async def test_history_is_isolated_by_user_and_session(self) -> None:
        own_message = Message(role="user", content="my private conversation")
        await self.store.append(self.user_id, self.session_id, own_message)
        await self.store.append(
            self.other_user_id,
            self.session_id,
            Message(role="user", content="another user's conversation"),
        )
        await self.store.append(
            self.user_id,
            self.other_session_id,
            Message(role="user", content="another session"),
        )

        self.assertEqual(
            await self.store.get(self.user_id, self.session_id), [own_message]
        )

    async def test_get_returns_only_the_latest_20_messages_in_order(self) -> None:
        for index in range(21):
            await self.store.append(
                self.user_id,
                self.session_id,
                Message(role="user", content=f"message-{index}"),
            )

        messages = await self.store.get(self.user_id, self.session_id)

        self.assertEqual(len(messages), 20)
        self.assertEqual(messages[0].content, "message-1")
        self.assertEqual(messages[-1].content, "message-20")

    async def test_trimming_preserves_complete_tool_turns(self) -> None:
        turns = []
        for index in range(6):
            call_id = f"call-{index}"
            turns.append(
                [
                    Message(role="user", content=f"question-{index}"),
                    Message(
                        role="assistant",
                        tool_calls=[
                            ToolCall(
                                id=call_id,
                                name="get_order_status",
                                arguments={"order_id": "ORD001"},
                            )
                        ],
                    ),
                    Message(
                        role="tool",
                        name="get_order_status",
                        tool_call_id=call_id,
                        content='{"status":"shipped"}',
                    ),
                    Message(role="assistant", content=f"answer-{index}"),
                ]
            )
        newest = Message(role="user", content="My next question")
        messages = [message for turn in turns for message in turn] + [newest]

        for message in messages:
            await self.store.append(self.user_id, self.session_id, message)
        history = await self.store.get(self.user_id, self.session_id)

        self.assertEqual(len(history), 17)
        self.assertEqual(history[0].content, "question-2")
        self.assertEqual(history[-1], newest)
        self.assertEqual(
            history,
            [message for turn in turns[2:] for message in turn] + [newest],
        )
        for start in range(0, 16, 4):
            user, assistant, result, final = history[start : start + 4]
            self.assertEqual(
                [user.role, assistant.role, result.role, final.role],
                ["user", "assistant", "tool", "assistant"],
            )
            self.assertEqual(result.tool_call_id, assistant.tool_calls[0].id)

    async def test_latest_oversized_turn_is_preserved(self) -> None:
        messages = [Message(role="user", content="Check my orders")]
        for index in range(10):
            call_id = f"call-{index}"
            messages.extend(
                [
                    Message(
                        role="assistant",
                        tool_calls=[
                            ToolCall(
                                id=call_id,
                                name="get_order_status",
                                arguments={"order_id": "ORD001"},
                            )
                        ],
                    ),
                    Message(
                        role="tool",
                        name="get_order_status",
                        tool_call_id=call_id,
                        content='{"status":"shipped"}',
                    ),
                ]
            )
        messages.append(Message(role="assistant", content="All checked"))

        for message in messages:
            await self.store.append(self.user_id, self.session_id, message)
        history = await self.store.get(self.user_id, self.session_id)

        self.assertEqual(len(history), 22)
        self.assertEqual(history, messages)


if __name__ == "__main__":
    unittest.main()
