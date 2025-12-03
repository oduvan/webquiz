import asyncio
import httpx
import json
import csv
import yaml
import os
import socket
import subprocess
import platform
import zipfile
import tempfile
import shutil
import random
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiohttp import web, WSMsgType
import aiofiles
import logging
from io import StringIO
import ipaddress

from .config import WebQuizConfig, load_config_from_yaml
from .tunnel import TunnelManager

from webquiz import __version__ as package_version

# Logger will be configured in create_app() with custom log file
logger = logging.getLogger(__name__)


def read_package_resource(filename: str) -> str:
    """Read a file from the webquiz package resources.

    Args:
        filename: Name of the resource file to read

    Returns:
        Content of the resource file as string

    Raises:
        Various exceptions if file cannot be read
    """
    try:
        # Try modern importlib.resources first (Python 3.9+)
        import importlib.resources as pkg_resources

        return (pkg_resources.files("webquiz") / filename).read_text(encoding="utf-8")
    except (ImportError, AttributeError):
        # Fallback to pkg_resources for older Python versions
        import pkg_resources

        return pkg_resources.resource_string("webquiz", filename).decode("utf-8")


def get_package_version() -> str:
    """Get the webquiz package version.

    Returns:
        Package version string or "unknown" if version cannot be determined
    """
    try:
        return package_version
    except Exception as e:
        logger.exception(f"Failed to retrieve package version: {e}")
        return "unknown"


def get_file_version() -> str:
    """Read the webquiz package version directly from the __init__.py file.

    This evaluates the file to extract the __version__ variable, detecting if
    the package was updated while the server is running.

    Returns:
        Package version string from file or "unknown" if cannot be read
    """
    try:
        import importlib.resources as pkg_resources

        # Get the path to the webquiz package's __init__.py
        init_file = pkg_resources.files("webquiz") / "__init__.py"
        content = init_file.read_text(encoding="utf-8")

        # Execute the file content to extract __version__
        namespace = {}
        exec(content, namespace)

        if "__version__" in namespace:
            return namespace["__version__"]
        return "unknown"
    except Exception as e:
        logger.debug(f"Failed to read version from file: {e}")
        return "unknown"


def ensure_directory_exists(path: str) -> str:
    """Create directory if it doesn't exist and return the path.

    Args:
        path: Directory path to create

    Returns:
        The same path that was passed in
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_default_config_path() -> Optional[str]:
    """Get default config file path, creating one if it doesn't exist.

    Determines the appropriate location for the config file (binary directory
    or current working directory) and creates a default config file if none exists.

    Returns:
        Path to config file or None if creation failed
    """
    # Determine where to look for/create config file
    binary_dir = os.environ.get("WEBQUIZ_BINARY_DIR")
    if binary_dir:
        config_path = Path(binary_dir) / "webquiz.yaml"
    else:
        config_path = Path.cwd() / "webquiz.yaml"

    # If config file exists, return it
    if config_path.exists():
        return str(config_path)

    # Create default config file
    try:
        create_default_config_file(config_path)
        return str(config_path)
    except Exception as e:
        logger.warning(f"Could not create default config file at {config_path}: {e}")
        return None


def create_default_config_file(config_path: Path):
    """Create a default config file with example content.

    Args:
        config_path: Path where the config file should be created

    Raises:
        Various exceptions if file cannot be written
    """
    example_content = read_package_resource("server_config.yaml.example")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(example_content)
    logger.info(f"Created default config file: {config_path}")


def load_config_with_overrides(config_path: Optional[str] = None, **cli_overrides) -> WebQuizConfig:
    """Load configuration with CLI parameter overrides.

    Priority: CLI parameters > environment variables > config file > defaults

    Args:
        config_path: Optional path to config file
        **cli_overrides: CLI parameters that override config file values

    Returns:
        WebQuizConfig object with final merged configuration
    """
    # Use default config file if none provided
    if not config_path:
        config_path = get_default_config_path()

    # Start with config file or defaults
    if config_path:
        if os.path.exists(config_path):
            config = load_config_from_yaml(config_path)
            logger.info(f"Loaded configuration from: {config_path}")
        else:
            # Config file specified but doesn't exist - create from example
            create_default_config_file(Path(config_path))
            config = load_config_from_yaml(config_path)
            logger.info(f"Loaded configuration from newly created: {config_path}")
    else:
        config = WebQuizConfig()
        logger.info("Using default configuration")

    # Apply CLI overrides
    for key, value in cli_overrides.items():
        if value is not None:  # Only override if CLI parameter was provided
            if key in ["host", "port"]:
                setattr(config.server, key, value)
            elif key in ["quizzes_dir", "logs_dir", "csv_dir", "static_dir"]:
                setattr(config.paths, key, value)
            elif key in ["master_key"]:
                setattr(config.admin, key, value)

    # Environment variable override for master key
    env_master_key = os.environ.get("WEBQUIZ_MASTER_KEY")
    if env_master_key and not cli_overrides.get("master_key"):
        config.admin.master_key = env_master_key
        logger.info("Master key loaded from environment variable")

    # Store the actual config path that was used
    config.config_path = config_path

    return config


def log_startup_environment(config: WebQuizConfig):
    """Log important environment information at startup for troubleshooting.

    Logs system info, Python version, package versions, server configuration,
    and other useful debugging information to help diagnose issues.

    Args:
        config: WebQuizConfig object with server configuration
    """
    import sys
    import aiohttp

    logger.info("=" * 60)
    logger.info("WebQuiz Server Starting - Environment Information")
    logger.info("=" * 60)

    # WebQuiz version
    logger.info(f"WebQuiz version: {get_package_version()}")

    # Python information
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Python executable: {sys.executable}")

    # Platform and OS information
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"OS: {platform.system()} {platform.release()}")
    logger.info(f"Machine: {platform.machine()}")
    logger.info(f"Processor: {platform.processor() or 'Unknown'}")

    # Key dependency versions
    logger.info(f"aiohttp version: {aiohttp.__version__}")
    try:
        import yaml as yaml_module
        logger.info(f"PyYAML version: {yaml_module.__version__}")
    except (ImportError, AttributeError):
        pass

    # Working directory and paths
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Config file: {config.config_path or 'None (using defaults)'}")

    # Binary mode detection
    is_binary = os.environ.get("WEBQUIZ_IS_BINARY") == "1"
    binary_dir = os.environ.get("WEBQUIZ_BINARY_DIR")
    logger.info(f"Running as binary: {is_binary}")
    if binary_dir:
        logger.info(f"Binary directory: {binary_dir}")

    # Server configuration
    logger.info("-" * 40)
    logger.info("Server Configuration:")
    logger.info(f"  Host: {config.server.host}")
    logger.info(f"  Port: {config.server.port}")

    # Path configuration
    logger.info("Path Configuration:")
    logger.info(f"  Quizzes directory: {config.paths.quizzes_dir}")
    logger.info(f"  Logs directory: {config.paths.logs_dir}")
    logger.info(f"  CSV directory: {config.paths.csv_dir}")
    logger.info(f"  Static directory: {config.paths.static_dir}")

    # Admin configuration (without exposing master key)
    logger.info("Admin Configuration:")
    logger.info(f"  Master key set: {bool(config.admin.master_key)}")
    logger.info(f"  Trusted IPs: {config.admin.trusted_ips}")

    # Registration configuration
    logger.info("Registration Configuration:")
    logger.info(f"  Approval required: {config.registration.approve}")
    logger.info(f"  Username label: {config.registration.username_label}")
    logger.info(f"  Custom fields: {config.registration.fields}")

    # Tunnel configuration
    if config.tunnel.server:
        logger.info("Tunnel Configuration:")
        logger.info(f"  Server: {config.tunnel.server}")
        logger.info(f"  Public key path: {config.tunnel.public_key}")
        logger.info(f"  Private key path: {config.tunnel.private_key}")
        if config.tunnel.socket_name:
            logger.info(f"  Socket name: {config.tunnel.socket_name}")

    # Network interfaces
    try:
        interfaces = get_network_interfaces()
        if interfaces:
            logger.info(f"Network interfaces: {', '.join(interfaces)}")
        else:
            logger.info("Network interfaces: No non-loopback interfaces found")
    except Exception as e:
        logger.info(f"Network interfaces: Unable to retrieve ({e})")

    # Hostname
    try:
        logger.info(f"Hostname: {socket.gethostname()}")
    except Exception:
        pass

    logger.info("=" * 60)


def get_client_ip(request):
    """Extract client IP address from request, handling proxies.

    Checks X-Forwarded-For and X-Real-IP headers for proxied requests.

    Args:
        request: aiohttp request object

    Returns:
        Client IP address as string, defaults to "127.0.0.1"
    """
    client_ip = request.remote or "127.0.0.1"
    if "X-Forwarded-For" in request.headers:
        # Handle proxy/load balancer forwarded IPs (take the first one)
        client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
    elif "X-Real-IP" in request.headers:
        client_ip = request.headers["X-Real-IP"]
    return client_ip


def is_loopback_address(ip_str: str) -> bool:
    """Check if an IP address is a loopback address.

    Uses the ipaddress module to properly check the entire loopback range
    (127.0.0.0/8 for IPv4 and ::1 for IPv6).

    Args:
        ip_str: IP address string to check

    Returns:
        True if the address is loopback or invalid, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_loopback
    except ValueError:
        # Invalid IP addresses are treated as loopback (excluded) for safety
        return True


def get_network_interfaces():
    """Get all network interfaces and their IP addresses.

    Returns list of non-localhost IP addresses available on the system.
    Excludes all loopback addresses (127.0.0.0/8 and ::1).

    Returns:
        List of IP address strings (excludes loopback addresses)
    """
    interfaces = []
    # Get hostname
    hostname = socket.gethostname()

    # Get all IP addresses associated with the hostname
    ip_addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
    for ip_info in ip_addresses:
        ip = ip_info[4][0]
        if not is_loopback_address(ip):
            interfaces.append(ip)

    # Also try to get more interface info on Unix systems
    if platform.system() != "Windows":
        try:
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                for ip in ips:
                    if ip not in interfaces and not is_loopback_address(ip):
                        interfaces.append(ip)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

    return list(set(interfaces))  # Remove duplicates


def admin_auth_required(func):
    """Decorator to require session cookie authentication for admin endpoints.

    Restricts access to local/private networks only.
    Bypasses authentication for requests from trusted IPs.
    Requires valid session cookie (obtained via /api/admin/auth).

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function with authentication check
    """

    async def wrapper(self, request):

        # Get client IP
        client_ip = get_client_ip(request)

        # Check if IP is from local/private network
        try:
            ip_obj = ipaddress.ip_address(client_ip)
            if not ip_obj.is_private:
                return web.json_response({"error": "Доступ заборонено: тільки для локальної мережі"}, status=403)
        except ValueError:
            # Invalid IP format - deny access
            return web.json_response({"error": "Доступ заборонено: невірна IP адреса"}, status=403)

        # Check if it's in trusted list (bypass authentication)
        if hasattr(self, "admin_config") and client_ip in self.admin_config.trusted_ips:
            return await func(self, request)

        # Check if master key is configured
        if not self.master_key:
            return web.json_response({"error": "Admin functionality disabled - no master key set"}, status=403)

        # Check for valid session cookie
        session_token = request.cookies.get("admin_session")
        if session_token and hasattr(self, "admin_sessions") and session_token in self.admin_sessions:
            return await func(self, request)

        return web.json_response({"error": "Недійсний або відсутній сеанс"}, status=401)

    return wrapper


def local_network_only(func):
    """Decorator to restrict access to local/private networks only.

    Automatically detects private IP addresses (RFC 1918) and blocks public IPs.
    Private ranges: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
    Also supports IPv6 private ranges (::1, fc00::/7, fe80::/10).

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function with network check
    """

    async def wrapper(self, request):
        client_ip = get_client_ip(request)

        try:
            ip_obj = ipaddress.ip_address(client_ip)

            # Check if IP is private/local
            if not ip_obj.is_private:
                return web.json_response({"error": "Доступ заборонено: тільки для локальної мережі"}, status=403)
        except ValueError:
            # Invalid IP format - deny access
            return web.json_response({"error": "Доступ заборонено: невірна IP адреса"}, status=403)

        return await func(self, request)

    return wrapper


@web.middleware
async def error_middleware(request, handler):
    """Global error handling middleware.

    Catches all unexpected exceptions, logs them with full traceback, and returns 500 error.
    Allows HTTPException to pass through for proper HTTP status codes.

    Args:
        request: aiohttp request object
        handler: Request handler function

    Returns:
        Response from handler or formatted error response
    """
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Error handling {request.method} {request.path} from {request.remote}: {type(e).__name__}: {e}"
        )
        return web.json_response({"error": str(e)}, status=500)


class TestingServer:
    def __init__(self, config: WebQuizConfig):
        """Initialize testing server with configuration.

        Args:
            config: WebQuizConfig object with server settings
        """
        self.config = config
        self.quizzes_dir = config.paths.quizzes_dir
        self.master_key = config.admin.master_key
        self.admin_config = config.admin  # Store admin config for IP whitelist access
        self.current_quiz_file = None  # Will be set when quiz is selected
        self.logs_dir = config.paths.logs_dir
        self.csv_dir = config.paths.csv_dir
        self.static_dir = config.paths.static_dir
        self.log_file = None  # Will be set during initialization
        self.csv_file = None  # Will be set when quiz is selected (answers CSV)
        self.user_csv_file = None  # Will be set when quiz is selected (users CSV)
        self.quiz_title = "Система Тестування"  # Default title, updated when quiz is loaded
        self.show_right_answer = True  # Default setting, updated when quiz is loaded
        self.users: Dict[str, Dict[str, Any]] = {}  # user_id -> user data
        self.questions: List[Dict[str, Any]] = []
        self.user_responses: List[Dict[str, Any]] = []
        self.user_progress: Dict[str, int] = {}  # user_id -> last_answered_question_id
        self.question_start_times: Dict[str, datetime] = {}  # user_id -> question_start_time
        self.user_stats: Dict[str, Dict[str, Any]] = {}  # user_id -> final stats for completed users
        self.user_answers: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> list of answers for stats calculation

        # Live stats WebSocket infrastructure
        self.websocket_clients: List[web.WebSocketResponse] = []  # Connected WebSocket clients (live stats)
        self.admin_websocket_clients: List[web.WebSocketResponse] = []  # Connected admin WebSocket clients
        self.live_stats: Dict[str, Dict[int, str]] = {}  # user_id -> {question_id: state}

        # SSH Tunnel infrastructure
        self.tunnel_manager = None  # Will be initialized if tunnel is configured

        # Admin session storage for cookie-based authentication
        self.admin_sessions: Dict[str, datetime] = {}  # session_token -> creation_time

        # Preload templates
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """Preload all templates at startup.

        Returns:
            Dictionary mapping template filenames to their content
        """
        templates = {}
        template_files = [
            "index.html",
            "admin.html",
            "files.html",
            "live_stats.html",
            "quiz_selection_required.html",
            "template_error.html",
        ]

        for template_file in template_files:
            try:
                templates[template_file] = read_package_resource(f"templates/{template_file}")
                logger.info(f"Loaded template: {template_file}")
            except Exception as e:
                logger.warning(f"Failed to load template {template_file}: {e}")

        return templates

    def generate_log_path(self) -> str:
        """Generate log file path in logs directory with simple numeric naming.

        Finds the next available number (0001, 0002, etc.) for the log file.

        Returns:
            Path to the new log file
        """
        ensure_directory_exists(self.logs_dir)

        # Find the next available number
        suffix = 1
        while True:
            log_path = os.path.join(self.logs_dir, f"{suffix:04d}.log")
            if not os.path.exists(log_path):
                return log_path
            suffix += 1

    def generate_csv_path(self, quiz_name: str, csv_type: str = "answers") -> str:
        """Generate CSV file path in CSV directory with quiz name and numeric naming.

        Ensures both answers and users CSVs use the same numeric suffix.

        Args:
            quiz_name: Name of the quiz file
            csv_type: Type of CSV - 'answers' or 'users'

        Returns:
            Path to CSV file (answers: quiz_0001.csv, users: quiz_0001.users.csv)
        """
        ensure_directory_exists(self.csv_dir)

        # Clean quiz name (remove extension)
        quiz_prefix = quiz_name.replace(".yaml", "").replace(".yml", "")

        # Find the next available number for this quiz
        suffix = 1
        while True:
            if csv_type == "users":
                csv_path = os.path.join(self.csv_dir, f"{quiz_prefix}_{suffix:04d}.users.csv")
            else:  # answers
                csv_path = os.path.join(self.csv_dir, f"{quiz_prefix}_{suffix:04d}.csv")

            # Check both files to ensure they use the same number
            answers_csv = os.path.join(self.csv_dir, f"{quiz_prefix}_{suffix:04d}.csv")
            users_csv = os.path.join(self.csv_dir, f"{quiz_prefix}_{suffix:04d}.users.csv")

            if not os.path.exists(answers_csv) and not os.path.exists(users_csv):
                return csv_path
            suffix += 1

    def reset_server_state(self):
        """Reset all server state for new quiz.

        Clears users, responses, progress, stats, and live stats data.
        """
        self.users.clear()
        self.user_responses.clear()
        self.user_progress.clear()
        self.question_start_times.clear()
        self.user_stats.clear()
        self.user_answers.clear()
        self.live_stats.clear()
        logger.info("Server state reset for new quiz")

    async def list_available_quizzes(self):
        """List all available quiz files in quizzes directory.

        Returns:
            Sorted list of quiz filenames (.yaml and .yml files)
        """
        quiz_files = []
        if os.path.exists(self.quizzes_dir):
            for filename in os.listdir(self.quizzes_dir):
                if filename.endswith((".yaml", ".yml")):
                    quiz_files.append(filename)
        return sorted(quiz_files)

    async def switch_quiz(self, quiz_filename: str):
        """Switch to a different quiz file and reset server state.

        Resets all user data, loads new questions, regenerates index.html,
        and notifies connected WebSocket clients.

        Args:
            quiz_filename: Name of the quiz file to switch to

        Raises:
            ValueError: If quiz file doesn't exist
        """
        quiz_path = os.path.join(self.quizzes_dir, quiz_filename)
        if not os.path.exists(quiz_path):
            raise ValueError(f"Quiz file not found: {quiz_filename}")

        # Reset server state
        self.reset_server_state()

        # Update current quiz and CSV filenames (both answers and users)
        self.current_quiz_file = quiz_path
        self.csv_file = self.generate_csv_path(quiz_filename, "answers")
        self.user_csv_file = self.generate_csv_path(quiz_filename, "users")

        # Load new questions
        await self.load_questions_from_file(quiz_path)

        # Regenerate index.html with new questions
        await self.create_default_index_html()

        # Notify WebSocket clients about quiz switch
        await self.broadcast_to_websockets(
            {
                "type": "quiz_switched",
                "current_quiz": quiz_filename,
                "questions": self.questions,
                "total_questions": len(self.questions),
                "message": f"Quiz switched to: {quiz_filename}",
            }
        )

        logger.info(f"Switched to quiz: {quiz_filename}, CSV: {self.csv_file}")

    async def create_admin_selection_page(self):
        """Create a page informing admin to select a quiz first.

        Displays list of available quizzes and instructs admin to use
        the admin panel to select one.
        """
        ensure_directory_exists(self.static_dir)
        index_path = f"{self.static_dir}/index.html"

        # Get list of available quizzes for display
        available_quizzes = await self.list_available_quizzes()
        quiz_list_html = ""
        for quiz in available_quizzes:
            quiz_list_html += f"<li>{quiz}</li>"

        # Load template and replace placeholders
        template_content = self.templates.get("quiz_selection_required.html", "")
        selection_html = template_content.replace("{{QUIZ_LIST}}", quiz_list_html)

        async with aiofiles.open(index_path, "w", encoding="utf-8") as f:
            await f.write(selection_html)
        logger.info(f"Created admin selection page: {index_path}")

    async def initialize_log_file(self):
        """Initialize new log file with unique suffix in logs directory.

        Creates the log file and logs initial server start message.
        """

        # Generate log file path
        self.log_file = self.generate_log_path()
        # Create the new log file
        with open(self.log_file, "w") as f:
            f.write("")
        logger.info(f"=== Server Started - New Log File Created: {self.log_file} ===")

    async def initialize_tunnel(self):
        """Initialize SSH tunnel if configured.

        Checks if tunnel is configured, validates/generates keys, but does not
        auto-connect. Connection is initiated by admin via button click.
        """
        if not self.config.tunnel.server:
            logger.info("SSH tunnel not configured, skipping initialization")
            return

        logger.info(f"Initializing SSH tunnel for server: {self.config.tunnel.server}")

        # Create tunnel manager
        self.tunnel_manager = TunnelManager(self.config.tunnel, local_port=self.config.server.port)

        # Set up status callback to broadcast changes to admin clients
        async def tunnel_status_callback(status):
            # Include configured and server fields in status updates
            tunnel_update = {
                "configured": True,
                "server": self.config.tunnel.server,
                "socket_name": self.config.tunnel.socket_name,
                **status,
            }
            await self.broadcast_to_admin_websockets({"type": "tunnel_status", "tunnel": tunnel_update})

        self.tunnel_manager.set_status_callback(tunnel_status_callback)

        # Ensure keys exist (generate if needed), but don't connect yet
        success, message = await self.tunnel_manager.ensure_keys_exist()

        if success:
            logger.info(f"SSH tunnel initialized successfully: {message}")
        else:
            logger.warning(f"SSH tunnel keys not ready: {message}")

    async def create_default_config_yaml(self, file_path: str = None):
        """Create default quiz YAML file with example questions.

        Args:
            file_path: Path where the file should be created (optional)
        """
        if file_path is None:
            file_path = self.config_file if hasattr(self, "config_file") else "config.yaml"
        default_questions = {
            "title": "Тестовий Quiz",
            "show_right_answer": True,
            "questions": [
                {"question": "Скільки буде 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
                {
                    "question": "Яка столиця України?",
                    "options": ["Харків", "Львів", "Київ", "Одеса"],
                    "correct_answer": 2,
                },
            ],
        }

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(yaml.dump(default_questions, default_flow_style=False, allow_unicode=True))
        logger.info(f"Created default config file: {file_path}")

    async def load_questions_from_file(self, quiz_file_path: str):
        """Load questions from specific quiz file for quiz execution.

        Loads questions, title, settings, and adds automatic IDs.

        Args:
            quiz_file_path: Path to the quiz YAML file

        Raises:
            Various exceptions if file cannot be read or parsed
        """
        async with aiofiles.open(quiz_file_path, "r", encoding="utf-8") as f:
            content = await f.read()
            data = yaml.safe_load(content)
            self.questions = data["questions"]

            # Store quiz title or use default
            self.quiz_title = data.get("title", "Система Тестування")

            # Store show_right_answer setting (default: True)
            self.show_right_answer = data.get("show_right_answer", True)

            # Store randomize_questions setting (default: False)
            self.randomize_questions = data.get("randomize_questions", False)

            # Store show_answers_on_completion setting (default: False)
            self.show_answers_on_completion = data.get("show_answers_on_completion", False)

            # Add automatic IDs based on array index (for quiz execution only)
            for i, question in enumerate(self.questions):
                question["id"] = i + 1

            logger.info(
                f"Loaded {len(self.questions)} questions from {quiz_file_path}, "
                f"show_right_answer: {self.show_right_answer}, randomize_questions: {self.randomize_questions}, "
                f"show_answers_on_completion: {self.show_answers_on_completion}"
            )

    async def load_questions(self):
        """Load questions based on available quiz files.

        Handles multiple scenarios:
        - No quiz files: creates default.yaml
        - Single quiz file: uses it automatically
        - Multiple files with default.yaml: uses default.yaml
        - Multiple files without default.yaml: requires admin selection
        """
        # Check if quizzes directory exists
        if not os.path.exists(self.quizzes_dir):
            os.makedirs(self.quizzes_dir)
            logger.info(f"Created quizzes directory: {self.quizzes_dir}")

        # Get available quiz files
        available_quizzes = await self.list_available_quizzes()

        if not available_quizzes:
            # No quiz files found, create default
            default_path = os.path.join(self.quizzes_dir, "default.yaml")
            await self.create_default_config_yaml(default_path)
            available_quizzes = ["default.yaml"]
            await self.switch_quiz("default.yaml")
        elif len(available_quizzes) == 1:
            # Only one quiz file - use it as default
            await self.switch_quiz(available_quizzes[0])
            logger.info(f"Using single quiz file as default: {available_quizzes[0]}")
        elif "default.yaml" in available_quizzes or "default.yml" in available_quizzes:
            # Multiple files but default.yaml exists - use it
            default_file = "default.yaml" if "default.yaml" in available_quizzes else "default.yml"
            await self.switch_quiz(default_file)
            logger.info(f"Using explicit default file: {default_file}")
        else:
            # Multiple files but no default.yaml - don't load any quiz
            logger.info(f"Multiple quiz files found but no default.yaml - admin must select quiz first")
            await self.create_admin_selection_page()

    async def create_default_index_html(self):
        """Create default index.html file with embedded questions data.

        Embeds questions (without correct answers), registration fields,
        quiz title, and settings into the HTML template.
        """
        ensure_directory_exists(self.static_dir)
        index_path = f"{self.static_dir}/index.html"

        # Prepare questions data for client (without correct answers)
        questions_for_client = []
        for q in self.questions:
            client_question = {
                "id": q["id"],
                "options": q["options"],
                "is_multiple_choice": isinstance(q["correct_answer"], list),
            }
            # Include question text if present
            if "question" in q and q["question"]:
                client_question["question"] = q["question"]
            # Include optional image attribute if present
            if "image" in q and q["image"]:
                client_question["image"] = q["image"]
            # Include optional file attribute if present (prepend /attach/ if not already there)
            if "file" in q and q["file"]:
                file_path = q["file"]
                if not file_path.startswith("/attach/"):
                    file_path = f"/attach/{file_path}"
                client_question["file"] = file_path
            # Include min_correct for multiple choice questions
            if isinstance(q["correct_answer"], list):
                client_question["min_correct"] = q.get("min_correct", len(q["correct_answer"]))
            questions_for_client.append(client_question)

        # Convert questions to JSON string for embedding
        questions_json = json.dumps(questions_for_client, indent=2)

        template_content = self.templates.get("index.html", "")

        # Generate registration fields HTML as a table (always include username)
        registration_fields_html = '<table class="registration-table">'

        # Get username label from config
        username_label = "Ім'я користувача"
        if hasattr(self.config, "registration") and hasattr(self.config.registration, "username_label"):
            username_label = self.config.registration.username_label

        # Add username field as first row
        registration_fields_html += f"""
            <tr>
                <td class="registration-label">{username_label}:</td>
                <td class="registration-input">
                    <input type="text" id="username">
                </td>
            </tr>"""

        # Add additional registration fields if configured
        if hasattr(self.config, "registration") and self.config.registration.fields:
            for field_label in self.config.registration.fields:
                field_name = field_label.lower().replace(" ", "_")
                registration_fields_html += f"""
            <tr>
                <td class="registration-label">{field_label}:</td>
                <td class="registration-input">
                    <input type="text" class="registration-field" data-field-name="{field_name}">
                </td>
            </tr>"""

        registration_fields_html += "</table>"

        # Inject questions data, title, version, registration fields, username label, and show_right_answer setting into template
        html_content = template_content.replace("{{QUESTIONS_DATA}}", questions_json)
        html_content = html_content.replace("{{QUIZ_TITLE}}", self.quiz_title)
        html_content = html_content.replace("{{REGISTRATION_FIELDS}}", registration_fields_html)
        html_content = html_content.replace("{{USERNAME_LABEL}}", username_label)
        html_content = html_content.replace("{{SHOW_RIGHT_ANSWER}}", "true" if self.show_right_answer else "false")
        html_content = html_content.replace("{{WEBQUIZ_VERSION}}", get_package_version())

        # Write to destination
        async with aiofiles.open(index_path, "w", encoding="utf-8") as f:
            await f.write(html_content)

    async def flush_responses_to_csv(self):
        """Flush in-memory responses to CSV file.

        Writes accumulated responses to CSV, creating file with headers if needed.
        Clears in-memory responses after writing.
        """
        if not self.user_responses:
            return

        # Check if CSV file exists, if not create it with headers
        file_exists = os.path.exists(self.csv_file)

        # Use StringIO buffer to write CSV data
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)

        # Write headers if file doesn't exist
        if not file_exists:
            csv_writer.writerow(
                ["user_id", "question", "selected_answer", "correct_answer", "is_correct", "time_taken_seconds"]
            )

        # Write all responses to buffer
        for response in self.user_responses:
            csv_writer.writerow(
                [
                    response["user_id"],
                    response["question"],
                    response["selected_answer"],
                    response["correct_answer"],
                    response["is_correct"],
                    response["time_taken_seconds"],
                ]
            )

        # Write buffer content to file
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()
        total_responses = len(self.user_responses)
        self.user_responses.clear()

        mode = "w" if not file_exists else "a"
        async with aiofiles.open(self.csv_file, mode, encoding="utf-8") as f:
            await f.write(csv_content)

        action = "Created" if not file_exists else "Updated"
        logger.info(f"{action} CSV file with {total_responses} responses: {self.csv_file}")

    async def flush_users_to_csv(self):
        """Flush user registration data to separate CSV file.

        Writes all user data including statistics to CSV, always overwriting
        the file with current data.
        """
        if not self.users or not self.user_csv_file:
            return

        # Use StringIO buffer to write CSV data
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)

        # Determine headers based on registration fields
        headers = ["user_id", "username"]
        if hasattr(self.config, "registration") and self.config.registration.fields:
            for field_label in self.config.registration.fields:
                field_name = field_label.lower().replace(" ", "_")
                headers.append(field_name)
        headers.extend(["registered_at", "total_questions_asked", "correct_answers", "total_time"])

        # Always write headers (we always overwrite the file)
        csv_writer.writerow(headers)

        # Write all user data to buffer
        for user_id, user_data in self.users.items():
            row = [user_id, user_data["username"]]

            # Add additional registration fields in order
            if hasattr(self.config, "registration") and self.config.registration.fields:
                for field_label in self.config.registration.fields:
                    field_name = field_label.lower().replace(" ", "_")
                    row.append(user_data.get(field_name, ""))

            row.append(user_data.get("registered_at", ""))

            # Calculate and add user statistics
            user_answer_list = self.user_answers.get(user_id, [])
            total_questions_asked = len(user_answer_list)
            correct_answers = sum(answer["is_correct"] for answer in user_answer_list)
            total_time_seconds = sum(answer.get("time_taken", 0) for answer in user_answer_list)
            # Format total_time as MM:SS
            minutes = int(total_time_seconds // 60)
            seconds = int(total_time_seconds % 60)
            total_time_formatted = f"{minutes}:{seconds:02d}"
            row.extend([total_questions_asked, correct_answers, total_time_formatted])

            csv_writer.writerow(row)

        # Write buffer content to file
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()

        # Always overwrite the file (users don't accumulate like responses do)
        async with aiofiles.open(self.user_csv_file, "w", encoding="utf-8") as f:
            await f.write(csv_content)

    async def periodic_flush(self):
        """Periodically flush responses and users to CSV every 5 seconds."""
        while True:
            await asyncio.sleep(5)  # Flush every 30 seconds
            try:
                await self.flush_responses_to_csv()
            except Exception as e:
                logger.exception(f"Error during flush_responses_to_csv: {e}")

            try:
                await self.flush_users_to_csv()
            except Exception as e:
                logger.exception(f"Error during flush_users_to_csv: {e}")

    async def _broadcast_to_websocket_list(
        self, clients_list: List[web.WebSocketResponse], message: dict, client_type: str = "WebSocket"
    ):
        """Generic broadcast function for WebSocket clients.

        Sends message to all connected clients and removes closed connections.

        Args:
            clients_list: List of WebSocket client connections
            message: Dictionary to send as JSON
            client_type: Description of client type for logging

        Returns:
            List of active clients (closed connections removed)
        """
        if not clients_list:
            return []

        # Clean up closed connections and broadcast
        active_clients = []
        for ws in clients_list:
            if not ws.closed:
                try:
                    await ws.send_str(json.dumps(message))
                    active_clients.append(ws)
                except Exception as e:
                    logger.warning(f"Failed to send message to {client_type} client: {e}")

        return active_clients

    async def broadcast_to_websockets(self, message: dict):
        """Broadcast message to all connected WebSocket clients (live stats).

        Args:
            message: Dictionary to send as JSON
        """
        self.websocket_clients = await self._broadcast_to_websocket_list(
            self.websocket_clients, message, "live stats WebSocket"
        )

    async def broadcast_to_admin_websockets(self, message: dict):
        """Broadcast message to all connected admin WebSocket clients.

        Args:
            message: Dictionary to send as JSON
        """
        self.admin_websocket_clients = await self._broadcast_to_websocket_list(
            self.admin_websocket_clients, message, "admin WebSocket"
        )

    def _extract_registration_fields(self, user_data: dict) -> dict:
        """Extract only custom registration fields for display to admin.

        Excludes system fields: user_id, username, approved, registered_at, question_order.
        Returns only the custom fields configured in registration.fields.

        Args:
            user_data: User data dictionary

        Returns:
            Dictionary with only custom registration fields
        """
        fields = {}
        if hasattr(self.config, "registration") and self.config.registration.fields:
            for field_label in self.config.registration.fields:
                field_name = field_label.lower().replace(" ", "_")
                if field_name in user_data:
                    fields[field_name] = user_data[field_name]
        return fields

    def _validate_answer(self, selected_answer, question):
        """Validate answer for both single and multiple choice questions.

        For single answer: checks if selected index matches correct index.
        For multiple answers: validates all selected are correct, no incorrect
        selected, and minimum correct requirement is met.

        Args:
            selected_answer: Integer index or list of integer indices
            question: Question dictionary with options and correct_answer

        Returns:
            True if answer is correct, False otherwise
        """
        correct_answer = question["correct_answer"]

        if isinstance(correct_answer, int):
            # Single answer question
            return selected_answer == correct_answer
        elif isinstance(correct_answer, list):
            # Multiple answer question
            if not isinstance(selected_answer, list):
                return False

            # Convert to sets for comparison
            selected_set = set(selected_answer)
            correct_set = set(correct_answer)

            # Check if any incorrect answers were selected
            if not selected_set.issubset(set(range(len(question["options"])))):
                return False  # Invalid option indices

            # Check if any incorrect answers were selected
            incorrect_selected = selected_set - correct_set
            if incorrect_selected:
                return False  # Any incorrect answer makes it wrong

            # Check minimum correct requirement
            min_correct = question.get("min_correct", len(correct_answer))
            correct_selected = selected_set & correct_set

            return len(correct_selected) >= min_correct
        else:
            return False  # Invalid correct_answer format

    def _format_answer_text(self, answer_indices, options):
        """Format answer text for CSV with | separator for multiple answers.

        Args:
            answer_indices: Integer index or list of integer indices
            options: List of option strings

        Returns:
            Formatted answer string (single option or pipe-separated options)
        """
        if isinstance(answer_indices, int):
            # Validate index bounds
            if 0 <= answer_indices < len(options):
                return options[answer_indices]
            else:
                logger.warning(f"Invalid answer index {answer_indices} for options with length {len(options)}")
                return f"Invalid index: {answer_indices}"
        elif isinstance(answer_indices, list):
            # Sort indices and join corresponding option texts with |
            sorted_indices = sorted(answer_indices)
            valid_options = []
            for idx in sorted_indices:
                if 0 <= idx < len(options):
                    valid_options.append(options[idx])
                else:
                    logger.warning(f"Invalid answer index {idx} in list for options with length {len(options)}")
                    valid_options.append(f"Invalid index: {idx}")
            return "|".join(valid_options)
        else:
            return str(answer_indices)

    def generate_random_question_order(self) -> list:
        """Generate a random question order for a user.

        Returns a list of question IDs in random order.
        Only called if self.randomize_questions is True.

        Returns:
            List of question IDs in shuffled order
        """
        import random

        # Create a list of all question IDs
        question_ids = [q["id"] for q in self.questions]

        # Shuffle the list to create random order
        shuffled_ids = question_ids.copy()
        random.shuffle(shuffled_ids)

        logger.info(f"Generated random question order: {shuffled_ids}")
        return shuffled_ids

    def update_live_stats(self, user_id: str, question_id: int, state: str, time_taken: float = None):
        """Update live stats for a user and question.

        Args:
            user_id: User identifier
            question_id: Question identifier
            state: State string ("think", "ok", "fail")
            time_taken: Optional time taken in seconds
        """
        if user_id not in self.live_stats:
            self.live_stats[user_id] = {}

        # Store both state and time_taken
        self.live_stats[user_id][question_id] = {"state": state, "time_taken": time_taken}

    async def register_user(self, request):
        """Register a new user.

        Creates user account with unique ID, validates username uniqueness,
        handles approval workflow, and generates random question order if enabled.

        Args:
            request: aiohttp request with username and registration fields

        Returns:
            JSON response with user_id and registration status
        """
        data = await request.json()
        username = data["username"].strip()

        if not username:
            return web.json_response({"error": "Ім'я користувача не може бути порожнім"}, status=400)

        # Check if username already exists
        for existing_user in self.users.values():
            if existing_user["username"] == username:
                return web.json_response({"error": "Ім'я користувача вже існує"}, status=400)

        # Generate unique 6-digit user ID
        max_attempts = 100
        for _ in range(max_attempts):
            user_id = str(random.randint(100000, 999999))
            if user_id not in self.users:
                break
        else:
            return web.json_response({"error": "Could not generate unique user ID"}, status=500)

        # Check if approval is required
        requires_approval = hasattr(self.config, "registration") and self.config.registration.approve

        # Build user data with additional registration fields
        user_data = {
            "user_id": user_id,
            "username": username,
            "registered_at": datetime.now().isoformat(),
            "approved": not requires_approval,  # Auto-approve if approval not required
        }

        # Add additional registration fields if configured
        if hasattr(self.config, "registration") and self.config.registration.fields:
            for field_label in self.config.registration.fields:
                # Convert field label to field name (lowercase, sanitized)
                field_name = field_label.lower().replace(" ", "_")
                # Get value from request data
                field_value = data.get(field_name, "").strip()
                if not field_value:
                    return web.json_response({"error": f'Поле "{field_label}" не може бути порожнім'}, status=400)
                user_data[field_name] = field_value

        # Generate random question order if randomization is enabled
        if self.randomize_questions:
            user_data["question_order"] = self.generate_random_question_order()
            logger.info(f"Generated random question order for user {user_id}: {user_data['question_order']}")

        self.users[user_id] = user_data

        # If approval not required, start timing and live stats immediately
        if not requires_approval:
            # Start timing for first question
            self.question_start_times[user_id] = datetime.now()

            # Initialize live stats: set first question to "think"
            if len(self.questions) > 0:
                # Determine first question ID (use question_order if randomization enabled)
                first_question_id = user_data.get("question_order", [1])[0] if self.randomize_questions else 1

                self.update_live_stats(user_id, first_question_id, "think")

                # Broadcast new user registration to live stats
                await self.broadcast_to_websockets(
                    {
                        "type": "user_registered",
                        "user_id": user_id,
                        "username": username,
                        "question_id": first_question_id,
                        "state": "think",
                        "time_taken": None,
                        "total_questions": len(self.questions),
                    }
                )
        else:
            # Broadcast to admin WebSocket for approval
            await self.broadcast_to_admin_websockets(
                {
                    "type": "new_registration",
                    "user_id": user_data["user_id"],
                    "username": user_data["username"],
                    "registration_fields": self._extract_registration_fields(user_data),
                }
            )

        logger.info(f"Registered user: {username} with ID: {user_id}, requires_approval: {requires_approval}")

        # Build response
        response_data = {
            "username": username,
            "user_id": user_id,
            "message": "User registered successfully",
            "requires_approval": requires_approval,
            "approved": user_data["approved"],
        }

        # Include question_order if randomization is enabled
        if self.randomize_questions and "question_order" in user_data:
            response_data["question_order"] = user_data["question_order"]

        return web.json_response(response_data)

    async def update_registration(self, request):
        """Update registration data for a user (only if not approved yet).

        Args:
            request: aiohttp request with user_id and fields to update

        Returns:
            JSON response with success status and updated user data
        """
        data = await request.json()
        user_id = data.get("user_id")

        if not user_id:
            return web.json_response({"error": "User ID is required"}, status=400)

        # Check if user exists
        if user_id not in self.users:
            return web.json_response({"error": "User not found"}, status=404)

        user_data = self.users[user_id]

        # Check if user is already approved
        if user_data.get("approved", False):
            return web.json_response({"error": "Cannot update registration data after approval"}, status=400)

        # Update username if provided
        username = data.get("username", "").strip()
        if username:
            # Check if new username already exists (exclude current user)
            for existing_user_id, existing_user in self.users.items():
                if existing_user_id != user_id and existing_user["username"] == username:
                    return web.json_response({"error": "Ім'я користувача вже існує"}, status=400)
            user_data["username"] = username

        # Update additional registration fields if configured
        if hasattr(self.config, "registration") and self.config.registration.fields:
            for field_label in self.config.registration.fields:
                # Convert field label to field name (lowercase, sanitized)
                field_name = field_label.lower().replace(" ", "_")
                # Get value from request data
                field_value = data.get(field_name, "").strip()
                if field_value:  # Only update if provided
                    user_data[field_name] = field_value

        # Update user data in memory
        self.users[user_id] = user_data

        # Broadcast update to admin WebSocket
        await self.broadcast_to_admin_websockets(
            {
                "type": "registration_updated",
                "user_id": user_id,
                "username": user_data["username"],
                "registration_fields": self._extract_registration_fields(user_data),
            }
        )

        logger.info(f"Updated registration data for user: {user_id}")
        return web.json_response(
            {"success": True, "message": "Registration data updated successfully", "user_data": user_data}
        )

    async def submit_answer(self, request):
        """Submit test answer.

        Validates answer, calculates time taken, stores response, updates progress,
        broadcasts to WebSocket clients, and calculates final stats if test complete.

        Args:
            request: aiohttp request with user_id, question_id, and selected_answer

        Returns:
            JSON response with feedback (conditionally includes correctness)
        """
        data = await request.json()
        user_id = data["user_id"]
        question_id = data["question_id"]
        selected_answer = data["selected_answer"]

        # Find user by user_id
        if user_id not in self.users:
            return web.json_response({"error": "Користувача не знайдено"}, status=404)

        username = self.users[user_id]["username"]
        user_data = self.users[user_id]

        # Validate question order for randomized quizzes (security check)
        if getattr(self, "randomize_questions", False) and "question_order" in user_data:
            question_order = user_data["question_order"]
            last_answered_id = self.user_progress.get(user_id, 0)

            # Determine the expected next question
            if last_answered_id == 0:
                # First question - should be the first in their order
                expected_question_id = question_order[0]
            else:
                # Find the index of last answered question in their order
                try:
                    last_index = question_order.index(last_answered_id)
                    next_index = last_index + 1

                    # Check if user has finished all questions
                    if next_index >= len(question_order):
                        return web.json_response({"error": "Ви вже відповіли на всі питання"}, status=400)

                    expected_question_id = question_order[next_index]
                except ValueError:
                    # Last answered question not in order (shouldn't happen)
                    logger.error(f"User {user_id} last_answered_id {last_answered_id} not found in question_order")
                    return web.json_response({"error": "Помилка валідації порядку питань"}, status=500)

            # Validate submitted question matches expected
            if question_id != expected_question_id:
                logger.warning(
                    f"User {user_id} attempted to answer question {question_id} "
                    f"but expected question {expected_question_id}"
                )
                return web.json_response(
                    {
                        "error": "Ви можете відповідати лише на поточне питання",
                        "expected_question_id": expected_question_id,
                    },
                    status=403,
                )

        # Find the question
        question = next((q for q in self.questions if q["id"] == question_id), None)
        if not question:
            return web.json_response({"error": "Питання не знайдено"}, status=404)

        # Calculate time taken server-side from when question was displayed
        time_taken = 0
        if user_id in self.question_start_times:
            time_taken = (datetime.now() - self.question_start_times[user_id]).total_seconds()
            # Clean up the start time
            del self.question_start_times[user_id]

        # Check if answer is correct (handle both single and multiple answers)
        is_correct = self._validate_answer(selected_answer, question)

        # Store response in memory
        response_data = {
            "user_id": user_id,
            "username": username,
            "question_id": question_id,
            "question": question.get("question", ""),  # Handle image-only questions
            "selected_answer": self._format_answer_text(selected_answer, question["options"]),
            "correct_answer": self._format_answer_text(question["correct_answer"], question["options"]),
            "is_correct": is_correct,
            "time_taken_seconds": time_taken,
            "timestamp": datetime.now().isoformat(),
        }

        self.user_responses.append(response_data)

        # Track answer separately for stats calculation (independent of CSV flushing)
        if user_id not in self.user_answers:
            self.user_answers[user_id] = []

        # Normalize file path for results (prepend /attach/ if needed)
        file_value = question.get("file")
        if file_value and not file_value.startswith("/attach/"):
            file_value = f"/attach/{file_value}"

        answer_data = {
            "question": question.get("question", ""),  # Handle image-only questions
            "image": question.get("image"),
            "file": file_value,
            "selected_answer": self._format_answer_text(selected_answer, question["options"]),
            "correct_answer": self._format_answer_text(question["correct_answer"], question["options"]),
            "is_correct": is_correct,
            "time_taken": time_taken,
        }
        self.user_answers[user_id].append(answer_data)

        # Update user progress
        self.user_progress[user_id] = question_id

        # Update live stats: set current question state based on correctness
        state = "ok" if is_correct else "fail"
        self.update_live_stats(user_id, question_id, state, time_taken)

        # Check if this was the last question and calculate final stats
        # Use the number of answers instead of question_id to support randomization
        test_completed = len(self.user_answers.get(user_id, [])) == len(self.questions)
        completion_time = None
        if test_completed:
            # Test completed - calculate and store final stats
            self.calculate_and_store_user_stats(user_id)
            # Get completion time from stored stats
            completion_time = self.user_stats.get(user_id, {}).get("completed_at")
            logger.info(f"Test completed for user {user_id} - final stats calculated")

        # Broadcast current question result with completion status
        await self.broadcast_to_websockets(
            {
                "type": "state_update",
                "user_id": user_id,
                "username": username,
                "question_id": question_id,
                "state": state,
                "time_taken": time_taken,
                "total_questions": len(self.questions),
                "completed": test_completed,
                "completed_at": completion_time,
            }
        )

        logger.info(
            f"Answer submitted by {username} (ID: {user_id}) for question {question_id}: {'Correct' if is_correct else 'Incorrect'} (took {time_taken}s)"
        )
        logger.info(f"Updated progress for user {user_id}: last answered question = {question_id}")

        # Prepare response data
        response_data = {"time_taken": time_taken, "message": "Answer submitted successfully"}

        # Only include correctness feedback and correct answer if show_right_answer is enabled
        if self.show_right_answer:
            response_data["is_correct"] = is_correct
            response_data["correct_answer"] = question["correct_answer"]
            response_data["is_multiple_choice"] = isinstance(question["correct_answer"], list)

        return web.json_response(response_data)

    async def question_start(self, request):
        """Handle notification that a user started viewing a question.

        Starts timing for the question and updates live stats to "think" state.

        Args:
            request: aiohttp request with user_id and question_id

        Returns:
            JSON response with success status
        """
        data = await request.json()
        user_id = data["user_id"]
        question_id = data["question_id"]
        username = self.users[user_id]["username"]

        # Verify user exists
        if user_id not in self.users:
            return web.json_response({"error": "Користувача не знайдено"}, status=404)

        if user_id not in self.question_start_times:
            self.question_start_times[user_id] = datetime.now()
        self.update_live_stats(user_id, question_id, "think")

        await self.broadcast_to_websockets(
            {
                "type": "state_update",
                "user_id": user_id,
                "username": username,
                "question_id": question_id,
                "state": "think",
                "time_taken": None,
                "total_questions": len(self.questions),
            }
        )

        return web.json_response({"status": "success"})

    def calculate_and_store_user_stats(self, user_id):
        """Calculate and store final stats for a completed user.

        Uses user_answers tracking (independent of CSV flushing) to calculate
        correct count, percentage, and total time.

        Args:
            user_id: User identifier
        """
        # Get answers from dedicated user_answers tracking (independent of CSV flushing)
        if user_id not in self.user_answers or not self.user_answers[user_id]:
            logger.warning(f"No answers found for user {user_id} during stats calculation")
            return

        user_answer_list = self.user_answers[user_id]

        # Calculate stats from user_answers
        correct_count = 0
        total_time = 0

        for answer in user_answer_list:
            if answer["is_correct"]:
                correct_count += 1
            total_time += answer["time_taken"]

        total_count = len(user_answer_list)
        percentage = round((correct_count / total_count) * 100) if total_count > 0 else 0

        # Store final stats (copy the answer data to avoid reference issues)
        self.user_stats[user_id] = {
            "test_results": [answer.copy() for answer in user_answer_list],
            "correct_count": correct_count,
            "total_count": total_count,
            "percentage": percentage,
            "total_time": total_time,
            "completed_at": datetime.now().isoformat(),
        }

        logger.info(
            f"Stored final stats for user {user_id}: {correct_count}/{total_count} ({percentage}%) using user_answers"
        )

    def all_students_completed(self):
        """Check if all students have completed the quiz.

        Counts only approved students when approval is required.
        Dynamically evaluates based on current state.

        Returns:
            bool: True if all students have completed, False otherwise
        """
        # Get count of approved students (or all students if approval not required)
        requires_approval = hasattr(self.config, "registration") and self.config.registration.approve

        if requires_approval:
            # Count only approved students
            approved_count = sum(1 for user_data in self.users.values() if user_data.get("approved", False))
            total_students = approved_count
        else:
            # Count all registered students
            total_students = len(self.users)

        # Count completed students
        completed_count = len(self.user_stats)

        # Return True if all students have completed
        # Handle edge case: if no students registered, return False
        if total_students == 0:
            return False

        return completed_count >= total_students

    def get_user_final_results(self, user_id):
        """Get final results for a completed user from persistent user_stats.

        Filters out correct answer information based on configuration:
        - If show_right_answer is True: always show correct answers
        - If show_answers_on_completion is True and all students completed: show correct answers
        - Otherwise: hide correct answers

        Args:
            user_id: User identifier

        Returns:
            Dictionary with test_results, correct_count, total_count, percentage, total_time,
            all_completed, and show_answers_on_completion flags
        """
        if user_id in self.user_stats:
            # Return stored stats (without the completed_at timestamp for the frontend)
            stats = self.user_stats[user_id].copy()
            stats.pop("completed_at", None)  # Remove timestamp from response

            # Check if all students have completed
            all_completed = self.all_students_completed()

            # Add flags for frontend
            stats["all_completed"] = all_completed
            stats["show_answers_on_completion"] = self.show_answers_on_completion

            # Determine if correct answers should be shown
            # Priority: show_right_answer > show_answers_on_completion
            should_show_answers = self.show_right_answer or (self.show_answers_on_completion and all_completed)

            # If answers should not be shown, remove correct answer information from test results
            if not should_show_answers:
                # Create a copy of test_results without correct_answer and is_correct fields
                modified_results = []
                for result in stats.get("test_results", []):
                    result_copy = result.copy()
                    result_copy.pop("correct_answer", None)  # Remove correct_answer field
                    result_copy.pop("is_correct", None)  # Remove is_correct field
                    modified_results.append(result_copy)
                stats["test_results"] = modified_results

            return stats

        # Fallback - should not happen if calculate_and_store_user_stats was called
        return {
            "test_results": [],
            "correct_count": 0,
            "total_count": 0,
            "percentage": 0,
            "total_time": 0,
            "all_completed": False,
            "show_answers_on_completion": False,
        }

    async def verify_user_id(self, request):
        """Verify if user_id exists and return user data.

        Returns user approval status, test progress, and final results if completed.

        Args:
            request: aiohttp request with user_id in path

        Returns:
            JSON response with user validation data and test state
        """
        user_id = request.match_info["user_id"]

        # Find user by user_id
        if user_id not in self.users:
            return web.json_response({"valid": False, "message": "User ID not found"})

        user_data = self.users[user_id]
        username = user_data["username"]
        approved = user_data.get("approved", True)  # Default to True for backwards compatibility

        # Check if approval is required and user is not yet approved
        requires_approval = hasattr(self.config, "registration") and self.config.registration.approve
        if requires_approval and not approved:
            # User waiting for approval
            response_data = {
                "valid": True,
                "user_id": user_id,
                "username": username,
                "approved": False,
                "requires_approval": True,
                "user_data": user_data,
                "message": "User waiting for approval",
            }

            # Include question_order if randomization is enabled
            if self.randomize_questions and "question_order" in user_data:
                response_data["question_order"] = user_data["question_order"]

            return web.json_response(response_data)

        # User is approved (or approval not required), return test state
        # Get last answered question ID from progress tracking
        last_answered_question_id = self.user_progress.get(user_id, 0)

        # Find the index of next question to answer
        next_question_index = 0
        if last_answered_question_id > 0:
            if self.randomize_questions and "question_order" in user_data:
                # With randomization: find index in user's custom order
                try:
                    last_index = user_data["question_order"].index(last_answered_question_id)
                    next_question_index = last_index + 1
                except ValueError:
                    # Question ID not found in order (shouldn't happen), default to 0
                    next_question_index = 0
            else:
                # Without randomization: find index in original question order
                for i, question in enumerate(self.questions):
                    if question["id"] == last_answered_question_id:
                        next_question_index = i + 1
                        break

        # Ensure we don't go beyond available questions
        if next_question_index >= len(self.questions):
            next_question_index = len(self.questions)

        # Check if test is completed
        test_completed = next_question_index >= len(self.questions)

        response_data = {
            "valid": True,
            "user_id": user_id,
            "username": username,
            "approved": approved,
            "next_question_index": next_question_index,
            "total_questions": len(self.questions),
            "last_answered_question_id": last_answered_question_id,
            "test_completed": test_completed,
        }

        # Include question_order if randomization is enabled
        if self.randomize_questions and "question_order" in user_data:
            response_data["question_order"] = user_data["question_order"]

        if test_completed:
            # Get final results for completed test
            final_results = self.get_user_final_results(user_id)
            response_data["final_results"] = final_results
            logger.info(f"User {user_id} verification: test completed, returning final results")
        else:
            logger.info(
                f"User {user_id} verification: last_answered={last_answered_question_id}, next_index={next_question_index}"
            )

        return web.json_response(response_data)

    # Admin API endpoints
    @admin_auth_required
    async def admin_list_quizzes(self, request):
        """List available quiz files.

        Returns:
            JSON response with list of quiz files and current quiz
        """
        quizzes = await self.list_available_quizzes()
        return web.json_response(
            {
                "quizzes": quizzes,
                "current_quiz": os.path.basename(self.current_quiz_file) if self.current_quiz_file else None,
            }
        )

    @admin_auth_required
    async def admin_switch_quiz(self, request):
        """Switch to a different quiz.

        Args:
            request: aiohttp request with quiz_filename

        Returns:
            JSON response with success status and new quiz info
        """
        data = await request.json()
        quiz_filename = data["quiz_filename"]

        await self.switch_quiz(quiz_filename)

        return web.json_response(
            {
                "success": True,
                "message": f"Switched to quiz: {quiz_filename}",
                "current_quiz": quiz_filename,
                "csv_file": os.path.basename(self.csv_file),
            }
        )

    @local_network_only
    async def admin_auth(self, request):
        """Authenticate admin with master key and create session.

        Validates master key from request body,
        creates a new session token, and sets it as a cookie.
        Trusted IPs bypass master key validation.

        Returns:
            JSON response confirming authentication succeeded with session cookie
        """
        # Check if it's in trusted list (bypass master key validation)
        client_ip = get_client_ip(request)
        is_trusted = hasattr(self, "admin_config") and client_ip in self.admin_config.trusted_ips

        if not is_trusted:
            # Check if master key is configured
            if not self.master_key:
                return web.json_response({"error": "Admin functionality disabled - no master key set"}, status=403)

            # Get master key from request body only
            provided_key = None
            try:
                data = await request.json()
                provided_key = data.get("master_key")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as e:
                logger.exception(f"Unexpected error reading admin auth request body: {e}")

            if not provided_key or provided_key != self.master_key:
                return web.json_response({"error": "Недійсний або відсутній головний ключ"}, status=401)

        # Generate a new session token
        session_token = secrets.token_urlsafe(32)
        self.admin_sessions[session_token] = datetime.now()

        # Create response with session cookie
        response = web.json_response({"authenticated": True, "message": "Admin authentication successful"})
        response.set_cookie(
            "admin_session",
            session_token,
            httponly=True,
            samesite="Strict",
            path="/",
        )
        return response

    @local_network_only
    async def admin_check_session(self, request):
        """Check if admin session cookie is valid.

        Used for auto-authentication on page load without requiring master key.

        Returns:
            JSON response with session validity status
        """
        session_token = request.cookies.get("admin_session")

        if not session_token:
            return web.json_response({"valid": False, "reason": "No session cookie"}, status=401)

        if session_token not in self.admin_sessions:
            return web.json_response({"valid": False, "reason": "Invalid session"}, status=401)

        return web.json_response({"valid": True, "message": "Session is valid"})

    @local_network_only
    async def admin_version_check(self, request):
        """Check if a newer package version is available on disk.

        Compares the in-memory package version with the version from the
        __init__.py file to detect if the package was updated while running.

        Returns:
            JSON response with version info and restart_required flag
        """
        running_version = get_package_version()
        file_version = get_file_version()

        restart_required = (
            running_version != "unknown" and file_version != "unknown" and running_version != file_version
        )

        return web.json_response(
            {"running_version": running_version, "file_version": file_version, "restart_required": restart_required}
        )

    @admin_auth_required
    async def admin_approve_user(self, request):
        """Approve a user for testing.

        Marks user as approved, starts timing, initializes live stats,
        and generates random question order if enabled.

        Args:
            request: aiohttp request with user_id

        Returns:
            JSON response with approval confirmation
        """
        data = await request.json()
        user_id = data.get("user_id")

        if not user_id:
            return web.json_response({"error": "User ID is required"}, status=400)

        # Check if user exists
        if user_id not in self.users:
            return web.json_response({"error": "User not found"}, status=404)

        user_data = self.users[user_id]

        # Check if already approved
        if user_data.get("approved", False):
            return web.json_response({"success": True, "message": "User already approved"})

        # Approve the user
        user_data["approved"] = True

        # Generate random question order if randomization is enabled and not yet generated
        if self.randomize_questions and "question_order" not in user_data:
            user_data["question_order"] = self.generate_random_question_order()
            logger.info(f"Generated random question order for approved user {user_id}: {user_data['question_order']}")

        self.users[user_id] = user_data

        # Start timing for first question
        self.question_start_times[user_id] = datetime.now()

        # Initialize live stats: set first question to "think"
        if len(self.questions) > 0:
            # Determine first question ID (use question_order if randomization enabled)
            first_question_id = user_data.get("question_order", [1])[0] if self.randomize_questions else 1

            self.update_live_stats(user_id, first_question_id, "think")

            # Broadcast user approval to live stats WebSocket
            await self.broadcast_to_websockets(
                {
                    "type": "user_registered",
                    "user_id": user_id,
                    "username": user_data["username"],
                    "question_id": first_question_id,
                    "state": "think",
                    "time_taken": None,
                    "total_questions": len(self.questions),
                }
            )

        # Broadcast approval to admin WebSocket
        await self.broadcast_to_admin_websockets({"type": "user_approved", "user_id": user_id})

        logger.info(f"Approved user: {user_id}")
        return web.json_response({"success": True, "message": "User approved successfully", "user_id": user_id})

    @admin_auth_required
    async def admin_get_quiz(self, request):
        """Get quiz content for editing.

        Args:
            request: aiohttp request with filename in path

        Returns:
            JSON response with quiz content (raw YAML and parsed)
        """
        filename = request.match_info["filename"]
        quiz_path = os.path.join(self.quizzes_dir, filename)

        if not os.path.exists(quiz_path):
            return web.json_response({"error": "Quiz file not found"}, status=404)

        with open(quiz_path, "r", encoding="utf-8") as f:
            quiz_content = f.read()

        # Also return parsed YAML for wizard mode
        try:
            import yaml

            parsed_quiz = yaml.safe_load(quiz_content)
            return web.json_response({"filename": filename, "content": quiz_content, "parsed": parsed_quiz})
        except yaml.YAMLError as e:
            return web.json_response(
                {"filename": filename, "content": quiz_content, "parsed": None, "yaml_error": str(e)}
            )

    @admin_auth_required
    async def admin_create_quiz(self, request):
        """Create new quiz from wizard or text input.

        Args:
            request: aiohttp request with filename, mode, and quiz data/content

        Returns:
            JSON response with success status
        """
        data = await request.json()
        filename = data.get("filename", "").strip()
        mode = data.get("mode", "wizard")  # 'wizard' or 'text'

        if not filename:
            return web.json_response({"error": "Filename is required"}, status=400)

        if not filename.endswith(".yaml"):
            filename += ".yaml"

        quiz_path = os.path.join(self.quizzes_dir, filename)

        # Check if file already exists
        if os.path.exists(quiz_path):
            return web.json_response({"error": "Quiz file already exists"}, status=409)

        # Validate and create quiz content
        if mode == "wizard":
            quiz_data = data.get("quiz_data", {})
            if not self._validate_quiz_data(quiz_data):
                return web.json_response({"error": "Неправильна структура даних квізу"}, status=400)

            import yaml

            quiz_content = yaml.dump(quiz_data, default_flow_style=False, allow_unicode=True)
        else:  # text mode
            quiz_content = data.get("content", "").strip()
            if not quiz_content:
                return web.json_response({"error": "Quiz content is required"}, status=400)

            # Validate YAML
            try:
                import yaml

                parsed = yaml.safe_load(quiz_content)
                if not self._validate_quiz_data(parsed):
                    return web.json_response({"error": "Неправильна структура даних квізу"}, status=400)
            except yaml.YAMLError as e:
                return web.json_response({"error": f"Неправильний YAML: {str(e)}"}, status=400)

        # Write the quiz file
        with open(quiz_path, "w", encoding="utf-8") as f:
            f.write(quiz_content)

        logger.info(f"Created new quiz: {filename}")
        return web.json_response(
            {"success": True, "message": f'Quiz "{filename}" created successfully', "filename": filename}
        )

    @admin_auth_required
    async def admin_update_quiz(self, request):
        """Update existing quiz.

        Creates backup before updating. Reloads quiz if it's currently active.

        Args:
            request: aiohttp request with filename in path and quiz data

        Returns:
            JSON response with success status and backup filename
        """
        filename = request.match_info["filename"]
        data = await request.json()
        mode = data.get("mode", "wizard")

        quiz_path = os.path.join(self.quizzes_dir, filename)

        if not os.path.exists(quiz_path):
            return web.json_response({"error": "Quiz file not found"}, status=404)

        # Create backup
        backup_path = quiz_path + ".backup"

        shutil.copy2(quiz_path, backup_path)

        # Prepare new content
        if mode == "wizard":
            quiz_data = data.get("quiz_data", {})
            if not self._validate_quiz_data(quiz_data):
                return web.json_response({"error": "Неправильна структура даних квізу"}, status=400)

            quiz_content = yaml.dump(quiz_data, default_flow_style=False, allow_unicode=True)
        else:  # text mode
            quiz_content = data.get("content", "").strip()
            if not quiz_content:
                return web.json_response({"error": "Quiz content is required"}, status=400)

            # Validate YAML
            try:
                parsed = yaml.safe_load(quiz_content)
                if not self._validate_quiz_data(parsed):
                    return web.json_response({"error": "Неправильна структура даних квізу"}, status=400)
            except yaml.YAMLError as e:
                return web.json_response({"error": f"Неправильний YAML: {str(e)}"}, status=400)

        # Write updated content
        with open(quiz_path, "w", encoding="utf-8") as f:
            f.write(quiz_content)

        # If this is the current quiz, reload it
        if self.current_quiz_file and os.path.basename(self.current_quiz_file) == filename:
            await self.switch_quiz(filename)

        logger.info(f"Updated quiz: {filename}")
        return web.json_response(
            {
                "success": True,
                "message": f'Quiz "{filename}" updated successfully',
                "backup_created": os.path.basename(backup_path),
            }
        )

    @admin_auth_required
    async def admin_delete_quiz(self, request):
        """Delete quiz file.

        Creates backup before deletion. Prevents deleting currently active quiz.

        Args:
            request: aiohttp request with filename in path

        Returns:
            JSON response with success status and backup filename
        """
        filename = request.match_info["filename"]
        quiz_path = os.path.join(self.quizzes_dir, filename)

        if not os.path.exists(quiz_path):
            return web.json_response({"error": "Quiz file not found"}, status=404)

        # Don't allow deleting the current quiz
        if self.current_quiz_file and os.path.basename(self.current_quiz_file) == filename:
            return web.json_response({"error": "Cannot delete the currently active quiz"}, status=400)

        # Create backup before deletion
        backup_path = quiz_path + ".deleted_backup"
        import shutil

        shutil.copy2(quiz_path, backup_path)

        # Delete the file
        os.remove(quiz_path)

        logger.info(f"Deleted quiz: {filename} (backup: {backup_path})")
        return web.json_response(
            {
                "success": True,
                "message": f'Quiz "{filename}" deleted successfully',
                "backup_created": os.path.basename(backup_path),
            }
        )

    @admin_auth_required
    async def admin_validate_quiz(self, request):
        """Validate quiz YAML structure.

        Args:
            request: aiohttp request with quiz content

        Returns:
            JSON response with validation result and errors if any
        """
        data = await request.json()
        content = data.get("content", "").strip()

        if not content:
            return web.json_response({"valid": False, "errors": ["Content is empty"]})

        try:
            import yaml

            parsed = yaml.safe_load(content)

            # Validate structure
            errors = []
            if not self._validate_quiz_data(parsed, errors):
                return web.json_response({"valid": False, "errors": errors})

            return web.json_response(
                {"valid": True, "parsed": parsed, "question_count": len(parsed.get("questions", []))}
            )
        except yaml.YAMLError as e:
            return web.json_response({"valid": False, "errors": [f"YAML syntax error: {str(e)}"]})

    def _validate_quiz_data(self, data, errors=None):
        """Validate quiz data structure.

        Checks for required fields, valid data types, correct answer indices,
        and optional settings like min_correct, show_right_answer, etc.

        Args:
            data: Quiz data dictionary to validate
            errors: Optional list to append error messages to

        Returns:
            True if valid, False otherwise (errors list contains details)
        """
        if errors is None:
            errors = []

        if not isinstance(data, dict):
            errors.append("Дані квізу повинні бути словником")
            return False

        if "questions" not in data:
            errors.append("Квіз повинен містити поле 'questions'")
            return False

        questions = data["questions"]
        if not isinstance(questions, list):
            errors.append("'questions' повинно бути списком")
            return False

        if len(questions) == 0:
            errors.append("Квіз повинен містити принаймні одне питання")
            return False

        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                errors.append(f"Question {i+1} must be a dictionary")
                continue

            # Validate required fields (except 'question' which is optional if image provided)
            required_fields = ["options", "correct_answer"]
            for field in required_fields:
                if field not in question:
                    errors.append(f"Question {i+1} missing required field: {field}")

            # Either question text OR image must be provided
            has_question = "question" in question and question["question"]
            has_image = "image" in question and question["image"]
            if not has_question and not has_image:
                errors.append(f"Question {i+1} must have either question text or image")

            # Validate options
            if "options" in question:
                options = question["options"]
                if not isinstance(options, list):
                    errors.append(f"Question {i+1} options must be a list")
                elif len(options) < 2:
                    errors.append(f"Question {i+1} must have at least 2 options")
                elif not all(isinstance(opt, str) for opt in options):
                    errors.append(f"Question {i+1} all options must be strings")

            # Validate correct_answer (can be integer for single answer or list for multiple answers)
            if "correct_answer" in question and "options" in question:
                correct_answer = question["correct_answer"]
                options_count = len(question["options"])

                if isinstance(correct_answer, int):
                    # Single answer validation
                    if correct_answer < 0 or correct_answer >= options_count:
                        errors.append(f"Question {i+1} correct_answer index out of range")
                elif isinstance(correct_answer, list):
                    # Multiple answers validation
                    if len(correct_answer) == 0:
                        errors.append(f"Question {i+1} correct_answer array cannot be empty")
                    elif not all(isinstance(idx, int) for idx in correct_answer):
                        errors.append(f"Question {i+1} correct_answer array must contain only integers")
                    elif any(idx < 0 or idx >= options_count for idx in correct_answer):
                        errors.append(f"Question {i+1} correct_answer array contains index out of range")
                    elif len(set(correct_answer)) != len(correct_answer):
                        errors.append(f"Question {i+1} correct_answer array contains duplicate indices")
                else:
                    errors.append(f"Question {i+1} correct_answer must be an integer or array of integers")

            # Validate min_correct (only valid for multiple answers)
            if "min_correct" in question:
                min_correct = question["min_correct"]
                if "correct_answer" not in question:
                    errors.append(f"Question {i+1} has min_correct but no correct_answer")
                elif not isinstance(question["correct_answer"], list):
                    errors.append(f"Question {i+1} min_correct is only valid for multiple answer questions")
                elif not isinstance(min_correct, int):
                    errors.append(f"Question {i+1} min_correct must be an integer")
                elif min_correct < 1:
                    errors.append(f"Question {i+1} min_correct must be at least 1")
                elif min_correct > len(question["correct_answer"]):
                    errors.append(f"Question {i+1} min_correct cannot exceed number of correct answers")

        # Validate optional top-level fields
        if "show_right_answer" in data and not isinstance(data["show_right_answer"], bool):
            errors.append("'show_right_answer' must be a boolean (true or false)")

        if "randomize_questions" in data and not isinstance(data["randomize_questions"], bool):
            errors.append("'randomize_questions' must be a boolean (true or false)")

        if "title" in data and not isinstance(data["title"], str):
            errors.append("'title' must be a string")

        return len(errors) == 0

    def _validate_config_data(self, data, errors=None):
        """Validate server configuration data structure.

        All sections are optional - empty config is valid.
        Validates structure and types for server, paths, admin, registration, and quizzes sections.

        Args:
            data: Config data dictionary to validate
            errors: Optional list to append error messages to

        Returns:
            True if valid, False otherwise (errors list contains details)
        """
        if errors is None:
            errors = []

        # Config can be None or empty dict - both are valid
        if data is None:
            return True

        if not isinstance(data, dict):
            errors.append("Config must be a dictionary")
            return False

        # Validate server section (optional)
        if "server" in data:
            server = data["server"]
            if not isinstance(server, dict):
                errors.append("'server' section must be a dictionary")
            else:
                if "host" in server and not isinstance(server["host"], str):
                    errors.append("'server.host' must be a string")
                if "port" in server:
                    if not isinstance(server["port"], int):
                        errors.append("'server.port' must be an integer")
                    elif server["port"] < 1 or server["port"] > 65535:
                        errors.append("'server.port' must be between 1 and 65535")

        # Validate paths section (optional)
        if "paths" in data:
            paths = data["paths"]
            if not isinstance(paths, dict):
                errors.append("'paths' section must be a dictionary")
            else:
                path_fields = ["quizzes_dir", "logs_dir", "csv_dir", "static_dir"]
                for field in path_fields:
                    if field in paths and not isinstance(paths[field], str):
                        errors.append(f"'paths.{field}' must be a string")

        # Validate admin section (optional)
        if "admin" in data:
            admin = data["admin"]
            if not isinstance(admin, dict):
                errors.append("'admin' section must be a dictionary")
            else:
                if "master_key" in admin:
                    if admin["master_key"] is not None and not isinstance(admin["master_key"], str):
                        errors.append("'admin.master_key' must be a string or null")
                if "trusted_ips" in admin:
                    if not isinstance(admin["trusted_ips"], list):
                        errors.append("'admin.trusted_ips' must be a list")
                    elif not all(isinstance(ip, str) for ip in admin["trusted_ips"]):
                        errors.append("'admin.trusted_ips' must contain only strings")

        # Validate registration section (optional)
        if "registration" in data:
            registration = data["registration"]
            if not isinstance(registration, dict):
                errors.append("'registration' section must be a dictionary")
            else:
                if "fields" in registration:
                    if not isinstance(registration["fields"], list):
                        errors.append("'registration.fields' must be a list")
                    elif not all(isinstance(field, str) for field in registration["fields"]):
                        errors.append("'registration.fields' must contain only strings")
                if "approve" in registration:
                    if not isinstance(registration["approve"], bool):
                        errors.append("'registration.approve' must be a boolean")
                if "username_label" in registration:
                    if not isinstance(registration["username_label"], str):
                        errors.append("'registration.username_label' must be a string")

        # Validate quizzes section (optional)
        if "quizzes" in data:
            quizzes = data["quizzes"]
            if not isinstance(quizzes, list):
                errors.append("'quizzes' section must be a list")
            else:
                for i, quiz in enumerate(quizzes):
                    if not isinstance(quiz, dict):
                        errors.append(f"Quiz {i+1} must be a dictionary")
                        continue

                    # Check required fields for each quiz
                    required_quiz_fields = ["name", "download_path", "folder"]
                    for field in required_quiz_fields:
                        if field not in quiz:
                            errors.append(f"Quiz {i+1} missing required field: '{field}'")
                        elif not isinstance(quiz[field], str):
                            errors.append(f"Quiz {i+1} field '{field}' must be a string")

        return len(errors) == 0

    @admin_auth_required
    async def admin_list_images(self, request):
        """List all images in quizzes/imgs directory.

        Returns:
            JSON response with list of image files and their paths
        """
        imgs_dir = os.path.join(self.quizzes_dir, "imgs")
        if not os.path.exists(imgs_dir):
            return web.json_response({"images": []})

        image_files = []
        for filename in os.listdir(imgs_dir):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg")):
                image_files.append(
                    {
                        "filename": filename,
                        "path": f"/imgs/{filename}",
                    }
                )

        # Sort alphabetically by filename (case-insensitive)
        image_files.sort(key=lambda x: x["filename"].lower())

        return web.json_response({"images": image_files})

    @admin_auth_required
    async def admin_list_files(self, request):
        """List all files in quizzes/attach directory.

        Returns:
            JSON response with list of files (filename, path, size)
        """
        files_dir = os.path.join(self.quizzes_dir, "attach")
        if not os.path.exists(files_dir):
            return web.json_response({"files": []})

        file_list = []
        for filename in os.listdir(files_dir):
            file_path = os.path.join(files_dir, filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_list.append(
                    {
                        "filename": filename,
                        "path": f"/attach/{filename}",
                        "size": file_size,
                    }
                )

        # Sort alphabetically by filename (case-insensitive)
        file_list.sort(key=lambda x: x["filename"].lower())

        return web.json_response({"files": file_list})

    async def serve_quiz_file(self, request):
        """Serve quiz file for download.

        Serves files from quizzes/attach directory with Content-Disposition: attachment
        to force browser download.

        Args:
            request: aiohttp request with filename in path

        Returns:
            File response with attachment disposition header
        """
        filename = request.match_info["filename"]

        # Validate filename (prevent path traversal)
        if not self._is_safe_filename(filename):
            return web.json_response({"error": "Invalid filename"}, status=400)

        files_dir = os.path.join(self.quizzes_dir, "attach")
        file_path = os.path.join(files_dir, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            return web.json_response({"error": "File not found"}, status=404)

        # Check if it's actually a file (not directory)
        if not os.path.isfile(file_path):
            return web.json_response({"error": "Not a file"}, status=400)

        # Return file response with attachment disposition to force download
        return web.FileResponse(
            file_path,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @admin_auth_required
    async def admin_download_quiz(self, request):
        """Download and extract quiz from ZIP file.

        Downloads ZIP from HTTPS URL, extracts specified folder to quizzes directory.

        Args:
            request: aiohttp request with name, download_path, and folder

        Returns:
            JSON response with extraction results and updated quiz list
        """
        data = await request.json()
        name = data.get("name")
        download_path = data.get("download_path")
        folder = data.get("folder")

        if not name or not download_path:
            return web.json_response({"error": "Name and download_path are required"}, status=400)

        # Check for absolute paths (Unix-style or Windows-style)
        if os.path.isabs(folder) or (len(folder) >= 2 and folder[1] == ":"):
            return web.json_response({"error": "Invalid folder path: absolute paths not allowed"}, status=400)

        # Check for path traversal attempts before normalization
        if ".." in folder:
            return web.json_response({"error": "Invalid folder path: parent directory access not allowed"}, status=400)

        # Normalize the path to handle different separators
        normalized_folder = os.path.normpath(folder)

        # Double-check after normalization
        if ".." in normalized_folder:
            return web.json_response({"error": "Invalid folder path: parent directory access not allowed"}, status=400)

        # Ensure the normalized path doesn't escape the quizzes directory
        test_path = os.path.normpath(os.path.join(self.quizzes_dir, normalized_folder))
        quizzes_dir_normalized = os.path.normpath(self.quizzes_dir) + os.sep
        test_path_normalized = test_path + os.sep

        if not test_path_normalized.startswith(quizzes_dir_normalized):
            return web.json_response({"error": "Invalid folder path: path traversal detected"}, status=400)

        folder = normalized_folder

        # Download and extract the ZIP file using temporary directory
        try:
            # Download the ZIP file
            logger.info(f"Downloading quiz from {download_path}")
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(download_path)
                response.raise_for_status()

                # Use temporary directory for extraction (auto-cleanup)
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Save ZIP file
                    zip_path = os.path.join(temp_dir, f"{name.replace(' ', '_')}.zip")
                    async with aiofiles.open(zip_path, "wb") as zip_file:
                        await zip_file.write(response.content)

                    # Extract ZIP
                    logger.info(f"Extracting ZIP to {temp_dir}")
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        file_list = zip_ref.namelist()
                        logger.info(f"ZIP contains {len(file_list)} files")
                        zip_ref.extractall(temp_dir)

                    source_path = os.path.join(temp_dir, folder)

                    # Verify source path exists
                    if not os.path.exists(source_path):
                        raise ValueError(
                            f"Folder '{folder}' not found in ZIP archive. Available paths: {os.listdir(temp_dir)}"
                        )

                    # Move everything from source to quizzes directory
                    logger.info(f"Moving contents from {source_path} to {self.quizzes_dir}")
                    shutil.copytree(source_path, self.quizzes_dir, dirs_exist_ok=True)

                    # Update the quiz list
                    await self.list_available_quizzes()

                    return web.json_response({"success": True, "message": f"Quiz '{name}' downloaded successfully"})

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading quiz: {e.response.status_code} - {e}")
            return web.json_response({"error": f"Failed to download quiz: HTTP {e.response.status_code}"}, status=500)

        except httpx.RequestError as e:
            logger.error(f"Network error downloading quiz: {e}")
            return web.json_response({"error": f"Network error: {str(e)}"}, status=500)

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {e}")
            return web.json_response({"error": "Downloaded file is not a valid ZIP archive"}, status=500)

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return web.json_response({"error": str(e)}, status=400)

    @admin_auth_required
    async def admin_update_config(self, request):
        """Update server configuration file.

        Validates YAML syntax and structure before writing to file.

        Args:
            request: aiohttp request with config content

        Returns:
            JSON response with success status (requires server restart)
        """
        data = await request.json()
        content = data.get("content", "").strip()

        # Get config file path (use the actual path that was loaded)
        config_path = self.config.config_path
        if not config_path:
            return web.json_response(
                {"error": "No config file was specified. Server started without --config parameter."}, status=400
            )

        # Validate YAML syntax
        try:
            parsed_config = yaml.safe_load(content) if content else {}
        except yaml.YAMLError as e:
            return web.json_response({"error": f"Invalid YAML syntax: {str(e)}"}, status=400)

        # Validate config structure
        errors = []
        if not self._validate_config_data(parsed_config, errors):
            return web.json_response({"error": "Configuration validation failed", "errors": errors}, status=400)

        # Write to config file
        async with aiofiles.open(config_path, "w", encoding="utf-8") as f:
            await f.write(content if content else "")

        logger.info(f"Configuration file updated: {config_path}")
        return web.json_response(
            {
                "success": True,
                "message": "Configuration saved successfully. Restart server to apply changes.",
                "config_path": config_path,
            }
        )

    @admin_auth_required
    async def tunnel_connect(self, request):
        """Connect SSH tunnel.

        Args:
            request: aiohttp request

        Returns:
            JSON response with success status and URL or error
        """
        if not self.tunnel_manager:
            return web.json_response({"error": "Tunnel not configured"}, status=400)

        success, result = await self.tunnel_manager.connect()

        if success:
            logger.info(f"Tunnel connected: {result}")
            return web.json_response({"success": True, "url": result})
        else:
            logger.error(f"Tunnel connection failed: {result}")
            return web.json_response({"error": result}, status=500)

    @admin_auth_required
    async def tunnel_disconnect(self, request):
        """Disconnect SSH tunnel.

        Args:
            request: aiohttp request

        Returns:
            JSON response with success status
        """
        if not self.tunnel_manager:
            return web.json_response({"error": "Tunnel not configured"}, status=400)

        await self.tunnel_manager.disconnect()
        logger.info("Tunnel disconnected")
        return web.json_response({"success": True})

    @local_network_only
    async def serve_files_page(self, request):
        """Serve the files management page.

        Injects trusted IP status and config content for auto-authentication.

        Returns:
            HTML response with files management interface
        """
        template_content = self.templates.get("files.html", "")

        # Check if client IP is trusted and inject auto-auth flag
        client_ip = get_client_ip(request)
        is_trusted_ip = client_ip in self.admin_config.trusted_ips if hasattr(self, "admin_config") else False

        # Read config file content (only if config file was provided)
        config_path = self.config.config_path
        config_content = ""
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read config file: {e}")

        # Inject JavaScript variables for trusted IP auto-auth and config
        js_variables = f"""
            const IS_TRUSTED_IP = {str(is_trusted_ip).lower()};
            const CONFIG_CONTENT = {json.dumps(config_content) if config_path else 'null'};
            const CONFIG_PATH = {json.dumps(config_path) if config_path else 'null'};
        """

        # Inject the JavaScript variables before </head>
        template_content = template_content.replace("</head>", f"<script>{js_variables}</script>\n    </head>")

        return web.Response(text=template_content, content_type="text/html")

    def _list_files_in_directory(self, directory, file_type):
        """Helper to list files in a directory with metadata.

        Args:
            directory: Directory path to list
            file_type: Type label for files (e.g., "log", "csv")

        Returns:
            List of file dictionaries with name, size, modified, type (sorted by modified)
        """
        files = []
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    files.append(
                        {
                            "name": filename,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "type": file_type,
                        }
                    )
        # Sort files by modified date (newest first)
        files.sort(key=lambda x: x["modified"], reverse=True)
        return files

    @admin_auth_required
    async def files_list(self, request):
        """List all files in logs_dir, csv_dir, and quizzes_dir with metadata.

        Returns:
            JSON response with logs, csv, and quizzes file lists
        """
        logs_files = self._list_files_in_directory(self.logs_dir, "log")
        csv_files = self._list_files_in_directory(self.csv_dir, "csv")
        quizzes_files = self._list_files_in_directory(self.quizzes_dir, "yaml")

        return web.json_response({"logs": logs_files, "csv": csv_files, "quizzes": quizzes_files})

    def _get_file_path_and_validate(self, file_type, filename):
        """Helper to validate file type, filename, and return file path.

        Prevents path traversal attacks and validates file existence.

        Args:
            file_type: Type of file ("csv", "logs", or "quizzes")
            filename: Name of the file

        Returns:
            Tuple of (file_path, error_response) where error_response is None on success
        """
        # Determine base directory from file type
        if file_type == "csv":
            base_dir = self.csv_dir
        elif file_type == "logs":
            base_dir = self.logs_dir
        elif file_type == "quizzes":
            base_dir = self.quizzes_dir
        else:
            return None, web.json_response({"error": "Invalid file type"}, status=400)

        # Validate filename (prevent path traversal)
        if not self._is_safe_filename(filename):
            return None, web.json_response({"error": "Invalid filename"}, status=400)

        file_path = os.path.join(base_dir, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            return None, web.json_response({"error": "File not found"}, status=404)

        # Check if it's actually a file (not directory)
        if not os.path.isfile(file_path):
            return None, web.json_response({"error": "Path is not a file"}, status=400)

        return file_path, None

    @admin_auth_required
    async def files_view(self, request):
        """View file contents (text files only, with 10MB size limit).

        Args:
            request: aiohttp request with type and filename in path

        Returns:
            Plain text response with file content or error if too large/binary
        """
        file_type = request.match_info["type"]
        filename = request.match_info["filename"]

        # Validate and get file path
        file_path, error = self._get_file_path_and_validate(file_type, filename)
        if error:
            return error

        # Check file size (limit to 10MB for viewing)
        MAX_VIEW_SIZE = 1024 * 1024 * 10  # 10MB
        file_size = os.path.getsize(file_path)

        if file_size > MAX_VIEW_SIZE:
            return web.json_response(
                {
                    "error": f"File too large for viewing (>10MB). Size: {file_size} bytes. Use download instead.",
                    "size": file_size,
                },
                status=400,
            )

        # Read file content
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
        except UnicodeDecodeError:
            return web.json_response({"error": "File contains non-UTF-8 content. Use download instead."}, status=400)

        return web.Response(
            text=content, content_type="text/plain", headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )

    @admin_auth_required
    async def files_download(self, request):
        """Download file directly.

        Args:
            request: aiohttp request with type and filename in path

        Returns:
            File response with appropriate content-type and disposition headers
        """
        file_type = request.match_info["type"]
        filename = request.match_info["filename"]

        # Validate and get file path
        file_path, error = self._get_file_path_and_validate(file_type, filename)
        if error:
            return error

        # Determine content type
        if file_type == "csv":
            content_type = "text/csv"
        elif file_type == "quizzes":
            content_type = "text/yaml"
        else:
            content_type = "text/plain"

        # Return file response with proper headers
        return web.FileResponse(
            file_path,
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": content_type},
        )

    @admin_auth_required
    async def files_save_quiz(self, request):
        """Save quiz file with validation and backup.

        Args:
            request: aiohttp request with filename in path and content in body

        Returns:
            JSON response with success status and backup filename
        """
        filename = request.match_info["filename"]
        data = await request.json()
        content = data.get("content", "").strip()

        if not content:
            return web.json_response({"error": "Content is required"}, status=400)

        # Validate filename
        if not self._is_safe_filename(filename):
            return web.json_response({"error": "Invalid filename"}, status=400)

        quiz_path = os.path.join(self.quizzes_dir, filename)

        if not os.path.exists(quiz_path):
            return web.json_response({"error": "Quiz file not found"}, status=404)

        # Validate YAML
        try:
            parsed = yaml.safe_load(content)
            errors = []
            if not self._validate_quiz_data(parsed, errors):
                return web.json_response({"error": "Неправильна структура даних квізу", "errors": errors}, status=400)
        except yaml.YAMLError as e:
            return web.json_response({"error": f"Неправильний YAML: {str(e)}"}, status=400)

        # Create backup
        backup_path = quiz_path + ".backup"

        shutil.copy2(quiz_path, backup_path)

        # Write the updated content
        with open(quiz_path, "w", encoding="utf-8") as f:
            f.write(content)

        # If this is the currently active quiz, reload it
        if filename == self.current_quiz_file:
            logger.info(f"Reloading active quiz after edit: {filename}")
            await self.load_questions()

        logger.info(f"Saved quiz file: {filename}")
        return web.json_response(
            {
                "success": True,
                "message": f'Quiz "{filename}" saved successfully (backup created)',
                "backup": backup_path,
            }
        )

    def _is_safe_filename(self, filename):
        """Check if filename is safe (no path traversal attempts).

        Validates against path traversal, null bytes, special names, and length.

        Args:
            filename: Filename to validate

        Returns:
            True if safe, False otherwise
        """
        if not filename:
            return False

        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            return False

        # Check for null bytes
        if "\0" in filename:
            return False

        # Check for special filenames
        if filename in [".", ".."]:
            return False

        # Check for overly long filenames
        if len(filename) > 255:
            return False

        return True

    async def serve_index_page(self, request):
        """Serve the index.html page from static directory.

        Returns:
            HTML file response
        """
        index_path = f"{self.static_dir}/index.html"
        return web.FileResponse(index_path, headers={"Content-Type": "text/html; charset=utf-8"})

    @local_network_only
    async def serve_admin_page(self, request):
        """Serve the admin interface page.

        Injects trusted IP status, network info, downloadable quizzes, and version.

        Returns:
            HTML response with admin interface
        """
        template_content = self.templates.get("admin.html", "")

        # Check if client IP is trusted and inject auto-auth flag
        client_ip = get_client_ip(request)
        is_trusted_ip = client_ip in self.admin_config.trusted_ips if hasattr(self, "admin_config") else False

        # Get network information (external interfaces only)
        interfaces = get_network_interfaces()  # This already excludes localhost
        port = self.config.server.port

        # Generate URLs for external network interfaces only
        urls = []
        for ip in interfaces:
            urls.append({"label": f"Network Access ({ip})", "quiz_url": f"http://{ip}:{port}/"})

        # Prepare network info for JavaScript (only what's actually used)
        network_info = {"urls": urls}

        # Get downloadable quizzes configuration
        downloadable_quizzes = []
        if hasattr(self.config, "quizzes") and self.config.quizzes and self.config.quizzes.quizzes:
            for quiz in self.config.quizzes.quizzes:
                downloadable_quizzes.append(
                    {"name": quiz.name, "download_path": quiz.download_path, "folder": quiz.folder}
                )

        # Read SSH public key if tunnel is configured
        tunnel_public_key = ""
        if self.tunnel_manager and self.tunnel_manager.config and self.tunnel_manager.config.public_key:
            try:
                public_key_path = self.tunnel_manager.config.public_key

                # Resolve path relative to binary directory if needed
                if not os.path.isabs(public_key_path):
                    binary_dir = os.environ.get("WEBQUIZ_BINARY_DIR")
                    if binary_dir:
                        public_key_path = os.path.join(binary_dir, public_key_path)

                if os.path.exists(public_key_path):
                    with open(public_key_path, "r") as f:
                        tunnel_public_key = f.read().strip()
            except Exception as e:
                logger.error(f"Error reading tunnel public key: {e}")

        # Inject trusted IP status, network info, downloadable quizzes, and version into the template
        server_data_script = f"""
    const IS_TRUSTED_IP = {str(is_trusted_ip).lower()};
    const NETWORK_INFO = {json.dumps(network_info)};
    const DOWNLOADABLE_QUIZZES = {json.dumps(downloadable_quizzes)};
    const WEBQUIZ_VERSION = {json.dumps(package_version)};
    const TUNNEL_PUBLIC_KEY = {json.dumps(tunnel_public_key)};"""

        template_content = template_content.replace("<script>", f"<script>{server_data_script}\n")

        return web.Response(text=template_content, content_type="text/html")

    @local_network_only
    async def serve_live_stats_page(self, request):
        """Serve the live stats page.

        Returns:
            HTML response with live stats interface
        """
        try:
            template_content = self.templates.get("live_stats.html", "")

            return web.Response(text=template_content, content_type="text/html")
        except Exception as e:
            logger.error(f"Error serving live stats page: {e}")
            return web.Response(text="<h1>Live stats page not found</h1>", content_type="text/html", status=404)

    async def _handle_websocket_connection(
        self, request, client_list: List[web.WebSocketResponse], initial_state_data: dict, client_type: str
    ):
        """Generic WebSocket connection handler.

        Manages connection lifecycle: adds to list, sends initial state,
        handles messages, removes on disconnect.

        Args:
            request: aiohttp request object
            client_list: List to manage connected clients
            initial_state_data: Initial data to send on connection
            client_type: Description for logging

        Returns:
            WebSocket response object
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Add to connected clients
        client_list.append(ws)
        logger.info(f"New {client_type} client connected. Total clients: {len(client_list)}")

        # Send initial state
        try:
            await ws.send_str(json.dumps(initial_state_data))
        except Exception as e:
            logger.error(f"Error sending initial state to {client_type} client: {e}")

        # Listen for messages (mainly for connection keep-alive)
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "ping":
                        await ws.send_str(json.dumps({"type": "pong"}))
                except Exception as e:
                    logger.warning(f"Error processing {client_type} message: {e}")
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"{client_type} error: {ws.exception()}")
                break

        # Remove from connected clients when connection closes
        if ws in client_list:
            client_list.remove(ws)
        logger.info(f"{client_type} client disconnected. Total clients: {len(client_list)}")

        return ws

    @local_network_only
    async def websocket_live_stats(self, request):
        """WebSocket endpoint for live stats updates.

        Filters to only show approved users in live stats.

        Returns:
            WebSocket connection with live stats updates
        """
        # Filter out unapproved users from live stats
        approved_users = {
            user_id: user_data["username"]
            for user_id, user_data in self.users.items()
            if user_data.get("approved", True)  # Include if approved or no approval field (backward compatibility)
        }

        # Filter live stats to only include approved users
        approved_live_stats = {
            user_id: stats for user_id, stats in self.live_stats.items() if user_id in approved_users
        }

        # Build completion status for approved users
        completed_users = {
            user_id: (len(self.user_answers.get(user_id, [])) == len(self.questions))
            for user_id in approved_users.keys()
        }

        # Build completion timestamps for approved users
        completion_times = {
            user_id: self.user_stats.get(user_id, {}).get("completed_at")
            for user_id in approved_users.keys()
            if user_id in self.user_stats
        }

        initial_data = {
            "type": "initial_state",
            "live_stats": approved_live_stats,
            "users": approved_users,
            "completed_users": completed_users,
            "completion_times": completion_times,
            "questions": self.questions,
            "total_questions": len(self.questions),
            "current_quiz": os.path.basename(self.current_quiz_file) if self.current_quiz_file else None,
        }
        return await self._handle_websocket_connection(request, self.websocket_clients, initial_data, "WebSocket")

    @local_network_only
    async def websocket_admin(self, request):
        """WebSocket endpoint for admin real-time notifications.

        Sends notifications for user registrations awaiting approval.

        Returns:
            WebSocket connection with admin notifications
        """
        # Filter users waiting for approval and extract only registration fields
        pending_users = {}
        if hasattr(self.config, "registration") and self.config.registration.approve:
            for user_id, user_data in self.users.items():
                if not user_data.get("approved", True):
                    pending_users[user_id] = {
                        "username": user_data["username"],
                        "registration_fields": self._extract_registration_fields(user_data),
                    }

        # Get tunnel status if configured
        tunnel_info = None
        if self.tunnel_manager:
            tunnel_status = self.tunnel_manager.get_status()
            tunnel_info = {
                "configured": True,
                "server": self.config.tunnel.server,
                "socket_name": self.config.tunnel.socket_name,
                **tunnel_status,
            }

        initial_data = {
            "type": "initial_state",
            "pending_users": pending_users,
            "requires_approval": hasattr(self.config, "registration") and self.config.registration.approve,
            "tunnel": tunnel_info,
        }
        return await self._handle_websocket_connection(
            request, self.admin_websocket_clients, initial_data, "admin WebSocket"
        )


async def create_app(config: WebQuizConfig):
    """Create and configure the application"""

    server = TestingServer(config)

    # Initialize log file first (this will set server.log_file)
    await server.initialize_log_file()

    # Configure logging with the actual log file path
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(server.log_file), logging.StreamHandler()],  # Also log to console
        force=True,  # Override any existing configuration
    )

    # Log startup environment information for troubleshooting
    log_startup_environment(config)

    # Initialize SSH tunnel if configured (checks keys, but doesn't auto-connect)
    await server.initialize_tunnel()

    # Load questions and create HTML with embedded data (CSV will be initialized in switch_quiz)
    await server.load_questions()

    # Start periodic flush task
    asyncio.create_task(server.periodic_flush())

    # Create app with middleware
    app = web.Application(middlewares=[error_middleware])

    # Routes
    app.router.add_post("/api/register", server.register_user)
    app.router.add_put("/api/update-registration", server.update_registration)
    app.router.add_post("/api/submit-answer", server.submit_answer)
    app.router.add_post("/api/question-start", server.question_start)
    app.router.add_get("/api/verify-user/{user_id}", server.verify_user_id)

    # Admin routes
    app.router.add_get("/admin/", server.serve_admin_page)
    app.router.add_post("/api/admin/auth", server.admin_auth)
    app.router.add_get("/api/admin/check-session", server.admin_check_session)
    app.router.add_get("/api/admin/version-check", server.admin_version_check)
    app.router.add_put("/api/admin/approve-user", server.admin_approve_user)
    app.router.add_get("/api/admin/list-quizzes", server.admin_list_quizzes)
    app.router.add_post("/api/admin/switch-quiz", server.admin_switch_quiz)
    app.router.add_get("/api/admin/quiz/{filename}", server.admin_get_quiz)
    app.router.add_post("/api/admin/create-quiz", server.admin_create_quiz)
    app.router.add_put("/api/admin/quiz/{filename}", server.admin_update_quiz)
    app.router.add_delete("/api/admin/quiz/{filename}", server.admin_delete_quiz)
    app.router.add_post("/api/admin/validate-quiz", server.admin_validate_quiz)
    app.router.add_get("/api/admin/list-images", server.admin_list_images)
    app.router.add_get("/api/admin/list-files", server.admin_list_files)
    app.router.add_post("/api/admin/download-quiz", server.admin_download_quiz)
    app.router.add_put("/api/admin/config", server.admin_update_config)

    # Tunnel routes
    app.router.add_post("/api/admin/tunnel/connect", server.tunnel_connect)
    app.router.add_post("/api/admin/tunnel/disconnect", server.tunnel_disconnect)

    app.router.add_get("/ws/admin", server.websocket_admin)

    # File management routes (admin access)
    app.router.add_get("/files/", server.serve_files_page)
    # Quiz file attachment download route
    app.router.add_get("/attach/{filename}", server.serve_quiz_file)
    app.router.add_get("/api/files/list", server.files_list)
    app.router.add_get("/api/files/{type}/view/{filename}", server.files_view)
    app.router.add_get("/api/files/{type}/download/{filename}", server.files_download)
    app.router.add_put("/api/files/quizzes/save/{filename}", server.files_save_quiz)

    # Live stats routes (public access)
    app.router.add_get("/live-stats/", server.serve_live_stats_page)
    app.router.add_get("/ws/live-stats", server.websocket_live_stats)

    # Serve index.html at root path
    app.router.add_get("/", server.serve_index_page)

    # Ensure imgs and attach directories exist
    ensure_directory_exists(os.path.join(config.paths.quizzes_dir, "imgs"))
    ensure_directory_exists(os.path.join(config.paths.quizzes_dir, "attach"))
    app.router.add_static(
        "/imgs/",
        path=os.path.join(config.paths.quizzes_dir, "imgs"),
        show_index=True,
        name="imgs",
    )
    # Serve static files from configured static directory
    app.router.add_static("/", path=config.paths.static_dir, name="static")

    return app
