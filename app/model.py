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


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    name: str | None = None


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


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
