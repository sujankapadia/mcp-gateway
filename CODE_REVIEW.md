# Code Review Findings

## Findings

- **High:** JSON-RPC batch messages (arrays) will stall parsing because `_extract_message` only counts `{}` and never recognizes `[`/`]`; the buffer never drains once a batch arrives. `src/mcp_gateway/parser.py:125`
- **Medium:** When a message is blocked, the gateway always emits an error response even for notifications (no `id`). JSON-RPC forbids responses to notifications, so this can confuse clients or cause protocol errors. `src/mcp_gateway/gateway.py:152`
- **Medium:** Webhook alerting imports `requests`, but `requests` is not in `pyproject.toml` dependencies; enabling webhooks will crash at runtime. `src/mcp_gateway/scanner.py:216`, `pyproject.toml`
- **Low:** Redaction uses `str.replace` on the full message, so any identical substring elsewhere is redacted even if it didn’t match the rule (and match positions are ignored). Consider span-based replacement to avoid over-redaction. `src/mcp_gateway/scanner.py:115`
- **Low:** README config example uses `auditLog`, but the config schema expects `audit_log`; the sample config silently ignores the setting. `README.md:73`, `src/mcp_gateway/config.py`

## Open Questions / Assumptions

- Do you want to support JSON-RPC batch requests, or is the gateway explicitly restricted to single-object messages? If restricted, it should be documented to avoid silent stalls.
- Is MCP traffic guaranteed to be newline-delimited JSON? If a `Content-Length` framing is ever used, the parser will choke on headers.
