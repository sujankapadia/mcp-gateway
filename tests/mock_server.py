#!/usr/bin/env python3
"""Mock MCP server for testing the gateway."""

import json
import sys


def send_message(message: dict):
    """Send a JSON-RPC message to stdout."""
    print(json.dumps(message), flush=True)


def read_message() -> dict | None:
    """Read a JSON-RPC message from stdin."""
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def handle_initialize(msg_id):
    """Handle initialize request."""
    send_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": "mock-mcp-server",
                    "version": "0.1.0",
                },
            },
        }
    )


def handle_tools_list(msg_id):
    """Handle tools/list request."""
    send_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo back the input",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                            },
                            "required": ["message"],
                        },
                    },
                    {
                        "name": "get_secret",
                        "description": "Returns a fake secret (for testing scanner)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                ]
            },
        }
    )


def handle_tools_call(msg_id, params):
    """Handle tools/call request."""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name == "echo":
        message = arguments.get("message", "")
        send_message(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Echo: {message}",
                        }
                    ]
                },
            }
        )

    elif tool_name == "get_secret":
        # This will trigger the scanner
        send_message(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": "Here is a fake API key: sk-1234567890abcdefghijklmnopqrstuvwxyz",
                        }
                    ]
                },
            }
        )

    else:
        send_message(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}",
                },
            }
        )


def main():
    """Run the mock server."""
    print("Mock MCP server starting", file=sys.stderr)

    while True:
        message = read_message()
        if message is None:
            break

        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        if method == "initialize":
            handle_initialize(msg_id)

        elif method == "tools/list":
            handle_tools_list(msg_id)

        elif method == "tools/call":
            handle_tools_call(msg_id, params)

        else:
            # Unknown method
            send_message(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                }
            )


if __name__ == "__main__":
    main()
