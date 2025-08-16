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

from .server import create_app, load_config_with_overrides


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
                print(f"🌐 Server running at http://0.0.0.0:8080 (accessible on network)")
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
                # Get config from global variable set in main()
                config = getattr(start_daemon, '_config', None)
                if config is None:
                    from .server import WebQuizConfig
                    config = WebQuizConfig()
                run_server(config)
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


def run_server(config):
    """Run the server in foreground mode."""
    print("🚀 Starting WebQuiz Testing System...")
    print(f"📁 Quizzes directory: {config.paths.quizzes_dir}")
    print(f"📝 Logs directory: {config.paths.logs_dir}")
    print(f"📊 CSV directory: {config.paths.csv_dir}")
    print(f"📂 Static directory: {config.paths.static_dir}")
    print(f"🔑 Master key: {'Set' if config.admin.master_key else 'Not set (admin disabled)'}")
    print(f"🌐 Server will be available at: http://{config.server.host}:{config.server.port} (accessible on network)")
    if config.admin.master_key:
        print(f"🔧 Admin panel: http://{config.server.host}:{config.server.port}/admin")
    print("⏹️  Press Ctrl+C to stop")
    
    async def start_server():
        app = await create_app(config)
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, config.server.host, config.server.port)
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
  webquiz                              Start server with defaults
  webquiz -d                           Start server as daemon
  webquiz --config server.yaml        Use configuration file
  webquiz --quizzes-dir my_quizzes     Use custom quizzes directory
  webquiz --master-key secret123       Set admin master key
  webquiz --logs-dir /var/log          Use custom logs directory
  webquiz --csv-dir /data              Use custom CSV directory
  webquiz --static /var/www/quiz       Use custom static files directory
  WEBQUIZ_MASTER_KEY=secret webquiz    Set master key via environment
  webquiz --config prod.yaml --master-key override  Mix config file with CLI overrides
  webquiz --stop                       Stop daemon server
  webquiz --status                     Check daemon status

The server will be available at http://0.0.0.0:8080 (accessible on network)
Quiz files loaded from quizzes/ directory (auto-created if missing)
Admin panel available at http://0.0.0.0:8080/admin (if master key is set)
User responses saved to data/{quiz_name}_user_responses_{suffix}.csv
Server logs written to logs/server_{suffix}.log
Static files served from static/ directory
CLI parameters always override config file values
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
        help='Path to YAML configuration file'
    )
    
    parser.add_argument(
        '--quizzes-dir',
        help='Path to quizzes directory (default: quizzes)'
    )
    
    parser.add_argument(
        '--master-key',
        help='Master key for admin access (can also use WEBQUIZ_MASTER_KEY env var)'
    )
    
    parser.add_argument(
        '--logs-dir',
        help='Directory for log files (default: logs/)'
    )
    
    parser.add_argument(
        '--csv-dir',
        help='Directory for CSV response files (default: data/)'
    )
    
    parser.add_argument(
        '--static',
        help='Path to static files directory (default: static)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Load configuration with CLI overrides
    config = load_config_with_overrides(
        config_path=args.config,
        quizzes_dir=args.quizzes_dir,
        master_key=args.master_key,
        logs_dir=args.logs_dir,
        csv_dir=args.csv_dir,
        static_dir=args.static
    )
    
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
            print(f"🌐 Server: http://0.0.0.0:8080 (accessible on network)")
            return 0
        else:
            print("❌ Daemon is not running")
            return 1
    
    # Handle daemon start
    if args.daemon:
        # Store config for daemon process
        start_daemon._config = config
        return start_daemon()
    
    # Default: run server in foreground
    return run_server(config)


if __name__ == '__main__':
    sys.exit(main())