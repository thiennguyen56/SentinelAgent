import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from sqlalchemy import text

from app.agent import AgentService, LoggingLLMCallObserver
from app.auth import get_current_user_id
from app.database import create_database_engine, create_session_factory
from app.llm import OpenRouterLLMClient
from app.memory import PostgresMemoryStore
from app.model import ChatRequest, ChatResponse
from app.settings import DatabaseSettings
from app.tools import GetOrderStatusTool, ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = DatabaseSettings()
    engine = create_database_engine(settings.database_url.get_secret_value())

    try:
        # Verify connectivity before accepting requests.
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        session_factory = create_session_factory(engine)
        memory = PostgresMemoryStore(session_factory)

        app.state.agent = AgentService(
            llm=llm,
            memory=memory,
            tools=tools,
            observer=LoggingLLMCallObserver(),
        )

        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)


def get_agent(request: Request) -> AgentService:
    return request.app.state.agent


tools = ToolRegistry()
tools.register(GetOrderStatusTool().name, GetOrderStatusTool())

llm = OpenRouterLLMClient()


@app.get("/")
async def root():
    return {"message": "Hello, World!"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    return {"status": "ok"}


@app.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    agent: Annotated[AgentService, Depends(get_agent)],
) -> ChatResponse:
    return await agent.chat(
        session_id=request.session_id,
        user_id=user_id,
        message=request.message,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
