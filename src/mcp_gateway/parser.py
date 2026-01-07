"""JSON-RPC message parser for MCP protocol."""

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """JSON-RPC message types."""

    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    NOTIFICATION = "notification"


class JsonRpcRequest(BaseModel):
    """JSON-RPC request message."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | list[Any] | None = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC response message."""

    jsonrpc: str = "2.0"
    id: int | str | None
    result: Any = None


class JsonRpcError(BaseModel):
    """JSON-RPC error object."""

    code: int
    message: str
    data: Any = None


class JsonRpcErrorResponse(BaseModel):
    """JSON-RPC error response message."""

    jsonrpc: str = "2.0"
    id: int | str | None
    error: JsonRpcError


class ParsedMessage(BaseModel):
    """Parsed JSON-RPC message with metadata."""

    message_type: MessageType
    raw_message: str
    parsed_data: JsonRpcRequest | JsonRpcResponse | JsonRpcErrorResponse

    # Extracted fields for easy access
    method: str | None = None  # For requests and notifications
    params: dict[str, Any] | list[Any] | None = None  # For requests
    result: Any = None  # For responses
    error: JsonRpcError | None = None  # For error responses
    message_id: int | str | None = None

    def is_tool_call(self) -> bool:
        """Check if this is a tool call request."""
        return self.message_type == MessageType.REQUEST and self.method == "tools/call"

    def is_resource_read(self) -> bool:
        """Check if this is a resource read request."""
        return self.message_type == MessageType.REQUEST and self.method == "resources/read"

    def get_tool_name(self) -> str | None:
        """Get tool name from a tools/call request."""
        if self.is_tool_call() and isinstance(self.params, dict):
            return self.params.get("name")
        return None

    def get_resource_uri(self) -> str | None:
        """Get resource URI from a resources/read request."""
        if self.is_resource_read() and isinstance(self.params, dict):
            return self.params.get("uri")
        return None


class MessageParser:
    """Parser for JSON-RPC messages with buffering support."""

    def __init__(self):
        """Initialize the parser."""
        self.buffer = ""

    def feed(self, data: str) -> list[ParsedMessage]:
        """
        Feed data to the parser and return any complete messages.

        Args:
            data: String data to parse

        Returns:
            List of parsed messages
        """
        self.buffer += data
        messages = []

        while self.buffer:
            # Try to find a complete JSON message
            message, self.buffer = self._extract_message(self.buffer)
            if message is None:
                break

            try:
                parsed = self.parse_message(message)
                if parsed:
                    messages.append(parsed)
            except Exception as e:
                # Log parse error but continue
                # In production, this would go to logger
                print(f"Error parsing message: {e}")
                continue

        return messages

    def _extract_message(self, buffer: str) -> tuple[str | None, str]:
        """
        Extract a single JSON message from the buffer.

        Returns:
            Tuple of (message, remaining_buffer)
        """
        buffer = buffer.lstrip()
        if not buffer:
            return None, ""

        # Try to parse JSON
        depth = 0
        in_string = False
        escape = False

        for i, char in enumerate(buffer):
            if escape:
                escape = False
                continue

            if char == '\\':
                escape = True
                continue

            if char == '"' and not escape:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    # Found complete JSON object
                    message = buffer[:i + 1]
                    remaining = buffer[i + 1:]
                    return message, remaining

        # No complete message found
        return None, buffer

    def parse_message(self, message: str) -> ParsedMessage | None:
        """
        Parse a single JSON-RPC message.

        Args:
            message: JSON string to parse

        Returns:
            Parsed message or None if invalid
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
            return None

        # Determine message type
        if "method" in data:
            # Request or notification
            if "id" in data:
                message_type = MessageType.REQUEST
            else:
                message_type = MessageType.NOTIFICATION

            parsed_data = JsonRpcRequest(**data)
            return ParsedMessage(
                message_type=message_type,
                raw_message=message,
                parsed_data=parsed_data,
                method=parsed_data.method,
                params=parsed_data.params,
                message_id=parsed_data.id,
            )

        elif "error" in data:
            # Error response
            parsed_data = JsonRpcErrorResponse(**data)
            return ParsedMessage(
                message_type=MessageType.ERROR,
                raw_message=message,
                parsed_data=parsed_data,
                error=parsed_data.error,
                message_id=parsed_data.id,
            )

        elif "result" in data:
            # Success response
            parsed_data = JsonRpcResponse(**data)
            return ParsedMessage(
                message_type=MessageType.RESPONSE,
                raw_message=message,
                parsed_data=parsed_data,
                result=parsed_data.result,
                message_id=parsed_data.id,
            )

        return None

    def reset(self):
        """Reset the parser buffer."""
        self.buffer = ""


def create_error_response(request_id: int | str | None, code: int, message: str, data: Any = None) -> str:
    """
    Create a JSON-RPC error response.

    Args:
        request_id: ID from the original request
        code: Error code
        message: Error message
        data: Additional error data

    Returns:
        JSON-RPC error response as string
    """
    error_response = JsonRpcErrorResponse(
        id=request_id,
        error=JsonRpcError(
            code=code,
            message=message,
            data=data,
        ),
    )
    return error_response.model_dump_json()
