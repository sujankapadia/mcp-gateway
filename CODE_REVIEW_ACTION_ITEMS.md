# Code Review Action Items

This document analyzes the findings from the OpenAI Codex code review and provides actionable recommendations.

## Issue Analysis

### Issue 1: JSON-RPC Batch Messages Not Supported
**Severity:** High
**Status:** ✅ REAL ISSUE
**Location:** `src/mcp_gateway/parser.py:157-162`

**Problem:**
The `_extract_message()` method only tracks `{` and `}` for JSON objects. If a JSON-RPC batch request arrives (an array like `[{...}, {...}]`), the parser will never recognize the closing `]` and the buffer will stall indefinitely.

**Impact:**
- Silent failure if any MCP client sends batch requests
- Buffer grows without bound, consuming memory
- All subsequent messages are blocked

**Evidence:**
```python
# Current code only handles objects
if char == '{':
    depth += 1
elif char == '}':
    depth -= 1
    if depth == 0:
        # Found complete JSON object
        return message, remaining
# No handling for '[' and ']'
```

**Recommended Fix:**
Either:
1. Add array parsing support to handle batch requests
2. Document that batch requests are not supported and add explicit detection/rejection

**Priority:** Medium (MCP may not commonly use batch requests, but should be documented)

---

### Issue 2: Blocked Notifications Return Error Responses
**Severity:** Medium
**Status:** ✅ REAL ISSUE
**Location:** `src/mcp_gateway/gateway.py:153-161`

**Problem:**
When a message is blocked, the gateway always emits an error response via `create_block_response()`, even for notifications (messages without an `id`). JSON-RPC 2.0 spec explicitly forbids responses to notifications.

**Impact:**
- Protocol violation
- Could confuse clients or cause protocol errors
- Breaks JSON-RPC 2.0 compliance

**Evidence:**
```python
# Handle blocking
if scan_result.should_block:
    # Send error response back to client
    error_response = self.scanner.create_block_response(
        message,
        scan_result,
    )
    sys.stdout.write(error_response + "\n")
    sys.stdout.flush()
    continue
# No check for message.message_id being None
```

**Recommended Fix:**
```python
if scan_result.should_block:
    # Only send error response for requests (not notifications)
    if message.message_id is not None:
        error_response = self.scanner.create_block_response(
            message,
            scan_result,
        )
        sys.stdout.write(error_response + "\n")
        sys.stdout.flush()
    # For notifications, just drop silently when blocked
    continue
```

**Priority:** High (protocol violation)

---

### Issue 3: Missing `requests` Dependency
**Severity:** Medium
**Status:** ✅ REAL ISSUE
**Location:** `src/mcp_gateway/scanner.py:146`, `pyproject.toml`

**Problem:**
Webhook alerting imports `requests` library, but `requests` is not in `pyproject.toml` dependencies. Enabling webhooks will crash at runtime with `ModuleNotFoundError`.

**Impact:**
- Runtime crash when webhooks are configured
- Unexpected failure in production

**Evidence:**
```python
# scanner.py:146
import requests
```

```toml
# pyproject.toml:8-11
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]
# requests is missing
```

**Recommended Fix:**
Add to `pyproject.toml`:
```toml
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "requests>=2.31.0",  # For webhook alerting
]
```

Or make it optional:
```toml
[project.optional-dependencies]
webhooks = [
    "requests>=2.31.0",
]
```

**Priority:** High (crashes at runtime if webhooks enabled)

---

### Issue 4: Redaction Over-Replaces Matches
**Severity:** Low
**Status:** ✅ REAL ISSUE
**Location:** `src/mcp_gateway/scanner.py:122-125`

**Problem:**
Redaction uses `str.replace(match.group(0), ...)` which replaces **all** occurrences of that string in the message, not just the one at the matched position. The captured match positions (`match_start`, `match_end`) are recorded but never used for replacement.

**Impact:**
- Could redact unintended parts of the message
- If the same string appears multiple times in different contexts, all get redacted even if only one matched the rule

**Example:**
```python
message = '{"password": "secret123", "note": "use secret123 for testing"}'
# If rule matches first "secret123", both instances get redacted
```

**Evidence:**
```python
# Current code
if rule.action == ActionType.REDACT:
    redacted_text = redacted_text.replace(
        match.group(0),
        f"[REDACTED:{rule.name}]",
    )
# This replaces ALL occurrences, not just the matched one
```

**Recommended Fix:**
Use span-based replacement:
```python
if rule.action == ActionType.REDACT:
    # Collect all matches first, then replace from end to start
    # to preserve positions
    pass
# Or build new string using match positions
```

**Priority:** Low (redaction feature is rarely used, workaround: unique secrets)

---

### Issue 5: README Config Example Mismatch
**Severity:** Low
**Status:** ✅ REAL ISSUE
**Location:** `README.md:75`, `src/mcp_gateway/config.py:60`

**Problem:**
The README example uses `"auditLog"` (camelCase), but the config schema expects `audit_log` (snake_case). Pydantic will silently ignore the mismatched field.

**Impact:**
- Users following README example will have audit logging use default path
- No error is raised, making it hard to debug
- User configuration is silently ignored

**Evidence:**
```json
// README.md:75
"auditing": {
  "enabled": true,
  "auditLog": "~/.mcp-gateway/audit.jsonl"
}
```

```python
# config.py:60
audit_log: Path = Field(
    default_factory=lambda: Path.home() / ".mcp-gateway" / "audit.jsonl"
)
```

**Recommended Fix:**
Update README.md to use correct field name:
```json
"auditing": {
  "enabled": true,
  "audit_log": "~/.mcp-gateway/audit.jsonl"
}
```

**Priority:** Medium (user-facing documentation bug)

---

## Summary

**All 5 findings are REAL issues** requiring fixes:

| Issue | Severity | Impact | Effort |
|-------|----------|--------|--------|
| Batch messages not supported | High | Silent failure, buffer stall | Medium |
| Notification blocking | Medium | Protocol violation | Low |
| Missing requests dependency | Medium | Runtime crash | Low |
| Redaction over-replaces | Low | Incorrect behavior | Medium |
| README config mismatch | Low | User confusion | Low |

## Priority Fixes

### Priority 1: Critical (Fix Immediately)
1. **Add `requests` to dependencies** - Prevents runtime crashes
2. **Fix notification blocking** - Prevents protocol violations

### Priority 2: High (Fix Before Release)
3. **Fix README config example** - Prevents user confusion
4. **Document batch request limitation** - Or implement support

### Priority 3: Low (Fix When Possible)
5. **Fix redaction over-replacement** - Edge case, rarely used

## Recommended Actions

### Immediate (This PR)
- [ ] Add `requests>=2.31.0` to `pyproject.toml` dependencies
- [ ] Fix notification blocking by checking `message_id` before creating error response
- [ ] Update README.md to use `audit_log` instead of `auditLog`

### Short-term (Next Release)
- [ ] Add explicit batch request detection and rejection with clear error
- [ ] Document that batch requests are not supported
- [ ] Add unit test for notification blocking behavior
- [ ] Add integration test for webhook alerting

### Long-term (Future Enhancement)
- [ ] Implement proper batch request support
- [ ] Fix redaction to use span-based replacement
- [ ] Add configuration validation that warns about unused fields

## Open Questions

From the original code review:

1. **Do you want to support JSON-RPC batch requests?**
   - If yes: Need to implement array parsing in `_extract_message()`
   - If no: Should document limitation and add detection/rejection

2. **Is MCP traffic guaranteed to be newline-delimited JSON?**
   - Current parser assumes newline-delimited
   - If `Content-Length` framing is ever used, parser will fail
   - Need to clarify MCP protocol specification

## Testing Requirements

After fixes, ensure:
- [ ] Unit test: Notification blocked should not generate error response
- [ ] Unit test: Request blocked should generate error response
- [ ] Integration test: Webhook alerting works (requires `requests`)
- [ ] Integration test: Batch request is properly handled/rejected
- [ ] Config test: `audit_log` field is correctly parsed
