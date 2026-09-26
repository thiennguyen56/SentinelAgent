import logging

from fastapi import FastAPI

from app.agent import AgentService, LoggingLLMCallObserver
from app.llm import OpenRouterLLMClient
from app.memory import InMemoryMemoryStore
from app.model import ChatRequest, ChatResponse
from app.tools import GetOrderStatusTool, ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI()

memory = InMemoryMemoryStore()


tools = ToolRegistry()
tools.register(GetOrderStatusTool().name, GetOrderStatusTool())
# llm = FakeLLMClient(
#     responses=[
#         {
#             "type": "tool_call",
#             "tool_call": {
#                 "name": "get_order_status",
#                 "arguments": {
#                     "order_id": "ORD001",
#                 },
#             },
#         },
#         {
#             "type": "final",
#             "content": (
#                 "ORD001 has shipped and is expected to arrive on September 25."
#             ),
#         },
#     ]
# )

llm = OpenRouterLLMClient()

agent = AgentService(
    llm=llm,
    memory=memory,
    tools=tools,
    observer=LoggingLLMCallObserver(),
)


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
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent.chat(
        session_id=request.session_id,
        user_id=request.user_id,
        message=request.message,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
