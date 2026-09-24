import json

from llm import (
    LLMClient,
    MalformedLLMResponse,
)
from memory import MemoryStore
from model import (
    ChatResponse,
    FinalAnswer,
    Message,
    ToolCallResponse,
)
from tools import (
    InvalidToolArgumentsError,
    ToolExecutionError,
    ToolRegistry,
    UnknownToolError,
)

MAX_TOOL_CALLS = 5


class AgentService:
    def __init__(
        self, llm: LLMClient, memory: MemoryStore, tools: ToolRegistry
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.tools = tools

    async def chat(self, session_id: str, user_id: str, message: str) -> ChatResponse:

        await self.memory.append(
            session_id=session_id, message=Message(role="user", content=message)
        )

        for _ in range(MAX_TOOL_CALLS + 1):
            history = await self.memory.get(session_id=session_id)

            try:
                response = await self.llm.generate(history)
            except MalformedLLMResponse:
                return ChatResponse(
                    session_id=session_id,
                    user_id=user_id,
                    message=("I'm unable to process that request right now"),
                )
            if isinstance(response, FinalAnswer):
                await self.memory.append(
                    session_id,
                    Message(
                        role="assistant",
                        content=response.content,
                    ),
                )

                return ChatResponse(
                    session_id=session_id,
                    user_id=user_id,
                    message=response.content,
                )
            if isinstance(response, ToolCallResponse):
                tool_call = response.tool_call

                try:
                    result = await self.tools.execute(
                        name=tool_call.name, arguments=tool_call.arguments
                    )
                except UnknownToolError:
                    result = {
                        "error": "unknown_tool",
                    }

                except InvalidToolArgumentsError:
                    result = {
                        "error": "invalid_arguments",
                    }

                except ToolExecutionError:
                    result = {
                        "error": "tool_execution_failed",
                    }

                await self.memory.append(
                    session_id,
                    Message(
                        role="tool",
                        name=tool_call.name,
                        content=json.dumps(result),
                    ),
                )

        return ChatResponse(
            session_id=session_id,
            user_id=user_id,
            message=("I'm unable to complete the request after multiple attempts."),
        )
