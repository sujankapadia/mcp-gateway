"""Configuration schema for MCP Gateway."""

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ActionType(str, Enum):
    """Actions to take when a rule matches."""

    LOG = "log"
    ALERT = "alert"
    BLOCK = "block"
    REDACT = "redact"


class Severity(str, Enum):
    """Severity levels for security findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    enabled: bool = True
    destination: Path = Field(default_factory=lambda: Path.home() / ".mcp-gateway" / "logs")
    level: LogLevel = LogLevel.INFO
    format: str = "json"  # json or text

    @field_validator("destination", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """Expand ~ in paths."""
        if isinstance(v, str):
            return Path(os.path.expanduser(v))
        return v


class AuditConfig(BaseModel):
    """Audit logging configuration."""

    enabled: bool = True
    audit_log: Path = Field(
        default_factory=lambda: Path.home() / ".mcp-gateway" / "audit.jsonl"
    )
    include_message_content: bool = True
    include_timestamps: bool = True

    @field_validator("audit_log", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """Expand ~ in paths."""
        if isinstance(v, str):
            return Path(os.path.expanduser(v))
        return v


class ScanRule(BaseModel):
    """Security scanning rule."""

    name: str
    description: str = ""
    pattern: str  # Regular expression pattern
    action: ActionType = ActionType.LOG
    severity: Severity = Severity.MEDIUM
    enabled: bool = True


class ScanningConfig(BaseModel):
    """Security scanning configuration."""

    enabled: bool = True
    rules: list[ScanRule] = Field(default_factory=list)
    scan_request: bool = True  # Scan client->server messages
    scan_response: bool = True  # Scan server->client messages


class AlertingConfig(BaseModel):
    """Alerting configuration."""

    enabled: bool = False
    webhook_url: str | None = None
    email: str | None = None


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    enabled: bool = True
    collect_latency: bool = True
    collect_message_counts: bool = True
    collect_violation_counts: bool = True


class GatewayConfig(BaseSettings):
    """Main gateway configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    auditing: AuditConfig = Field(default_factory=AuditConfig)
    scanning: ScanningConfig = Field(default_factory=ScanningConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    @classmethod
    def load_from_file(cls, config_path: Path) -> "GatewayConfig":
        """Load configuration from a JSON file."""
        import json

        with open(config_path) as f:
            config_data = json.load(f)
        return cls(**config_data)

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the default configuration file path."""
        return Path.home() / ".mcp-gateway" / "config.json"

    @classmethod
    def load_or_create_default(cls) -> "GatewayConfig":
        """Load config from default location or create default."""
        config_path = cls.get_default_config_path()
        if config_path.exists():
            return cls.load_from_file(config_path)
        return cls()


# Default security scanning rules
DEFAULT_SCAN_RULES = [
    ScanRule(
        name="openai-api-key",
        description="OpenAI API key",
        pattern=r"sk-[a-zA-Z0-9]{32,}",
        action=ActionType.ALERT,
        severity=Severity.CRITICAL,
    ),
    ScanRule(
        name="aws-access-key",
        description="AWS Access Key ID",
        pattern=r"AKIA[0-9A-Z]{16}",
        action=ActionType.BLOCK,
        severity=Severity.CRITICAL,
    ),
    ScanRule(
        name="aws-secret-key",
        description="AWS Secret Access Key",
        pattern=r"aws_secret_access_key\s*=\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?",
        action=ActionType.BLOCK,
        severity=Severity.CRITICAL,
    ),
    ScanRule(
        name="private-key",
        description="Private key (RSA, EC, OpenSSH)",
        pattern=r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
        action=ActionType.BLOCK,
        severity=Severity.CRITICAL,
    ),
    ScanRule(
        name="github-token",
        description="GitHub personal access token",
        pattern=r"gh[ps]_[a-zA-Z0-9]{36,}",
        action=ActionType.ALERT,
        severity=Severity.HIGH,
    ),
    ScanRule(
        name="jwt-token",
        description="JWT token",
        pattern=r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
        action=ActionType.ALERT,
        severity=Severity.MEDIUM,
    ),
    ScanRule(
        name="context7-api-key",
        description="Context7 API key",
        pattern=r"ctx7sk-[a-zA-Z0-9-]{32,}",
        action=ActionType.ALERT,
        severity=Severity.HIGH,
    ),
    ScanRule(
        name="generic-api-key",
        description="Generic API key pattern",
        pattern=r"api[_-]?key['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{16,})",
        action=ActionType.LOG,
        severity=Severity.MEDIUM,
    ),
    ScanRule(
        name="email-address",
        description="Email address",
        pattern=r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        action=ActionType.LOG,
        severity=Severity.LOW,
    ),
    ScanRule(
        name="credit-card",
        description="Credit card number",
        pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        action=ActionType.BLOCK,
        severity=Severity.CRITICAL,
    ),
    ScanRule(
        name="ssn",
        description="Social Security Number",
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        action=ActionType.BLOCK,
        severity=Severity.CRITICAL,
    ),
]
