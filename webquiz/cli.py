#!/usr/bin/env python3
"""
CLI interface for WebQuiz Testing System.

Usage:
    webquiz           # Start server in foreground
    webquiz -d        # Start server as daemon
    webquiz --daemon  # Start server as daemon
    webquiz --help    # Show help
"""

import argparse
import sys
import os
import subprocess
import signal
import time
from pathlib import Path
import asyncio
from aiohttp import web

from .server import create_app


def get_pid_file_path():
    """Get the path to the PID file."""
    return Path.cwd() / "webquiz.pid"


def is_daemon_running():
    """Check if daemon is already running."""
    pid_file = get_pid_file_path()
    if not pid_file.exists():
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process is still running
        os.kill(pid, 0)  # This will raise OSError if process doesn't exist
        return True
    except (OSError, ValueError, FileNotFoundError):
        # Process is not running, remove stale PID file
        if pid_file.exists():
            pid_file.unlink()
        return False


def start_daemon():
    """Start the server as a daemon process."""
    if is_daemon_running():
        print("❌ Daemon is already running")
        return 1
    
    print("🚀 Starting webquiz daemon...")
    
    # Fork the process
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process
            # Wait a moment to check if child started successfully
            time.sleep(1)
            if is_daemon_running():
                print(f"✅ Daemon started successfully (PID: {pid})")
                print(f"🌐 Server running at http://localhost:8080")
                print(f"📄 Logs: server.log")
                print(f"⏹️  Stop with: kill {pid}")
                return 0
            else:
                print("❌ Failed to start daemon")
                return 1
        else:
            # Child process - become daemon
            os.setsid()  # Create new session
            
            # Fork again to ensure we're not session leader
            pid = os.fork()
            if pid > 0:
                os._exit(0)
            
            # Write PID file
            with open(get_pid_file_path(), 'w') as f:
                f.write(str(os.getpid()))
            
            # Redirect standard file descriptors
            with open('/dev/null', 'r') as f:
                os.dup2(f.fileno(), sys.stdin.fileno())
            
            # Keep stdout/stderr for now (they'll go to server.log anyway)
            
            # Change working directory to avoid holding locks
            os.chdir('/')
            
            # Set signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                pid_file = get_pid_file_path()
                if pid_file.exists():
                    pid_file.unlink()
                sys.exit(0)
            
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            # Start the server
            try:
                # Get config file from global variable set in main()
                config_file = getattr(start_daemon, '_config_file', 'config.yaml')
                run_server(config_file)
            except Exception as e:
                print(f"❌ Error starting server: {e}")
                pid_file = get_pid_file_path()
                if pid_file.exists():
                    pid_file.unlink()
                sys.exit(1)
    
    except OSError as e:
        print(f"❌ Fork failed: {e}")
        return 1


def stop_daemon():
    """Stop the daemon process."""
    if not is_daemon_running():
        print("❌ No daemon is running")
        return 1
    
    pid_file = get_pid_file_path()
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        print(f"⏹️  Stopping daemon (PID: {pid})...")
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to stop
        for _ in range(10):  # Wait up to 10 seconds
            time.sleep(1)
            if not is_daemon_running():
                print("✅ Daemon stopped successfully")
                return 0
        
        # Force kill if still running
        print("⚠️  Force killing daemon...")
        os.kill(pid, signal.SIGKILL)
        pid_file.unlink()
        print("✅ Daemon force stopped")
        return 0
        
    except (OSError, ValueError, FileNotFoundError) as e:
        print(f"❌ Error stopping daemon: {e}")
        return 1


def run_server(config_file: str = 'config.yaml'):
    """Run the server in foreground mode."""
    print("🚀 Starting WebQuiz Testing System...")
    print(f"📄 Using config file: {config_file}")
    print("🌐 Server will be available at: http://localhost:8080")
    print("⏹️  Press Ctrl+C to stop")
    
    async def start_server():
        app = await create_app(config_file)
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, 'localhost', 8080)
        await site.start()
        
        print("✅ Server started successfully")
        
        try:
            # Keep the server running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down server...")
        finally:
            await runner.cleanup()
    
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("✅ Server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='webquiz',
        description='WebQuiz - A modern web-based quiz and testing platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  webquiz                    Start server in foreground
  webquiz -d                 Start server as daemon
  webquiz --config custom.yaml    Use custom config file
  webquiz --stop             Stop daemon server
  webquiz --status           Check daemon status

The server will be available at http://localhost:8080
Questions are loaded from config.yaml (auto-created if missing)
User responses are saved to user_responses.csv
Server logs are written to server.log
        """
    )
    
    parser.add_argument(
        '-d', '--daemon',
        action='store_true',
        help='Run server as daemon in background'
    )
    
    parser.add_argument(
        '--stop',
        action='store_true',
        help='Stop daemon server'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check daemon status'
    )
    
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Handle daemon stop
    if args.stop:
        return stop_daemon()
    
    # Handle status check
    if args.status:
        if is_daemon_running():
            pid_file = get_pid_file_path()
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
            print(f"✅ Daemon is running (PID: {pid})")
            print(f"🌐 Server: http://localhost:8080")
            return 0
        else:
            print("❌ Daemon is not running")
            return 1
    
    # Handle daemon start
    if args.daemon:
        # Store config file for daemon process
        start_daemon._config_file = args.config
        return start_daemon()
    
    # Default: run server in foreground
    return run_server(args.config)


if __name__ == '__main__':
    sys.exit(main())