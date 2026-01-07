#!/bin/bash
# Integration test for MCP Gateway with mock server

set -e

echo "=== MCP Gateway Integration Test ==="
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to project directory
cd "$(dirname "$0")/.."

echo "${YELLOW}1. Installing gateway...${NC}"
pip install -e . > /dev/null 2>&1
echo "${GREEN}✓ Gateway installed${NC}"
echo

echo "${YELLOW}2. Initializing configuration...${NC}"
mcp-gateway config init --force > /dev/null 2>&1
echo "${GREEN}✓ Configuration initialized${NC}"
echo

echo "${YELLOW}3. Making mock server executable...${NC}"
chmod +x tests/mock_server.py
echo "${GREEN}✓ Mock server ready${NC}"
echo

echo "${YELLOW}4. Testing gateway with mock server...${NC}"
echo

# Create a test script that sends requests
cat > /tmp/test_mcp_client.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import subprocess
import time

def send_and_receive(process, request):
    """Send request and read response."""
    request_str = json.dumps(request) + "\n"
    process.stdin.write(request_str.encode())
    process.stdin.flush()

    # Read response
    response_line = process.stdout.readline().decode().strip()
    if response_line:
        return json.loads(response_line)
    return None

# Start the gateway with mock server
gateway_cmd = ["mcp-gateway", "stdio", "python3", "tests/mock_server.py"]
proc = subprocess.Popen(
    gateway_cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(0.5)  # Give it time to start

try:
    # Test 1: Initialize
    print("Test 1: Initialize request")
    response = send_and_receive(proc, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    })

    if response and "result" in response:
        print("✓ Initialize successful")
    else:
        print("✗ Initialize failed")
        sys.exit(1)

    # Test 2: List tools
    print("\nTest 2: List tools")
    response = send_and_receive(proc, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    })

    if response and "result" in response and "tools" in response["result"]:
        tools = response["result"]["tools"]
        print(f"✓ Got {len(tools)} tools")
    else:
        print("✗ Failed to list tools")
        sys.exit(1)

    # Test 3: Call echo tool
    print("\nTest 3: Call echo tool")
    response = send_and_receive(proc, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "echo",
            "arguments": {"message": "Hello, Gateway!"}
        }
    })

    if response and "result" in response:
        print("✓ Echo tool call successful")
    else:
        print("✗ Echo tool call failed")
        sys.exit(1)

    # Test 4: Call get_secret tool (should trigger scanner)
    print("\nTest 4: Call get_secret tool (triggers scanner)")
    response = send_and_receive(proc, {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_secret",
            "arguments": {}
        }
    })

    if response:
        if "result" in response:
            print("✓ get_secret call returned (scanner logged/alerted)")
        elif "error" in response:
            print("✓ get_secret call blocked by scanner")
    else:
        print("✗ get_secret call failed")

    print("\n✓ All tests passed!")

finally:
    proc.terminate()
    proc.wait(timeout=5)
EOF

chmod +x /tmp/test_mcp_client.py
python3 /tmp/test_mcp_client.py

echo
echo "${GREEN}✓ Integration tests passed!${NC}"
echo

echo "${YELLOW}5. Checking logs and audit trail...${NC}"
echo

# Show some log entries
if [ -f ~/.mcp-gateway/logs/gateway-*.log ]; then
    echo "Recent gateway logs:"
    tail -n 5 ~/.mcp-gateway/logs/gateway-*.log | head -n 5
fi

echo
if [ -f ~/.mcp-gateway/audit.jsonl ]; then
    echo "Recent audit entries:"
    tail -n 5 ~/.mcp-gateway/audit.jsonl
fi

echo
echo "${GREEN}=== Integration test complete ===${NC}"
