from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.model import Message

MAX_MESSAGES_PER_SESSION = 20


def trim_complete_turns(
    messages: list[Message],
    max_messages: int = MAX_MESSAGES_PER_SESSION,
) -> list[Message]:
    if max_messages < 1:
        raise ValueError("max_messages must be positive")

    turn_starts = [
        index for index, message in enumerate(messages) if message.role == "user"
    ]

    if not turn_starts:
        return []

    # Choose the oldest turn whose entire remaining history fits.
    for start in turn_starts:
        if len(messages) - start <= max_messages:
            return messages[start:]

    # The latest turn alone exceeds the budget: preserve it intact.
    return messages[turn_starts[-1] :]


class ConversationMemory(Protocol):
    async def get(self, user_id: str, session_id: str) -> list[Message]: ...

    async def append(self, user_id: str, session_id: str, message: Message) -> None: ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], list[Message]] = {}

    async def get(self, user_id: str, session_id: str) -> list[Message]:
        return list(self._sessions.get((user_id, session_id), []))

    async def append(self, user_id: str, session_id: str, message: Message) -> None:
        key = (user_id, session_id)
        messages = self._sessions.setdefault(key, [])
        messages.append(message)
        self._sessions[key] = trim_complete_turns(messages)


class PostgresMemoryStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, user_id: str, session_id: str, message: Message) -> None:
        statement = text("""
        INSERT INTO conversation_messages (user_id, session_id, message)
                    VALUES (:user_id, :session_id, CAST(:message AS JSONB))
        """)

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    statement,
                    {
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": message.model_dump_json(),
                    },
                )
            return

    async def get(self, user_id: str, session_id: str) -> list[Message]:
        # statement = text("""
        #          SELECT message::text
        #          FROM conversation_messages
        #          WHERE user_id = :user_id
        #            AND session_id = :session_id
        #          ORDER BY id DESC
        #          LIMIT :message_limit
        #      """)

        # async with self._session_factory() as session:
        #     result = await session.execute(
        #         statement,
        #         {
        #             "user_id": user_id,
        #             "session_id": session_id,
        #             "message_limit": MAX_MESSAGES_PER_SESSION,
        #         },
        #     )
        #     payloads = result.scalars().all()

        # # The SQL query gets newest-first; the agent needs chronological order.
        # return [Message.model_validate_json(payload) for payload in reversed(payloads)]

        statement = text("""
                WITH recent_turns AS (
                    SELECT id
                    FROM conversation_messages
                    WHERE user_id = :user_id
                      AND session_id = :session_id
                      AND message ->> 'role' = 'user'
                    ORDER BY id DESC
                    LIMIT :candidate_turn_limit
                )
                SELECT message::text
                FROM conversation_messages
                WHERE user_id = :user_id
                  AND session_id = :session_id
                  AND id >= (SELECT MIN(id) FROM recent_turns)
                ORDER BY id ASC
            """)

        async with self._session_factory() as session:
            result = await session.execute(
                statement,
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "candidate_turn_limit": MAX_MESSAGES_PER_SESSION,
                },
            )
            payloads = result.scalars().all()

        messages = [Message.model_validate_json(payload) for payload in payloads]
        return trim_complete_turns(messages)
