#!/bin/bash
# Quick verification script for MCP Gateway

echo "=== MCP Gateway Verification ==="
echo

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found"
    exit 1
fi
echo "✓ Python 3 found"
echo

# Install in development mode
echo "Installing MCP Gateway..."
pip install -e . > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Installation failed"
    exit 1
fi
echo "✓ Installation successful"
echo

# Verify CLI is accessible
echo "Checking CLI..."
mcp-gateway --version > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ CLI not accessible"
    exit 1
fi
echo "✓ CLI accessible"
echo

# Check version
echo "Version:"
mcp-gateway --version
echo

# Initialize config
echo "Initializing configuration..."
mcp-gateway config init --force > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Config initialization failed"
    exit 1
fi
echo "✓ Configuration initialized"
echo

# Validate config
echo "Validating configuration..."
mcp-gateway config validate ~/.mcp-gateway/config.json > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Config validation failed"
    exit 1
fi
echo "✓ Configuration valid"
echo

# Check project structure
echo "Checking project structure..."
for file in src/mcp_gateway/gateway.py src/mcp_gateway/parser.py src/mcp_gateway/scanner.py src/mcp_gateway/cli.py; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing: $file"
        exit 1
    fi
done
echo "✓ All core files present"
echo

# Check tests
echo "Checking tests..."
for file in tests/test_parser.py tests/test_scanner.py tests/mock_server.py; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing: $file"
        exit 1
    fi
done
echo "✓ All test files present"
echo

echo "=== ✓ Verification Complete ==="
echo
echo "MCP Gateway is ready to use!"
echo
echo "Quick start:"
echo "  1. Test with mock server: cd tests && ./test_integration.sh"
echo "  2. View configuration: mcp-gateway config show"
echo "  3. Read quick start: cat docs/QUICKSTART.md"
echo
echo "Integration with Claude Code:"
echo "  See: tests/test_context7.md"
