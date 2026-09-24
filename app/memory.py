from model import Message


class MemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}

    async def get(self, session_id: str) -> list[Message]:
        return list(self._sessions.get(session_id, []))

    async def append(self, session_id: str, message: Message) -> None:
        self._sessions.setdefault(session_id, []).append(message)
