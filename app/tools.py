from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError


class UnknownToolError(Exception):
    pass


class InvalidToolArgumentsError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


ORDERS = {
    "ORD001": {
        "status": "shipped",
        "estimated_delivery": "2026-09-25",
    },
    "ORD002": {
        "status": "processing",
        "estimated_delivery": None,
    },
}


class GetOrderStatusArgs(BaseModel):
    order_id: str


class Tool(ABC):
    name: str
    args_schema: type[BaseModel]

    @abstractmethod
    async def execute(self, args: BaseModel) -> dict[str, Any]:
        pass


class GetOrderStatusTool(Tool):
    name = "get_order_status"
    args_schema = GetOrderStatusArgs

    async def execute(self, args: BaseModel) -> dict[str, Any]:
        if not isinstance(args, GetOrderStatusArgs):
            raise TypeError("Invalid arguments for get_order_status")

        order = ORDERS.get(args.order_id)
        if order is None:
            return {
                "error": "order_not_found",
                "order_id": args.order_id,
            }

        return {
            "order_id": args.order_id,
            "status": order["status"],
            "estimated_delivery": order["estimated_delivery"],
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, tool: Tool) -> None:
        self._tools[name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name, None)

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)

        if tool is None:
            raise UnknownToolError(f"Unknown tool: {name}")

        try:
            args = tool.args_schema.model_validate(arguments)
        except ValidationError as exc:
            raise InvalidToolArgumentsError(
                f"Invalid arguments for tool: {name}"
            ) from exc

        try:
            return await tool.execute(args)
        except Exception as exc:
            raise ToolExecutionError(f"Failed to execute tool: {name}") from exc
