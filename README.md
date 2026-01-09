# MCP Gateway

> [!WARNING]
> **NOT RECOMMENDED FOR USE YET - UNTESTED**
>
> This is a proof-of-concept implementation that has not been tested with real MCP servers. Do not use until it has been properly tested and validated.

A security gateway for Model Context Protocol (MCP) traffic, providing logging, auditing, and security scanning capabilities.

## Features

- **Transparent Proxying**: Works as a drop-in replacement for MCP servers
- **Security Scanning**: Detects API keys, credentials, PII, and other sensitive data
- **Audit Logging**: Comprehensive logging of all MCP tool calls and data access
- **Flexible Actions**: Log, alert, block, or redact sensitive information
- **stdio Support**: Works with local MCP servers using stdio transport
- **Easy Integration**: Simple CLI for wrapping existing MCP configurations

## Limitations

- **JSON-RPC Batch Requests**: Not currently supported. The gateway only handles single JSON-RPC messages per line. Batch requests (arrays of messages) will cause the parser to stall. If you need batch request support, please open an issue.

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

With gateway (recommended - with --name flag for better filtering):
```json
{
  "context7": {
    "type": "stdio",
    "command": "mcp-gateway",
    "args": ["stdio", "--name", "context7", "npx", "-y", "@upstash/context7-mcp", "--api-key", "ctx7sk-xxx"]
  }
}
```

The `--name` flag sets a friendly name for the server in logs and audit trails, making it easier to filter by server when viewing logs (`mcp-gateway audit --server context7`).

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
    "audit_log": "~/.mcp-gateway/audit.jsonl"
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
