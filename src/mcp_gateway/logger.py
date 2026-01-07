"""Logging and auditing functionality for MCP Gateway."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import GatewayConfig, LogLevel
from .parser import ParsedMessage


class GatewayLogger:
    """Logger for MCP Gateway."""

    def __init__(self, config: GatewayConfig):
        """
        Initialize the logger.

        Args:
            config: Gateway configuration
        """
        self.config = config
        self._setup_logging()
        self._setup_auditing()

    def _setup_logging(self):
        """Set up logging destination."""
        if not self.config.logging.enabled:
            return

        log_dir = self.config.logging.destination
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        self.log_file = log_dir / f"gateway-{timestamp}.log"

    def _setup_auditing(self):
        """Set up audit logging."""
        if not self.config.auditing.enabled:
            return

        audit_log = self.config.auditing.audit_log
        audit_log.parent.mkdir(parents=True, exist_ok=True)
        self.audit_file = audit_log

    def log(self, level: LogLevel, message: str, **kwargs):
        """
        Log a message.

        Args:
            level: Log level
            message: Log message
            **kwargs: Additional fields to include
        """
        if not self.config.logging.enabled:
            return

        # Filter by log level
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]
        if levels.index(level) < levels.index(self.config.logging.level):
            return

        timestamp = datetime.now().isoformat()

        if self.config.logging.format == "json":
            log_entry = {
                "timestamp": timestamp,
                "level": level.value,
                "message": message,
                **kwargs,
            }
            log_line = json.dumps(log_entry)
        else:
            # Text format
            extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
            log_line = f"[{timestamp}] {level.value.upper()}: {message} {extra}"

        # Write to log file
        try:
            with open(self.log_file, "a") as f:
                f.write(log_line + "\n")
        except Exception as e:
            print(f"Error writing to log file: {e}", file=sys.stderr)

        # Also print to stderr for INFO and above
        if level in [LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]:
            print(log_line, file=sys.stderr)

    def debug(self, message: str, **kwargs):
        """Log a debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log an info message."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log a warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log an error message."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def audit(
        self,
        direction: str,
        message: ParsedMessage,
        server_name: str | None = None,
        blocked: bool = False,
        violations: list[dict[str, Any]] | None = None,
    ):
        """
        Log an audit entry.

        Args:
            direction: Message direction (client->server or server->client)
            message: Parsed message
            server_name: Name of the MCP server
            blocked: Whether the message was blocked
            violations: List of security violations detected
        """
        if not self.config.auditing.enabled:
            return

        timestamp = datetime.now().isoformat()

        audit_entry = {
            "timestamp": timestamp,
            "direction": direction,
            "server": server_name,
            "message_type": message.message_type.value,
            "message_id": message.message_id,
            "blocked": blocked,
        }

        # Add method for requests
        if message.method:
            audit_entry["method"] = message.method

        # Add tool name for tool calls
        if message.is_tool_call():
            audit_entry["tool"] = message.get_tool_name()

        # Add resource URI for resource reads
        if message.is_resource_read():
            audit_entry["resource_uri"] = message.get_resource_uri()

        # Add message content if configured
        if self.config.auditing.include_message_content:
            audit_entry["params"] = message.params
            audit_entry["result"] = message.result
            audit_entry["error"] = message.error.model_dump() if message.error else None

        # Add violations
        if violations:
            audit_entry["violations"] = violations

        # Write to audit log (JSONL format)
        try:
            with open(self.audit_file, "a") as f:
                f.write(json.dumps(audit_entry) + "\n")
        except Exception as e:
            self.error(f"Error writing to audit log: {e}")

    def log_violation(
        self,
        rule_name: str,
        severity: str,
        action: str,
        match: str,
        message: ParsedMessage,
        direction: str,
    ):
        """
        Log a security violation.

        Args:
            rule_name: Name of the rule that triggered
            severity: Severity level
            action: Action taken
            match: The matched text
            message: The message containing the violation
            direction: Message direction
        """
        self.warning(
            "Security violation detected",
            rule=rule_name,
            severity=severity,
            action=action,
            match=match[:50] + "..." if len(match) > 50 else match,
            direction=direction,
            method=message.method,
        )


class MetricsCollector:
    """Collects metrics for monitoring."""

    def __init__(self, config: GatewayConfig):
        """
        Initialize metrics collector.

        Args:
            config: Gateway configuration
        """
        self.config = config
        self.metrics = {
            "messages_processed": 0,
            "messages_by_direction": {"client->server": 0, "server->client": 0},
            "messages_by_type": {},
            "tool_calls": {},
            "violations": {},
            "blocked_messages": 0,
            "total_latency_ms": 0,
        }

    def record_message(self, message: ParsedMessage, direction: str):
        """Record a processed message."""
        if not self.config.metrics.collect_message_counts:
            return

        self.metrics["messages_processed"] += 1
        self.metrics["messages_by_direction"][direction] += 1

        msg_type = message.message_type.value
        self.metrics["messages_by_type"][msg_type] = (
            self.metrics["messages_by_type"].get(msg_type, 0) + 1
        )

        # Track tool calls
        if message.is_tool_call():
            tool_name = message.get_tool_name()
            if tool_name:
                self.metrics["tool_calls"][tool_name] = (
                    self.metrics["tool_calls"].get(tool_name, 0) + 1
                )

    def record_violation(self, rule_name: str, blocked: bool):
        """Record a security violation."""
        if not self.config.metrics.collect_violation_counts:
            return

        self.metrics["violations"][rule_name] = (
            self.metrics["violations"].get(rule_name, 0) + 1
        )

        if blocked:
            self.metrics["blocked_messages"] += 1

    def record_latency(self, latency_ms: float):
        """Record processing latency."""
        if not self.config.metrics.collect_latency:
            return

        self.metrics["total_latency_ms"] += latency_ms

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        return self.metrics.copy()

    def get_summary(self) -> str:
        """Get a human-readable metrics summary."""
        total = self.metrics["messages_processed"]
        blocked = self.metrics["blocked_messages"]
        avg_latency = (
            self.metrics["total_latency_ms"] / total if total > 0 else 0
        )

        summary = [
            f"Total messages: {total}",
            f"Blocked: {blocked}",
            f"Average latency: {avg_latency:.2f}ms",
        ]

        if self.metrics["tool_calls"]:
            summary.append("\nTop tool calls:")
            sorted_tools = sorted(
                self.metrics["tool_calls"].items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for tool, count in sorted_tools[:5]:
                summary.append(f"  {tool}: {count}")

        if self.metrics["violations"]:
            summary.append("\nViolations by rule:")
            for rule, count in self.metrics["violations"].items():
                summary.append(f"  {rule}: {count}")

        return "\n".join(summary)
