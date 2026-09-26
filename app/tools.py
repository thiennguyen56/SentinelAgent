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

ORDER_OWNERS = {
    "ORD001": "USER001",
    "ORD002": "USER002",
}


class UnauthorizedToolRequest(Exception):
    pass


class GetOrderStatusArgs(BaseModel):
    order_id: str


class Tool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel]

    @abstractmethod
    async def execute(self, args: BaseModel, user_id: str) -> dict[str, Any]:
        pass


class GetOrderStatusTool(Tool):
    name = "get_order_status"
    description = "Get the status and estimated delivery date for an order."
    args_schema = GetOrderStatusArgs

    async def execute(self, args: BaseModel, user_id: str) -> dict[str, Any]:
        if not isinstance(args, GetOrderStatusArgs):
            raise TypeError("Invalid arguments for get_order_status")

        if ORDER_OWNERS.get(args.order_id) != user_id:
            raise UnauthorizedToolRequest()

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

    async def execute(
        self, name: str, arguments: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
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
            return await tool.execute(args, user_id)
        except UnauthorizedToolRequest:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"Failed to execute tool: {name}") from exc

    def get_registered_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.args_schema.model_json_schema(),
                },
            }
            for name, tool in self._tools.items()
        ]
