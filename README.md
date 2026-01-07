# MCP Gateway

A security gateway for Model Context Protocol (MCP) traffic, providing logging, auditing, and security scanning capabilities.

## Features

- **Transparent Proxying**: Works as a drop-in replacement for MCP servers
- **Security Scanning**: Detects API keys, credentials, PII, and other sensitive data
- **Audit Logging**: Comprehensive logging of all MCP tool calls and data access
- **Flexible Actions**: Log, alert, block, or redact sensitive information
- **stdio Support**: Works with local MCP servers using stdio transport
- **Easy Integration**: Simple CLI for wrapping existing MCP configurations

## Installation

```bash
cd mcp-gateway
pip install -e .
```

## Quick Start

### Wrap an existing MCP server

```bash
# Instead of running:
# npx @upstash/context7-mcp --api-key YOUR_KEY

# Run through the gateway:
mcp-gateway stdio npx @upstash/context7-mcp --api-key YOUR_KEY
```

### Configure with Claude Code

Original configuration (`.mcp.json`):
```json
{
  "context7": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp", "--api-key", "ctx7sk-xxx"]
  }
}
```

With gateway:
```json
{
  "context7": {
    "type": "stdio",
    "command": "mcp-gateway",
    "args": ["stdio", "npx", "-y", "@upstash/context7-mcp", "--api-key", "ctx7sk-xxx"]
  }
}
```

## Configuration

Create `~/.mcp-gateway/config.json`:

```json
{
  "logging": {
    "enabled": true,
    "destination": "~/.mcp-gateway/logs",
    "level": "info"
  },
  "auditing": {
    "enabled": true,
    "auditLog": "~/.mcp-gateway/audit.jsonl"
  },
  "scanning": {
    "enabled": true,
    "rules": [
      {
        "name": "api-keys",
        "pattern": "(sk-|ctx7sk-)[a-zA-Z0-9-]{32,}",
        "action": "alert",
        "severity": "high"
      }
    ]
  }
}
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/

# Lint
ruff check src/ tests/
```

## Architecture

See [mcp-gateway-architecture.md](../mcp-gateway-architecture.md) for detailed architecture documentation.

## License

MIT
