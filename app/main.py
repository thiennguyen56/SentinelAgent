from agent import AgentService
from fastapi import FastAPI
from llm import FakeLLMClient
from memory import MemoryStore
from model import ChatRequest, ChatResponse, LLMResponse, ToolCall
from tools import GetOrderStatusTool, ToolRegistry

app = FastAPI()

memory = MemoryStore()

tools = ToolRegistry()
tools.register(GetOrderStatusTool().name, GetOrderStatusTool())
llm = FakeLLMClient(
    responses=[
        {
            "type": "tool_call",
            "tool_call": {
                "name": "get_order_status",
                "arguments": {
                    "order_id": "ORD001",
                },
            },
        },
        {
            "type": "final",
            "content": (
                "ORD001 has shipped and is expected to arrive on September 25."
            ),
        },
    ]
)

print("hello", not llm._responses)

agent = AgentService(
    llm=llm,
    memory=memory,
    tools=tools,
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
