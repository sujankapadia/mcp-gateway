"""Command-line interface for MCP Gateway."""

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT_SCAN_RULES, GatewayConfig
from .gateway import run_gateway


def cmd_stdio(args):
    """Run stdio gateway wrapper."""
    if not args.command:
        print("Error: No server command specified", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    config_path = args.config
    if config_path:
        config = GatewayConfig.load_from_file(Path(config_path))
    else:
        config = GatewayConfig.load_or_create_default()

    # Run the gateway
    run_gateway(args.command, config_path)


def cmd_config_init(args):
    """Initialize default configuration."""
    config_path = Path(args.output) if args.output else GatewayConfig.get_default_config_path()

    if config_path.exists() and not args.force:
        print(f"Error: Configuration already exists at {config_path}", file=sys.stderr)
        print("Use --force to overwrite", file=sys.stderr)
        sys.exit(1)

    # Create config directory
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Create default configuration
    config = GatewayConfig()
    config.scanning.rules = DEFAULT_SCAN_RULES

    # Write to file
    config_dict = json.loads(config.model_dump_json())
    with open(config_path, "w") as f:
        json.dump(config_dict, f, indent=2)

    print(f"Configuration initialized at: {config_path}")


def cmd_config_validate(args):
    """Validate configuration file."""
    config_path = Path(args.config)

    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        config = GatewayConfig.load_from_file(config_path)
        print(f"✓ Configuration is valid: {config_path}")
        print(f"  - Logging: {'enabled' if config.logging.enabled else 'disabled'}")
        print(f"  - Auditing: {'enabled' if config.auditing.enabled else 'disabled'}")
        print(f"  - Scanning: {'enabled' if config.scanning.enabled else 'disabled'}")
        print(f"  - Scan rules: {len(config.scanning.rules)}")
    except Exception as e:
        print(f"✗ Configuration is invalid: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_show(args):
    """Show current configuration."""
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = GatewayConfig.get_default_config_path()

    if not config_path.exists():
        print(f"No configuration found at: {config_path}", file=sys.stderr)
        print("Run 'mcp-gateway config init' to create one", file=sys.stderr)
        sys.exit(1)

    config = GatewayConfig.load_from_file(config_path)
    print(config.model_dump_json(indent=2))


def cmd_install(args):
    """Install gateway wrapper for MCP servers."""
    # This would modify .mcp.json files to wrap servers
    # For now, just show instructions
    print("To install the gateway wrapper, update your .mcp.json configuration:")
    print()
    print("Original:")
    print('  "server": {')
    print('    "type": "stdio",')
    print('    "command": "npx",')
    print('    "args": ["-y", "@upstash/context7-mcp", "--api-key", "YOUR_KEY"]')
    print("  }")
    print()
    print("With gateway:")
    print('  "server": {')
    print('    "type": "stdio",')
    print('    "command": "mcp-gateway",')
    print('    "args": ["stdio", "npx", "-y", "@upstash/context7-mcp", "--api-key", "YOUR_KEY"]')
    print("  }")


def cmd_logs(args):
    """View gateway logs."""
    config = GatewayConfig.load_or_create_default()
    log_dir = config.logging.destination

    if not log_dir.exists():
        print(f"No logs found at: {log_dir}", file=sys.stderr)
        sys.exit(1)

    # Find most recent log file
    log_files = sorted(log_dir.glob("gateway-*.log"), reverse=True)
    if not log_files:
        print(f"No log files found in: {log_dir}", file=sys.stderr)
        sys.exit(1)

    log_file = log_files[0]
    print(f"Showing logs from: {log_file}\n")

    # Read and display logs
    with open(log_file) as f:
        if args.follow:
            # Simple tail -f implementation
            import time

            f.seek(0, 2)  # Go to end of file
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.1)
        else:
            # Show last N lines
            lines = f.readlines()
            start = max(0, len(lines) - args.lines)
            for line in lines[start:]:
                print(line.rstrip())


def cmd_audit(args):
    """View audit logs."""
    config = GatewayConfig.load_or_create_default()
    audit_log = config.auditing.audit_log

    if not audit_log.exists():
        print(f"No audit log found at: {audit_log}", file=sys.stderr)
        sys.exit(1)

    print(f"Showing audit log from: {audit_log}\n")

    # Read and display audit entries
    with open(audit_log) as f:
        lines = f.readlines()

        # Filter if requested
        if args.server or args.method:
            filtered = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if args.server and entry.get("server") != args.server:
                        continue
                    if args.method and entry.get("method") != args.method:
                        continue
                    filtered.append(line)
                except json.JSONDecodeError:
                    continue
            lines = filtered

        # Show last N lines
        start = max(0, len(lines) - args.lines)
        for line in lines[start:]:
            # Pretty print if requested
            if args.pretty:
                try:
                    entry = json.loads(line)
                    print(json.dumps(entry, indent=2))
                    print("-" * 80)
                except json.JSONDecodeError:
                    print(line.rstrip())
            else:
                print(line.rstrip())


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Gateway - Security gateway for Model Context Protocol traffic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="mcp-gateway 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # stdio command
    stdio_parser = subparsers.add_parser(
        "stdio",
        help="Run stdio gateway wrapper",
    )
    stdio_parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file",
    )
    stdio_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run the actual MCP server",
    )
    stdio_parser.set_defaults(func=cmd_stdio)

    # config commands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    # config init
    config_init_parser = config_subparsers.add_parser("init", help="Initialize configuration")
    config_init_parser.add_argument(
        "--output",
        type=str,
        help="Output path (default: ~/.mcp-gateway/config.json)",
    )
    config_init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration",
    )
    config_init_parser.set_defaults(func=cmd_config_init)

    # config validate
    config_validate_parser = config_subparsers.add_parser(
        "validate", help="Validate configuration"
    )
    config_validate_parser.add_argument(
        "config",
        type=str,
        help="Path to configuration file",
    )
    config_validate_parser.set_defaults(func=cmd_config_validate)

    # config show
    config_show_parser = config_subparsers.add_parser("show", help="Show configuration")
    config_show_parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file",
    )
    config_show_parser.set_defaults(func=cmd_config_show)

    # install command
    install_parser = subparsers.add_parser(
        "install",
        help="Install gateway wrapper for MCP servers",
    )
    install_parser.set_defaults(func=cmd_install)

    # logs command
    logs_parser = subparsers.add_parser("logs", help="View gateway logs")
    logs_parser.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Follow log output",
    )
    logs_parser.add_argument(
        "--lines",
        "-n",
        type=int,
        default=50,
        help="Number of lines to show (default: 50)",
    )
    logs_parser.set_defaults(func=cmd_logs)

    # audit command
    audit_parser = subparsers.add_parser("audit", help="View audit logs")
    audit_parser.add_argument(
        "--server",
        type=str,
        help="Filter by server name",
    )
    audit_parser.add_argument(
        "--method",
        type=str,
        help="Filter by method",
    )
    audit_parser.add_argument(
        "--lines",
        "-n",
        type=int,
        default=50,
        help="Number of lines to show (default: 50)",
    )
    audit_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON",
    )
    audit_parser.set_defaults(func=cmd_audit)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Handle config subcommands
    if args.command == "config" and not hasattr(args, "func"):
        config_parser.print_help()
        sys.exit(1)

    # Run the command
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
