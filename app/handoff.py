import json
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class Handoff(BaseModel):
    id: UUID
    user_id: str
    session_id: str
    reason: Literal["user_requested_human"]
    summary: str
    entity_ids: list[str]
    priority: Literal["normal", "high"]
    status: Literal["pending"]
    created_at: datetime


class PostgresHandoffStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        user_id: str,
        session_id: str,
        summary: str,
        entity_ids: list[str],
        priority: Literal["normal", "high"],
    ) -> Handoff:
        handoff_id = uuid4()

        statement = text("""
          INSERT INTO handoff_requests (
              id, user_id, session_id, reason, summary, entity_ids, priority
          )
          VALUES (
              :id, :user_id, :session_id, 'user_requested_human',
              :summary, CAST(:entity_ids AS JSONB), :priority
          )
          RETURNING
              id, user_id, session_id, reason, summary,
              entity_ids, priority, status, created_at
      """)

        async with self._session_factory.begin() as session:
            result = await session.execute(
                statement,
                {
                    "id": handoff_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "summary": summary,
                    "entity_ids": json.dumps(entity_ids),
                    "priority": priority,
                },
            )
            row = result.mappings().one()

        return Handoff.model_validate(dict(row))

    async def get(self, handoff_id: UUID, user_id: str) -> Handoff | None:
        statement = text("""
          SELECT
              id, user_id, session_id, reason, summary,
              entity_ids, priority, status, created_at
          FROM handoff_requests
          WHERE id = :handoff_id
            AND user_id = :user_id
      """)

        async with self._session_factory() as session:
            result = await session.execute(
                statement,
                {"handoff_id": handoff_id, "user_id": user_id},
            )
            row = result.mappings().one_or_none()

        return Handoff.model_validate(dict(row)) if row is not None else None
