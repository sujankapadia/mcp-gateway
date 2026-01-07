#!/usr/bin/env python3
"""Live test with Context7 MCP server through gateway."""

import json
import subprocess
import sys
import time


def send_message(process, message):
    """Send a JSON-RPC message to the process."""
    msg_str = json.dumps(message) + "\n"
    print(f">>> Sending: {message['method']}")
    process.stdin.write(msg_str.encode())
    process.stdin.flush()


def read_response(process, timeout=5):
    """Read a response from the process."""
    import select

    # Check if data is available
    readable, _, _ = select.select([process.stdout], [], [], timeout)

    if readable:
        line = process.stdout.readline().decode().strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Failed to parse response: {e}")
                print(f"Raw line: {line}")
                return None
    return None


def main():
    print("=== Testing MCP Gateway with Context7 ===\n")

    # Start the gateway with Context7
    cmd = [
        "mcp-gateway",
        "stdio",
        "npx",
        "-y",
        "@upstash/context7-mcp",
        "--api-key",
        "ctx7sk-3590db53-ad56-4ba8-9b57-72ba3b38f07f"
    ]

    print(f"Starting gateway: {' '.join(cmd)}\n")

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        # Give it a moment to start
        time.sleep(2)

        # Check if process is still running
        if process.poll() is not None:
            stderr = process.stderr.read().decode()
            print(f"Gateway exited early!")
            print(f"stderr: {stderr}")
            return 1

        print("Gateway started successfully\n")

        # Test 1: Initialize
        print("Test 1: Initialize")
        send_message(process, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        })

        response = read_response(process, timeout=10)
        if response:
            if "result" in response:
                print(f"✓ Initialize successful")
                print(f"  Server: {response['result'].get('serverInfo', {}).get('name', 'unknown')}")
            elif "error" in response:
                print(f"✗ Initialize failed: {response['error']}")
                return 1
        else:
            print("✗ No response received")
            return 1

        print()

        # Test 2: List tools
        print("Test 2: List tools")
        send_message(process, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })

        response = read_response(process, timeout=10)
        if response:
            if "result" in response:
                tools = response['result'].get('tools', [])
                print(f"✓ Got {len(tools)} tools")
                for tool in tools[:3]:  # Show first 3
                    print(f"  - {tool.get('name', 'unknown')}")
                if len(tools) > 3:
                    print(f"  ... and {len(tools) - 3} more")
            elif "error" in response:
                print(f"✗ Tools list failed: {response['error']}")
        else:
            print("✗ No response received")

        print()
        print("✓ All tests completed!\n")

        # Terminate the process
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

        print("Gateway stopped\n")

        # Show some logs
        print("=== Recent Gateway Logs ===")
        subprocess.run(["mcp-gateway", "logs", "-n", "10"])

        print("\n=== Audit Trail ===")
        subprocess.run(["mcp-gateway", "audit", "-n", "5"])

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
