"""Tests for security scanner."""

import pytest

from mcp_gateway.config import ActionType, GatewayConfig, ScanRule, Severity
from mcp_gateway.parser import MessageParser
from mcp_gateway.scanner import SecurityScanner


@pytest.fixture
def config():
    """Create test configuration."""
    config = GatewayConfig()
    config.scanning.rules = [
        ScanRule(
            name="test-api-key",
            pattern=r"sk-[a-zA-Z0-9]{32,}",
            action=ActionType.ALERT,
            severity=Severity.HIGH,
        ),
        ScanRule(
            name="test-password",
            pattern=r"password\s*=\s*['\"]([^'\"]+)['\"]",
            action=ActionType.BLOCK,
            severity=Severity.CRITICAL,
        ),
        ScanRule(
            name="test-email",
            pattern=r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            action=ActionType.LOG,
            severity=Severity.LOW,
        ),
        ScanRule(
            name="test-redact",
            pattern=r"SECRET:\s*(\w+)",
            action=ActionType.REDACT,
            severity=Severity.MEDIUM,
        ),
    ]
    return config


def test_scan_no_violations(config):
    """Test scanning a clean message."""
    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = '{"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"data": "clean"}}\n'
    messages = parser.feed(message_str)
    parsed = messages[0]

    result = scanner.scan_message(parsed, "client->server")

    assert not result.has_violations()
    assert not result.should_block
    assert result.modified_message is None


def test_scan_with_api_key(config):
    """Test scanning message with API key."""
    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = '{"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"key": "sk-1234567890abcdefghijklmnopqrstuvwxyz"}}\n'
    messages = parser.feed(message_str)
    parsed = messages[0]

    result = scanner.scan_message(parsed, "client->server")

    assert result.has_violations()
    assert len(result.violations) == 1
    assert result.violations[0]["rule_name"] == "test-api-key"
    assert result.violations[0]["severity"] == "high"
    assert result.violations[0]["action"] == "alert"
    assert not result.should_block  # ALERT doesn't block


def test_scan_with_password_blocks(config):
    """Test scanning message with password triggers block."""
    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = '{"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"creds": "password=\\"secret123\\""}}\n'
    messages = parser.feed(message_str)
    parsed = messages[0]

    result = scanner.scan_message(parsed, "client->server")

    assert result.has_violations()
    assert result.should_block
    violation = result.violations[0]
    assert violation["rule_name"] == "test-password"
    assert violation["action"] == "block"


def test_scan_with_redaction(config):
    """Test scanning message with redaction."""
    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = '{"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"data": "SECRET: MySecretValue"}}\n'
    messages = parser.feed(message_str)
    parsed = messages[0]

    result = scanner.scan_message(parsed, "client->server")

    assert result.has_violations()
    assert not result.should_block
    assert result.modified_message is not None
    assert "[REDACTED:test-redact]" in result.modified_message
    assert "MySecretValue" not in result.modified_message


def test_scan_multiple_violations(config):
    """Test scanning message with multiple violations."""
    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = (
        '{"jsonrpc": "2.0", "id": 1, "method": "test", '
        '"params": {"key": "sk-abc123def456ghi789jkl012mno345pqr678", "email": "test@example.com"}}\n'
    )
    messages = parser.feed(message_str)
    parsed = messages[0]

    result = scanner.scan_message(parsed, "client->server")

    assert result.has_violations()
    assert len(result.violations) == 2

    rule_names = {v["rule_name"] for v in result.violations}
    assert "test-api-key" in rule_names
    assert "test-email" in rule_names


def test_scan_direction_filtering(config):
    """Test that scanning respects direction settings."""
    config.scanning.scan_request = True
    config.scanning.scan_response = False

    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = '{"jsonrpc": "2.0", "id": 1, "result": {"key": "sk-1234567890abcdefghijklmnopqrstuvwxyz"}}\n'
    messages = parser.feed(message_str)
    parsed = messages[0]

    # Should not scan server->client
    result = scanner.scan_message(parsed, "server->client")
    assert not result.has_violations()

    # Should scan client->server
    result = scanner.scan_message(parsed, "client->server")
    assert result.has_violations()


def test_create_block_response(config):
    """Test creating a block response."""
    scanner = SecurityScanner(config)
    parser = MessageParser()

    message_str = '{"jsonrpc": "2.0", "id": 42, "method": "test", "params": {"pwd": "password=\\"secret\\""}}\n'
    messages = parser.feed(message_str)
    parsed = messages[0]

    result = scanner.scan_message(parsed, "client->server")
    assert result.should_block

    error_response = scanner.create_block_response(parsed, result)

    # Parse the error response
    import json

    error_data = json.loads(error_response)
    assert error_data["jsonrpc"] == "2.0"
    assert error_data["id"] == 42
    assert "error" in error_data
    assert error_data["error"]["code"] == -32000
    assert "security policy" in error_data["error"]["message"].lower()


def test_scan_text(config):
    """Test scanning arbitrary text."""
    scanner = SecurityScanner(config)

    text = "Here is an API key: sk-1234567890abcdefghijklmnopqrstuvwxyz and email: user@test.com"

    violations = scanner.scan_text(text)

    assert len(violations) >= 2
    rule_names = {rule.name for rule, _ in violations}
    assert "test-api-key" in rule_names
    assert "test-email" in rule_names
