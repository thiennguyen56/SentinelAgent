from typing import Protocol

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.model import Message

MAX_MESSAGES_PER_SESSION = 20


class ConversationMemory(Protocol):
    async def get(self, user_id: str, session_id: str) -> list[Message]: ...

    async def append(self, user_id: str, session_id: str, message: Message) -> None: ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], list[Message]] = {}

    async def get(self, user_id: str, session_id: str) -> list[Message]:
        return list(self._sessions.get((user_id, session_id), []))

    async def append(self, user_id: str, session_id: str, message: Message) -> None:
        messages = self._sessions.setdefault((user_id, session_id), [])
        messages.append(message)
        del messages[:-MAX_MESSAGES_PER_SESSION]


class PostgresMemoryStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, user_id: str, session_id: str, message: Message) -> None:
        return

    async def get(self, user_id: str, session_id: str) -> list[Message]:
        return []
