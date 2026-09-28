import asyncio
import unittest

from app.memory import InMemoryMemoryStore
from app.model import Message


class InMemoryMemoryStoreTests(unittest.TestCase):
    def test_get_keeps_only_the_most_recent_20_messages(self) -> None:
        memory = InMemoryMemoryStore()

        async def append_messages() -> list[Message]:
            for index in range(21):
                await memory.append(
                    user_id="USER001",
                    session_id="session-1",
                    message=Message(role="user", content=f"message-{index}"),
                )
            return await memory.get(user_id="USER001", session_id="session-1")

        messages = asyncio.run(append_messages())

        self.assertEqual(len(messages), 20)
        self.assertEqual(messages[0].content, "message-1")
        self.assertEqual(messages[-1].content, "message-20")

    def test_history_is_isolated_by_user_when_session_id_matches(self) -> None:
        memory = InMemoryMemoryStore()

        async def append_and_get_histories() -> tuple[list[Message], list[Message]]:
            await memory.append(
                user_id="USER001",
                session_id="shared-session",
                message=Message(role="user", content="private to USER001"),
            )
            await memory.append(
                user_id="USER002",
                session_id="shared-session",
                message=Message(role="user", content="private to USER002"),
            )
            user_one = await memory.get("USER001", "shared-session")
            user_two = await memory.get("USER002", "shared-session")
            return user_one, user_two

        user_one, user_two = asyncio.run(append_and_get_histories())

        self.assertEqual(
            [message.content for message in user_one], ["private to USER001"]
        )
        self.assertEqual(
            [message.content for message in user_two], ["private to USER002"]
        )


if __name__ == "__main__":
    unittest.main()
