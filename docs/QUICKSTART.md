# MCP Gateway Quick Start Guide

This guide will get you up and running with the MCP Gateway in minutes.

## Installation

```bash
cd mcp-gateway
pip install -e .
```

Verify installation:
```bash
mcp-gateway --version
```

## Initial Setup

### 1. Initialize Configuration

```bash
mcp-gateway config init
```

This creates `~/.mcp-gateway/config.json` with default settings including:
- Logging enabled
- Auditing enabled
- Security scanning with default rules
- Metrics collection enabled

### 2. View Configuration

```bash
mcp-gateway config show
```

### 3. Validate Configuration

```bash
mcp-gateway config validate ~/.mcp-gateway/config.json
```

## Testing

### Test with Mock Server

The quickest way to verify the gateway works:

```bash
# Run the integration test
cd tests
chmod +x test_integration.sh mock_server.py
./test_integration.sh
```

This will:
1. Install the gateway
2. Initialize configuration
3. Run tests against a mock MCP server
4. Show you logs and audit trails

### Test with Real MCP Server

Test with any real MCP server:

```bash
# Example: Test with npx-based server
mcp-gateway stdio npx -y @modelcontextprotocol/server-filesystem /tmp
```

Then send JSON-RPC requests via stdin:
```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
```

## Integration with Claude Code

### Step 1: Find Your MCP Configuration

Claude Code MCP servers are configured in:
- `.clauderc` (project-level)
- `.mcp.json` (project-level)
- `~/.config/claude/` (user-level)

### Step 2: Update Configuration

**Before (direct connection):**
```json
{
  "mcpServers": {
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp", "--api-key", "YOUR_KEY"]
    }
  }
}
```

**After (through gateway):**
```json
{
  "mcpServers": {
    "context7": {
      "type": "stdio",
      "command": "mcp-gateway",
      "args": ["stdio", "npx", "-y", "@upstash/context7-mcp", "--api-key", "YOUR_KEY"]
    }
  }
}
```

### Step 3: Restart Claude Code

Restart Claude Code to pick up the new configuration.

### Step 4: Verify It's Working

Use Claude Code normally, then check the gateway logs:

```bash
# View recent activity
mcp-gateway logs -n 20

# View audit trail
mcp-gateway audit --pretty

# View specific server
mcp-gateway audit --server context7
```

## Viewing Logs and Audits

### View Gateway Logs

```bash
# Last 50 lines
mcp-gateway logs

# Last 100 lines
mcp-gateway logs -n 100

# Follow logs in real-time
mcp-gateway logs -f
```

### View Audit Trail

```bash
# Last 50 audit entries
mcp-gateway audit

# Pretty-printed JSON
mcp-gateway audit --pretty

# Filter by server
mcp-gateway audit --server github

# Filter by method
mcp-gateway audit --method tools/call
```

### Raw Log Files

- Gateway logs: `~/.mcp-gateway/logs/gateway-YYYYMMDD.log`
- Audit log: `~/.mcp-gateway/audit.jsonl`

## Understanding Security Scanning

### Default Rules

The gateway comes with these default scanning rules:

1. **OpenAI API keys** (`sk-*`) - ALERT
2. **AWS Access Keys** (`AKIA*`) - BLOCK
3. **Private keys** (`-----BEGIN PRIVATE KEY-----`) - BLOCK
4. **GitHub tokens** (`ghp_*`, `ghs_*`) - ALERT
5. **JWT tokens** - ALERT
6. **Context7 API keys** (`ctx7sk-*`) - ALERT
7. **Email addresses** - LOG
8. **Credit cards** - BLOCK
9. **SSNs** - BLOCK

### Actions Explained

- **LOG**: Record in logs, allow through
- **ALERT**: Log + send alert (if webhook configured), allow through
- **BLOCK**: Prevent message from being sent, return error
- **REDACT**: Replace sensitive data with `[REDACTED]`, allow through

### Customizing Rules

Edit `~/.mcp-gateway/config.json`:

```json
{
  "scanning": {
    "enabled": true,
    "rules": [
      {
        "name": "my-custom-rule",
        "description": "Detect custom pattern",
        "pattern": "SECRET-[A-Z0-9]{16}",
        "action": "alert",
        "severity": "high",
        "enabled": true
      }
    ]
  }
}
```

Then validate:
```bash
mcp-gateway config validate ~/.mcp-gateway/config.json
```

## Common Use Cases

### Use Case 1: Audit All Tool Calls

Perfect for compliance and security monitoring.

**Setup:** Default configuration already logs all tool calls.

**View tool calls:**
```bash
mcp-gateway audit --method tools/call --pretty
```

**Example output:**
```json
{
  "timestamp": "2024-01-07T10:30:00.123Z",
  "direction": "client->server",
  "server": "github",
  "message_type": "request",
  "method": "tools/call",
  "tool": "create_or_update_file",
  "params": {
    "name": "create_or_update_file",
    "arguments": {
      "path": "src/app.py",
      "content": "..."
    }
  }
}
```

### Use Case 2: Prevent Secret Leakage

Block messages containing secrets.

**Setup:** Default rules already block AWS keys, private keys, credit cards, SSNs.

**Test it:**
1. Send a message with a secret through the gateway
2. Gateway will block it and return an error
3. Check logs: `mcp-gateway logs | grep -i "block"`

### Use Case 3: Monitor Specific Servers

Track activity for specific MCP servers.

**View server activity:**
```bash
mcp-gateway audit --server github --pretty
```

### Use Case 4: Alerting on Violations

Get notified when violations are detected.

**Setup webhook in config:**
```json
{
  "alerting": {
    "enabled": true,
    "webhook_url": "https://your-webhook.com/alerts"
  }
}
```

Alerts will be sent as POST requests with violation details.

## Troubleshooting

### Gateway not found after installation

```bash
# Check if installed
pip list | grep mcp-gateway

# Reinstall
pip install -e . --force-reinstall

# Check PATH
which mcp-gateway
```

### No logs being created

```bash
# Check configuration
mcp-gateway config show | grep -A5 logging

# Check directory exists
ls -la ~/.mcp-gateway/

# Create directory manually
mkdir -p ~/.mcp-gateway/logs
```

### Claude Code not connecting

1. Verify gateway works standalone:
   ```bash
   mcp-gateway stdio npx -y @modelcontextprotocol/server-filesystem /tmp
   ```

2. Check Claude Code logs for errors

3. Verify JSON syntax in config file

4. Try without gateway first to confirm MCP server works

### Performance issues

The gateway adds minimal overhead (<10ms per message). If you experience issues:

1. Disable scanning temporarily:
   ```json
   {"scanning": {"enabled": false}}
   ```

2. Reduce number of scan rules

3. Check system resources

## Next Steps

- **Customize scanning rules** for your organization
- **Set up alerting** via webhook or email
- **Integrate with SIEM** by forwarding audit logs
- **Create compliance reports** from audit data
- **Monitor metrics** for usage patterns

## Getting Help

- View CLI help: `mcp-gateway --help`
- Check command help: `mcp-gateway config --help`
- Review architecture: `../mcp-gateway-architecture.md`
- Run tests: `cd tests && ./test_integration.sh`

## Summary

You now have:
- ✓ Gateway installed and configured
- ✓ Default security rules active
- ✓ Logging and auditing enabled
- ✓ Ready to integrate with Claude Code

The gateway is now transparently intercepting and monitoring all MCP traffic!
