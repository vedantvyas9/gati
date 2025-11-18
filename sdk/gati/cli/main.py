"""GATI CLI - Command-line interface for managing GATI services."""
import argparse
import subprocess
import sys
from pathlib import Path


def get_gati_root() -> Path:
    """Get the root directory of GATI installation."""
    # When installed via pip, docker-compose.yml is in the gati package directory
    import gati
    gati_pkg = Path(gati.__file__).parent
    return gati_pkg


def start_services(args):
    """Start GATI backend and dashboard using Docker Compose."""
    print("\n" + "=" * 70)
    print("🚀 GATI - Starting services...")
    print("=" * 70 + "\n")

    gati_root = get_gati_root()
    compose_file = gati_root / "docker-compose.yml"

    if not compose_file.exists():
        print(f"❌ Error: docker-compose.yml not found at {compose_file}")
        print("\nPlease ensure GATI is installed correctly:")
        print("  pip install --upgrade gati\n")
        sys.exit(1)

    # Build the docker-compose command
    cmd = ["docker-compose", "-f", str(compose_file), "up"]

    # If foreground flag is set, override detach (run in foreground)
    run_detached = args.detach and not args.foreground
    if run_detached:
        cmd.append("-d")

    try:
        print("Starting Docker containers...")
        result = subprocess.run(cmd, check=True)

        if run_detached:
            print("\n" + "=" * 70)
            print("✅ GATI services started successfully!")
            print("=" * 70)
            print("\nServices running at:")
            print("  • Backend:   http://localhost:8000")
            print("  • Dashboard: http://localhost:3000")
            print("\nTo stop services: gati stop")
            print("To view logs:     gati logs -f")
            print("=" * 70 + "\n")

        return result.returncode
    except FileNotFoundError:
        print("❌ Error: docker-compose not found.")
        print("\nPlease install Docker and Docker Compose:")
        print("  https://docs.docker.com/get-docker/\n")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting services: {e}")
        print("\nTroubleshooting:")
        print("  • Make sure Docker is running")
        print("  • Check if ports 8000 and 3000 are available")
        print("  • Run 'docker-compose logs' for details\n")
        sys.exit(1)


def stop_services(args):
    """Stop GATI backend and dashboard."""
    print("\n🛑 Stopping GATI services...")

    gati_root = get_gati_root()
    compose_file = gati_root / "docker-compose.yml"

    if not compose_file.exists():
        print(f"❌ Error: docker-compose.yml not found at {compose_file}")
        sys.exit(1)

    cmd = ["docker-compose", "-f", str(compose_file), "down"]

    try:
        subprocess.run(cmd, check=True)
        print("✅ GATI services stopped successfully.\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error stopping services: {e}")
        sys.exit(1)


def show_status(args):
    """Show status of GATI services."""
    gati_root = get_gati_root()
    compose_file = gati_root / "docker-compose.yml"
    
    cmd = ["docker-compose", "-f", str(compose_file), "ps"]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error getting status: {e}")
        sys.exit(1)


def show_logs(args):
    """Show logs from GATI services."""
    gati_root = get_gati_root()
    compose_file = gati_root / "docker-compose.yml"
    
    cmd = ["docker-compose", "-f", str(compose_file), "logs"]
    if args.follow:
        cmd.append("-f")
    if args.service:
        cmd.append(args.service)
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error showing logs: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GATI - Local-first observability for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gati start              Start backend and dashboard (detached mode)
  gati start -f           Start in foreground with logs visible
  gati stop               Stop all services
  gati status             Show service status
  gati logs               Show logs
  gati logs -f backend    Follow backend logs
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start GATI services")
    start_parser.add_argument(
        "-d", "--detach",
        action="store_true",
        default=True,
        help="Run in detached mode (default: True)"
    )
    start_parser.add_argument(
        "-f", "--foreground",
        action="store_true",
        help="Run in foreground (logs visible)"
    )
    start_parser.set_defaults(func=start_services)
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop GATI services")
    stop_parser.set_defaults(func=stop_services)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.set_defaults(func=show_status)
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show service logs")
    logs_parser.add_argument(
        "-f", "--follow",
        action="store_true",
        help="Follow log output"
    )
    logs_parser.add_argument(
        "service",
        nargs="?",
        choices=["backend", "dashboard", "postgres"],
        help="Specific service to show logs for"
    )
    logs_parser.set_defaults(func=show_logs)

    args = parser.parse_args()
    
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
