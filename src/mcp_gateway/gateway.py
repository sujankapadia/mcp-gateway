"""Main gateway implementation for stdio MCP servers."""

import subprocess
import sys
import threading
import time
from typing import IO

from .config import ActionType, GatewayConfig
from .logger import GatewayLogger, MetricsCollector
from .parser import MessageParser
from .scanner import AlertManager, SecurityScanner


class StdioGateway:
    """Gateway wrapper for stdio-based MCP servers."""

    def __init__(
        self,
        server_command: list[str],
        config: GatewayConfig,
        server_name: str | None = None,
    ):
        """
        Initialize the gateway.

        Args:
            server_command: Command and arguments to run the actual MCP server
            config: Gateway configuration
            server_name: Optional name for the server (for logging)
        """
        self.server_command = server_command
        self.config = config
        self.server_name = server_name or server_command[0]

        # Initialize components
        self.logger = GatewayLogger(config)
        self.scanner = SecurityScanner(config)
        self.alert_manager = AlertManager(config)
        self.metrics = MetricsCollector(config)

        # Message parsers for each direction
        self.client_parser = MessageParser()
        self.server_parser = MessageParser()

        # Server process
        self.server_process: subprocess.Popen | None = None

    def start(self):
        """Start the gateway and spawn the actual MCP server."""
        self.logger.info(
            f"Starting MCP Gateway for {self.server_name}",
            command=" ".join(self.server_command),
        )

        try:
            # Spawn the actual MCP server process
            self.server_process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,  # Unbuffered
            )

            # Create threads for bidirectional forwarding
            client_to_server = threading.Thread(
                target=self._forward_client_to_server,
                daemon=True,
            )
            server_to_client = threading.Thread(
                target=self._forward_server_to_client,
                daemon=True,
            )
            stderr_handler = threading.Thread(
                target=self._handle_server_stderr,
                daemon=True,
            )

            # Start all threads
            client_to_server.start()
            server_to_client.start()
            stderr_handler.start()

            # Wait for the server process to exit
            self.server_process.wait()

            # Wait for threads to finish
            client_to_server.join(timeout=1)
            server_to_client.join(timeout=1)

        except Exception as e:
            self.logger.error(f"Error in gateway: {e}")
            raise
        finally:
            self._cleanup()

    def _forward_client_to_server(self):
        """Forward messages from client (stdin) to server with inspection."""
        try:
            while True:
                # Read from stdin
                line = sys.stdin.readline()
                if not line:
                    break

                start_time = time.time()

                # Parse messages
                messages = self.client_parser.feed(line)

                for message in messages:
                    # Record metrics
                    self.metrics.record_message(message, "client->server")

                    # Scan the message
                    scan_result = self.scanner.scan_message(message, "client->server")

                    # Log violations
                    for violation in scan_result.violations:
                        self.logger.log_violation(
                            rule_name=violation["rule_name"],
                            severity=violation["severity"],
                            action=violation["action"],
                            match=violation["match"],
                            message=message,
                            direction="client->server",
                        )
                        self.metrics.record_violation(
                            violation["rule_name"],
                            violation["action"] == ActionType.BLOCK.value,
                        )

                    # Send alerts if needed
                    if scan_result.has_violations():
                        self.alert_manager.send_alert(
                            message=message,
                            scan_result=scan_result,
                            direction="client->server",
                            server_name=self.server_name,
                        )

                    # Audit log
                    self.logger.audit(
                        direction="client->server",
                        message=message,
                        server_name=self.server_name,
                        blocked=scan_result.should_block,
                        violations=scan_result.violations if scan_result.has_violations() else None,
                    )

                    # Handle blocking
                    if scan_result.should_block:
                        # Only send error response for requests (not notifications)
                        # JSON-RPC 2.0 forbids responses to notifications (messages without id)
                        if message.message_id is not None:
                            error_response = self.scanner.create_block_response(
                                message,
                                scan_result,
                            )
                            sys.stdout.write(error_response + "\n")
                            sys.stdout.flush()
                        # For notifications, just drop silently when blocked
                        continue

                    # Forward to server (possibly redacted)
                    message_to_send = scan_result.modified_message or message.raw_message
                    if self.server_process and self.server_process.stdin:
                        self.server_process.stdin.write(
                            (message_to_send + "\n").encode("utf-8")
                        )
                        self.server_process.stdin.flush()

                # Record latency
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(latency_ms)

        except Exception as e:
            self.logger.error(f"Error in client->server forwarding: {e}")

    def _forward_server_to_client(self):
        """Forward messages from server (stdout) to client with inspection."""
        try:
            if not self.server_process or not self.server_process.stdout:
                return

            while True:
                # Read from server stdout
                line = self.server_process.stdout.readline()
                if not line:
                    break

                line = line.decode("utf-8")
                start_time = time.time()

                # Parse messages
                messages = self.server_parser.feed(line)

                for message in messages:
                    # Record metrics
                    self.metrics.record_message(message, "server->client")

                    # Scan the message
                    scan_result = self.scanner.scan_message(message, "server->client")

                    # Log violations
                    for violation in scan_result.violations:
                        self.logger.log_violation(
                            rule_name=violation["rule_name"],
                            severity=violation["severity"],
                            action=violation["action"],
                            match=violation["match"],
                            message=message,
                            direction="server->client",
                        )
                        self.metrics.record_violation(
                            violation["rule_name"],
                            violation["action"] == ActionType.BLOCK.value,
                        )

                    # Send alerts if needed
                    if scan_result.has_violations():
                        self.alert_manager.send_alert(
                            message=message,
                            scan_result=scan_result,
                            direction="server->client",
                            server_name=self.server_name,
                        )

                    # Audit log
                    self.logger.audit(
                        direction="server->client",
                        message=message,
                        server_name=self.server_name,
                        blocked=scan_result.should_block,
                        violations=scan_result.violations if scan_result.has_violations() else None,
                    )

                    # Handle blocking
                    if scan_result.should_block:
                        # Only send error response for requests (not notifications)
                        # JSON-RPC 2.0 forbids responses to notifications (messages without id)
                        if message.message_id is not None:
                            error_response = self.scanner.create_block_response(
                                message,
                                scan_result,
                            )
                            sys.stdout.write(error_response + "\n")
                            sys.stdout.flush()
                        # For notifications, just drop silently when blocked
                        continue

                    # Forward to client (possibly redacted)
                    message_to_send = scan_result.modified_message or message.raw_message
                    sys.stdout.write(message_to_send + "\n")
                    sys.stdout.flush()

                # Record latency
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(latency_ms)

        except Exception as e:
            self.logger.error(f"Error in server->client forwarding: {e}")

    def _handle_server_stderr(self):
        """Handle stderr from the server process."""
        try:
            if not self.server_process or not self.server_process.stderr:
                return

            while True:
                line = self.server_process.stderr.readline()
                if not line:
                    break

                line = line.decode("utf-8").strip()
                if line:
                    self.logger.debug(f"Server stderr: {line}")
                    # Also forward to our stderr
                    print(f"[{self.server_name}] {line}", file=sys.stderr)

        except Exception as e:
            self.logger.error(f"Error handling server stderr: {e}")

    def _cleanup(self):
        """Clean up resources."""
        self.logger.info(
            "Gateway shutting down",
            server=self.server_name,
        )

        # Print metrics summary
        if self.config.metrics.enabled:
            summary = self.metrics.get_summary()
            self.logger.info(f"Metrics summary:\n{summary}")

        # Terminate server process if still running
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()


def run_gateway(server_command: list[str], config_path: str | None = None, server_name: str | None = None):
    """
    Run the gateway with the specified server command.

    Args:
        server_command: Command and arguments for the MCP server
        config_path: Optional path to configuration file
        server_name: Optional friendly name for the server (for logging)
    """
    # Load configuration
    if config_path:
        from pathlib import Path

        config = GatewayConfig.load_from_file(Path(config_path))
    else:
        config = GatewayConfig.load_or_create_default()

    # Create and start gateway
    gateway = StdioGateway(
        server_command=server_command,
        config=config,
        server_name=server_name,
    )

    try:
        gateway.start()
    except KeyboardInterrupt:
        print("\nGateway interrupted by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Gateway error: {e}", file=sys.stderr)
        sys.exit(1)
