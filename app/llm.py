import json
from collections import deque
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import TypeAdapter, ValidationError

from app.model import FinalAnswer, LLMResponse, Message, ToolCall, ToolCallResponse
from app.settings import Settings

response_adapter = TypeAdapter(LLMResponse)


@dataclass(frozen=True)
class LLMCallMetadata:
    model: str
    provider_response_id: str
    duration_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class LLMCallResult:
    response: LLMResponse
    metadata: LLMCallMetadata


class MalformedLLMResponse(Exception):
    pass


def parse_llm_response(
    raw_response: dict[str, Any],
) -> LLMResponse:
    try:
        return response_adapter.validate_python(raw_response)
    except ValidationError as exc:
        raise MalformedLLMResponse("LLM returned an invalid response") from exc


class LLMClient(Protocol):
    async def generate(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMCallResult:
        return LLMCallResult(
            response=FinalAnswer(type="final", content=""),
            metadata=LLMCallMetadata(
                model="",
                provider_response_id="",
                duration_ms=0.0,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
            ),
        )


class OpenRouterLLMClient:
    def __init__(self) -> None:
        settings = Settings()
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key.get_secret_value(),
        )
        self.model = settings.openrouter_model

    def _serialize_message(self, message: Message) -> dict[str, Any]:
        if message.role == "assistant" and message.tool_calls:
            return {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        if message.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "name": message.name,
                "content": message.content,
            }

        return {"role": message.role, "content": message.content}

    async def generate(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMCallResult:
        started_at = perf_counter()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[self._serialize_message(message) for message in messages],
            tools=tools,
        )

        duration_ms = (perf_counter() - started_at) * 1000
        usage = response.usage
        metadata = LLMCallMetadata(
            model=response.model or self.model,
            provider_response_id=response.id or "unknown",
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
        )

        if not response.choices:
            raise MalformedLLMResponse("LLM returned no choices")

        message = response.choices[0].message
        if message.tool_calls:
            if len(message.tool_calls) != 1:
                raise MalformedLLMResponse("Expected one tool call")

            provider_call = message.tool_calls[0]

            try:
                arguments = json.loads(provider_call.function.arguments)
            except (TypeError, json.JSONDecodeError) as exc:
                raise MalformedLLMResponse(
                    "Tool arguments were not valid JSON"
                ) from exc

            if not isinstance(arguments, dict):
                raise MalformedLLMResponse("Tool arguments must be a JSON object")

            return LLMCallResult(
                response=ToolCallResponse(
                    type="tool_call",
                    tool_call=ToolCall(
                        id=provider_call.id,
                        name=provider_call.function.name,
                        arguments=arguments,
                    ),
                ),
                metadata=metadata,
            )

        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise MalformedLLMResponse("LLM returned no text")

        return LLMCallResult(
            response=FinalAnswer(type="final", content=content),
            metadata=metadata,
        )


class FakeLLMClient:
    def __init__(
        self,
        responses: list[dict[str, Any]],
    ) -> None:
        self._responses = deque(responses)

    async def generate(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMCallResult:
        if not self._responses:
            raise RuntimeError("FakeLLMClient has no responses remaining")
        return LLMCallResult(
            response=parse_llm_response(self._responses.popleft()),
            metadata=LLMCallMetadata(
                model="",
                provider_response_id="",
                duration_ms=0.0,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
            ),
        )
