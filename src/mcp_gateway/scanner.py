"""Security scanning engine for detecting sensitive information."""

import json
import re
from typing import Any

from .config import ActionType, GatewayConfig, ScanRule
from .parser import ParsedMessage, create_error_response


class ScanResult:
    """Result of a security scan."""

    def __init__(self):
        """Initialize scan result."""
        self.violations: list[dict[str, Any]] = []
        self.should_block = False
        self.modified_message: str | None = None

    def add_violation(
        self,
        rule: ScanRule,
        match: str,
        match_start: int,
        match_end: int,
    ):
        """
        Add a violation to the result.

        Args:
            rule: The rule that was violated
            match: The matched text
            match_start: Start position of match
            match_end: End position of match
        """
        self.violations.append(
            {
                "rule_name": rule.name,
                "severity": rule.severity.value,
                "action": rule.action.value,
                "description": rule.description,
                "match": match,
                "match_start": match_start,
                "match_end": match_end,
            }
        )

        # If any rule says to block, we block
        if rule.action == ActionType.BLOCK:
            self.should_block = True

    def has_violations(self) -> bool:
        """Check if any violations were found."""
        return len(self.violations) > 0


class SecurityScanner:
    """Security scanner for MCP messages."""

    def __init__(self, config: GatewayConfig):
        """
        Initialize the scanner.

        Args:
            config: Gateway configuration
        """
        self.config = config
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self.compiled_rules = []
        if not self.config.scanning.enabled:
            return

        for rule in self.config.scanning.rules:
            if rule.enabled:
                try:
                    compiled = re.compile(rule.pattern, re.IGNORECASE)
                    self.compiled_rules.append((rule, compiled))
                except re.error as e:
                    # Log error but continue with other rules
                    print(f"Error compiling pattern for rule {rule.name}: {e}")

    def scan_message(
        self,
        message: ParsedMessage,
        direction: str,
    ) -> ScanResult:
        """
        Scan a message for security violations.

        Args:
            message: The message to scan
            direction: Message direction (client->server or server->client)

        Returns:
            Scan result with any violations found
        """
        result = ScanResult()

        if not self.config.scanning.enabled:
            return result

        # Check if we should scan this direction
        if direction == "client->server" and not self.config.scanning.scan_request:
            return result
        if direction == "server->client" and not self.config.scanning.scan_response:
            return result

        # Scan the raw message
        message_text = message.raw_message
        redacted_text = message_text

        for rule, pattern in self.compiled_rules:
            for match in pattern.finditer(message_text):
                result.add_violation(
                    rule=rule,
                    match=match.group(0),
                    match_start=match.start(),
                    match_end=match.end(),
                )

                # If action is REDACT, replace the match
                if rule.action == ActionType.REDACT:
                    redacted_text = redacted_text.replace(
                        match.group(0),
                        f"[REDACTED:{rule.name}]",
                    )

        # If we redacted anything, update the modified message
        if redacted_text != message_text:
            result.modified_message = redacted_text

        return result

    def scan_text(self, text: str) -> list[tuple[ScanRule, str]]:
        """
        Scan arbitrary text for violations.

        Args:
            text: Text to scan

        Returns:
            List of (rule, match) tuples
        """
        violations = []

        if not self.config.scanning.enabled:
            return violations

        for rule, pattern in self.compiled_rules:
            for match in pattern.finditer(text):
                violations.append((rule, match.group(0)))

        return violations

    def create_block_response(
        self,
        original_message: ParsedMessage,
        scan_result: ScanResult,
    ) -> str:
        """
        Create a JSON-RPC error response for a blocked message.

        Args:
            original_message: The original message that was blocked
            scan_result: The scan result containing violations

        Returns:
            JSON-RPC error response as string
        """
        violation_details = [
            {
                "rule": v["rule_name"],
                "severity": v["severity"],
                "description": v["description"],
            }
            for v in scan_result.violations
        ]

        return create_error_response(
            request_id=original_message.message_id,
            code=-32000,  # Server error
            message="Request blocked by security policy",
            data={
                "reason": "Security violations detected",
                "violations": violation_details,
                "contact": "Contact your administrator for more information",
            },
        )


class AlertManager:
    """Manages security alerts."""

    def __init__(self, config: GatewayConfig):
        """
        Initialize alert manager.

        Args:
            config: Gateway configuration
        """
        self.config = config

    def send_alert(
        self,
        message: ParsedMessage,
        scan_result: ScanResult,
        direction: str,
        server_name: str | None = None,
    ):
        """
        Send an alert for security violations.

        Args:
            message: The message containing violations
            scan_result: Scan result with violations
            direction: Message direction
            server_name: Name of the MCP server
        """
        if not self.config.alerting.enabled:
            return

        alert_data = {
            "timestamp": self._get_timestamp(),
            "server": server_name,
            "direction": direction,
            "message_type": message.message_type.value,
            "method": message.method,
            "violations": scan_result.violations,
        }

        # Send to webhook if configured
        if self.config.alerting.webhook_url:
            self._send_webhook(alert_data)

        # Send email if configured
        if self.config.alerting.email:
            self._send_email(alert_data)

    def _send_webhook(self, alert_data: dict[str, Any]):
        """
        Send alert to webhook.

        Args:
            alert_data: Alert data to send
        """
        try:
            import requests

            response = requests.post(
                self.config.alerting.webhook_url,
                json=alert_data,
                timeout=5,
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Error sending webhook alert: {e}")

    def _send_email(self, alert_data: dict[str, Any]):
        """
        Send alert via email.

        Args:
            alert_data: Alert data to send
        """
        # Placeholder for email implementation
        # In production, this would use SMTP or an email service API
        print(f"Email alert to {self.config.alerting.email}: {alert_data}")

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().isoformat()
