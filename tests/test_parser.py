"""Tests for JSON-RPC message parser."""

import pytest

from mcp_gateway.parser import MessageParser, MessageType


def test_parse_request():
    """Test parsing a JSON-RPC request."""
    parser = MessageParser()
    message = '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "echo"}}\n'

    messages = parser.feed(message)

    assert len(messages) == 1
    parsed = messages[0]
    assert parsed.message_type == MessageType.REQUEST
    assert parsed.method == "tools/call"
    assert parsed.params == {"name": "echo"}
    assert parsed.message_id == 1


def test_parse_response():
    """Test parsing a JSON-RPC response."""
    parser = MessageParser()
    message = '{"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}\n'

    messages = parser.feed(message)

    assert len(messages) == 1
    parsed = messages[0]
    assert parsed.message_type == MessageType.RESPONSE
    assert parsed.result == {"status": "ok"}
    assert parsed.message_id == 1


def test_parse_error():
    """Test parsing a JSON-RPC error response."""
    parser = MessageParser()
    message = '{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}\n'

    messages = parser.feed(message)

    assert len(messages) == 1
    parsed = messages[0]
    assert parsed.message_type == MessageType.ERROR
    assert parsed.error.code == -32601
    assert parsed.error.message == "Method not found"


def test_parse_notification():
    """Test parsing a JSON-RPC notification."""
    parser = MessageParser()
    message = '{"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}\n'

    messages = parser.feed(message)

    assert len(messages) == 1
    parsed = messages[0]
    assert parsed.message_type == MessageType.NOTIFICATION
    assert parsed.method == "notifications/tools/list_changed"
    assert parsed.message_id is None


def test_parse_multiple_messages():
    """Test parsing multiple messages in one feed."""
    parser = MessageParser()
    messages_str = (
        '{"jsonrpc": "2.0", "id": 1, "method": "test1"}\n'
        '{"jsonrpc": "2.0", "id": 2, "method": "test2"}\n'
    )

    messages = parser.feed(messages_str)

    assert len(messages) == 2
    assert messages[0].method == "test1"
    assert messages[1].method == "test2"


def test_parse_partial_message():
    """Test parsing partial messages with buffering."""
    parser = MessageParser()

    # Feed first half
    messages = parser.feed('{"jsonrpc": "2.0", "id": 1, ')
    assert len(messages) == 0  # Incomplete message

    # Feed second half
    messages = parser.feed('"method": "test"}\n')
    assert len(messages) == 1
    assert messages[0].method == "test"


def test_is_tool_call():
    """Test tool call detection."""
    parser = MessageParser()
    message = '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "echo"}}\n'

    messages = parser.feed(message)
    parsed = messages[0]

    assert parsed.is_tool_call()
    assert parsed.get_tool_name() == "echo"


def test_is_resource_read():
    """Test resource read detection."""
    parser = MessageParser()
    message = '{"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "file:///test"}}\n'

    messages = parser.feed(message)
    parsed = messages[0]

    assert parsed.is_resource_read()
    assert parsed.get_resource_uri() == "file:///test"


def test_invalid_json():
    """Test handling of invalid JSON."""
    parser = MessageParser()

    # This should not raise an exception
    messages = parser.feed("{invalid json}\n")

    # Should return empty list or handle gracefully
    # The parser will keep buffering until it finds valid JSON
    assert isinstance(messages, list)
