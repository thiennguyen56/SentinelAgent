from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    user_id: str
    message: str


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


class FinalAnswer(BaseModel):
    type: Literal["final"]
    content: str


class ToolCallResponse(BaseModel):
    type: Literal["tool_call"]
    tool_call: ToolCall


LLMResponse = Annotated[
    FinalAnswer | ToolCallResponse,
    Field(discriminator="type"),
]
