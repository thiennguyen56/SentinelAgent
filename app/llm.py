from collections import deque
from typing import Any, Protocol

from model import FinalAnswer, LLMResponse, Message
from pydantic import TypeAdapter, ValidationError

response_adapter = TypeAdapter(LLMResponse)


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
    async def generate(self, message: list[Message]) -> LLMResponse:
        return FinalAnswer(type="final", content="")


class FakeLLMClient:
    def __init__(
        self,
        responses: list[dict[str, Any]],
    ) -> None:
        self._responses = deque(responses)

    async def generate(self, message: list[Message]) -> LLMResponse:
        if not self._responses:
            raise RuntimeError("FakeLLMClient has no responses remaining")
        return parse_llm_response(self._responses.popleft())
