import json
import logging
from typing import Protocol

from app.llm import (
    LLMCallMetadata,
    LLMClient,
    MalformedLLMResponse,
)
from app.memory import ConversationMemory
from app.model import (
    ChatResponse,
    FinalAnswer,
    Message,
    ToolCallResponse,
)
from app.tools import (
    InvalidToolArgumentsError,
    ToolExecutionError,
    ToolRegistry,
    UnauthorizedToolRequest,
    UnknownToolError,
)

logger = logging.getLogger(__name__)


class LLMCallObserver(Protocol):
    def record(self, metadata: LLMCallMetadata) -> None:
        return


class LoggingLLMCallObserver:
    def record(self, metadata: LLMCallMetadata) -> None:
        logger.info(
            "llm_call_completed model=%s duration_ms=%.2f "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            metadata.model,
            metadata.duration_ms,
            metadata.prompt_tokens,
            metadata.completion_tokens,
            metadata.total_tokens,
        )


MAX_TOOL_CALLS = 5


class AgentService:
    def __init__(
        self,
        llm: LLMClient,
        memory: ConversationMemory,
        tools: ToolRegistry,
        observer: LLMCallObserver | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.observer = observer

    async def chat(self, session_id: str, user_id: str, message: str) -> ChatResponse:

        await self.memory.append(
            user_id=user_id,
            session_id=session_id,
            message=Message(role="user", content=message),
        )

        for _ in range(MAX_TOOL_CALLS + 1):
            history = await self.memory.get(user_id=user_id, session_id=session_id)

            try:
                llm_call_result = await self.llm.generate(
                    history, self.tools.get_registered_tools()
                )
                response = llm_call_result.response

                if self.observer is not None:
                    try:
                        self.observer.record(llm_call_result.metadata)
                    except Exception:
                        logger.exception("Failed to record LLM call metadata")

            except MalformedLLMResponse as exc:
                logger.warning("Rejected LLM response: %s", exc)
                return ChatResponse(
                    session_id=session_id,
                    user_id=user_id,
                    message=("I'm unable to process that request right now"),
                )
            if isinstance(response, FinalAnswer):
                await self.memory.append(
                    user_id,
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
                await self.memory.append(
                    user_id,
                    session_id,
                    Message(role="assistant", tool_calls=[tool_call]),
                )
                try:
                    result = await self.tools.execute(
                        name=tool_call.name,
                        arguments=tool_call.arguments,
                        user_id=user_id,
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
                except UnauthorizedToolRequest:
                    reply = "I can’t provide information for that order."
                    await self.memory.append(
                        user_id,
                        session_id,
                        Message(role="assistant", content=reply),
                    )
                    return ChatResponse(
                        session_id=session_id,
                        user_id=user_id,
                        message=reply,
                    )

                await self.memory.append(
                    user_id,
                    session_id,
                    Message(
                        role="tool",
                        name=tool_call.name,
                        tool_call_id=tool_call.id,
                        content=json.dumps(result),
                    ),
                )

        return ChatResponse(
            session_id=session_id,
            user_id=user_id,
            message=("I'm unable to complete the request after multiple attempts."),
        )
