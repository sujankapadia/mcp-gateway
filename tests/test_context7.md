# Context7 Integration Test Guide

This guide walks through testing the MCP Gateway with your actual Context7 MCP server.

## Prerequisites

1. Gateway installed: `pip install -e .`
2. Gateway configured: `mcp-gateway config init`
3. Context7 MCP server accessible via npx

## Test 1: Direct Test (Manual)

### Run Context7 through the gateway manually:

```bash
mcp-gateway stdio npx -y @upstash/context7-mcp --api-key ctx7sk-3590db53-ad56-4ba8-9b57-72ba3b38f07f
```

### Send test requests via stdin:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
```

Press Enter and check that you get a response.

### Check the logs:

```bash
mcp-gateway logs
```

### Check the audit trail:

```bash
mcp-gateway audit
```

You should see:
- The Context7 API key being logged/alerted (matches pattern `ctx7sk-*`)
- All MCP method calls being audited
- Any tool calls being logged

## Test 2: Integration with Claude Code

### Step 1: Locate your Claude Code project

The project should have a `.clauderc` or similar config file with the Context7 server configured.

### Step 2: Update the configuration

Original configuration:
```json
{
  "mcpServers": {
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@upstash/context7-mcp",
        "--api-key",
        "ctx7sk-3590db53-ad56-4ba8-9b57-72ba3b38f07f"
      ],
      "env": {}
    }
  }
}
```

Updated with gateway:
```json
{
  "mcpServers": {
    "context7": {
      "type": "stdio",
      "command": "mcp-gateway",
      "args": [
        "stdio",
        "npx",
        "-y",
        "@upstash/context7-mcp",
        "--api-key",
        "ctx7sk-3590db53-ad56-4ba8-9b57-72ba3b38f07f"
      ],
      "env": {}
    }
  }
}
```

### Step 3: Restart Claude Code

Restart Claude Code so it picks up the new configuration.

### Step 4: Use Context7

Use Context7 features in Claude Code normally. For example:
- Ask Claude to search your codebase
- Ask Claude to analyze code context
- Any tool that uses Context7

### Step 5: Verify gateway is working

Check that the gateway is logging all interactions:

```bash
# View recent logs
mcp-gateway logs -n 20

# View audit trail
mcp-gateway audit --pretty

# Filter by Context7 server
mcp-gateway audit --server context7

# Filter by specific method
mcp-gateway audit --method tools/call
```

### Step 6: Check for API key detection

The gateway should have detected and alerted on the Context7 API key:

```bash
mcp-gateway logs | grep "ctx7sk"
```

You should see warnings about the API key being detected.

## Expected Results

### Logs should show:
- Gateway starting with Context7 server
- Messages being processed in both directions
- API key detection: `ctx7sk-3590db53-ad56-4ba8-9b57-72ba3b38f07f`
- Any tool calls being made

### Audit log should contain:
- `initialize` request when Claude Code connects
- `tools/list` request
- `tools/call` requests for each Context7 tool invocation
- Parameters and results for each call (if configured)

### Example audit entry:
```json
{
  "timestamp": "2024-01-07T10:30:00.123Z",
  "direction": "client->server",
  "server": null,
  "message_type": "request",
  "message_id": 1,
  "blocked": false,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "claude-code",
      "version": "1.0.0"
    }
  }
}
```

## Troubleshooting

### Gateway not starting
- Check that `mcp-gateway` is in your PATH: `which mcp-gateway`
- Try installing again: `pip install -e .`
- Check logs in `~/.mcp-gateway/logs/`

### No logs being created
- Verify configuration: `mcp-gateway config show`
- Check that logging is enabled in config
- Check directory permissions: `ls -la ~/.mcp-gateway/`

### Claude Code can't connect to Context7
- Test the gateway manually first (Test 1 above)
- Check Claude Code's error messages
- Verify the configuration syntax is correct
- Try removing the gateway temporarily to confirm Context7 works directly

### API key not being detected
- Check scanner rules: `mcp-gateway config show | grep -A5 scanning`
- Verify the pattern matches: `ctx7sk-[a-zA-Z0-9-]{32,}`
- Check if scanning is enabled in configuration

## Performance Notes

The gateway adds minimal overhead:
- Message parsing: < 1ms
- Pattern scanning: < 5ms per rule
- Logging: < 1ms

You should not notice any latency when using Claude Code with the gateway.

## Security Verification

To verify the gateway is providing security:

1. **Check that API keys are being detected:**
   ```bash
   mcp-gateway logs | grep -i "violation"
   ```

2. **Verify all tool calls are audited:**
   ```bash
   mcp-gateway audit --method tools/call
   ```

3. **Check metrics:**
   ```bash
   # The gateway prints metrics on shutdown
   # Or check the last lines of the log file
   tail -n 20 ~/.mcp-gateway/logs/gateway-*.log
   ```

## Next Steps

Once the gateway is working with Context7:

1. **Customize scanner rules** for your needs
2. **Set up alerting** (webhook or email)
3. **Integrate with SIEM** by forwarding audit logs
4. **Monitor metrics** for unusual patterns
5. **Create compliance reports** from audit logs
