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
                    session_id="session-1",
                    message=Message(role="user", content=f"message-{index}"),
                )
            return await memory.get(session_id="session-1")

        messages = asyncio.run(append_messages())

        self.assertEqual(len(messages), 20)
        self.assertEqual(messages[0].content, "message-1")
        self.assertEqual(messages[-1].content, "message-20")


if __name__ == "__main__":
    unittest.main()
