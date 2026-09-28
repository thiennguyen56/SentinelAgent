import os
import unittest
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.database import create_database_engine, create_session_factory
from app.handoff import PostgresHandoffStore


@pytest.mark.integration
class PostgresHandoffStoreIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        database_url = os.getenv("TEST_DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest(
                "Set TEST_DATABASE_URL to a dedicated, migrated PostgreSQL test database"
            )

        self.engine = create_database_engine(database_url)
        self.session_factory = create_session_factory(self.engine)
        self.store = PostgresHandoffStore(self.session_factory)
        self.user_id = f"test-user-{uuid4()}"
        self.session_id = f"test-session-{uuid4()}"

    async def asyncTearDown(self) -> None:
        if not hasattr(self, "session_factory"):
            return

        try:
            async with self.session_factory.begin() as session:
                await session.execute(
                    text("""
                        DELETE FROM handoff_requests
                        WHERE user_id = :user_id AND session_id = :session_id
                    """),
                    {"user_id": self.user_id, "session_id": self.session_id},
                )
        finally:
            await self.engine.dispose()

    async def test_created_handoff_can_be_read_by_its_owner(self) -> None:
        created = await self.store.create(
            user_id=self.user_id,
            session_id=self.session_id,
            summary="User requested help with an order.",
            entity_ids=["ORD001"],
            priority="normal",
        )

        self.assertEqual(created.user_id, self.user_id)
        self.assertEqual(created.session_id, self.session_id)
        self.assertEqual(created.reason, "user_requested_human")
        self.assertEqual(created.summary, "User requested help with an order.")
        self.assertEqual(created.entity_ids, ["ORD001"])
        self.assertEqual(created.priority, "normal")
        self.assertEqual(created.status, "pending")
        self.assertIsNotNone(created.created_at.tzinfo)
        self.assertEqual(await self.store.get(created.id, self.user_id), created)

    async def test_handoff_is_not_visible_to_another_user(self) -> None:
        created = await self.store.create(
            user_id=self.user_id,
            session_id=self.session_id,
            summary="User requested a person.",
            entity_ids=[],
            priority="normal",
        )

        self.assertIsNone(await self.store.get(created.id, f"other-user-{uuid4()}"))
        self.assertIsNotNone(await self.store.get(created.id, self.user_id))

    async def test_unknown_handoff_returns_none(self) -> None:
        self.assertIsNone(await self.store.get(uuid4(), self.user_id))
