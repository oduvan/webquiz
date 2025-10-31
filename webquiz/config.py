import os
from pathlib import Path
from dataclasses import dataclass, field
import yaml
import logging

from typing import List, Optional


logger = logging.getLogger(__name__)


def resolve_path_relative_to_binary(path_str: str) -> str:
    """Resolve relative paths relative to binary directory when running as binary.

    When running as a PyInstaller binary, relative paths are resolved from the
    binary's directory. When running normally, paths are returned as-is.

    Args:
        path_str: Path string to resolve

    Returns:
        Resolved absolute path when running as binary, original path otherwise
    """
    if not path_str or os.path.isabs(path_str):
        return path_str

    binary_dir = os.environ.get("WEBQUIZ_BINARY_DIR")
    if binary_dir:
        # Running as binary - resolve relative to binary directory
        resolved = Path(binary_dir) / path_str
        return str(resolved)
    else:
        # Running normally - return as-is (relative to cwd)
        return path_str


@dataclass
class ServerConfig:
    """Server configuration data class"""

    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class PathsConfig:
    """Paths configuration data class"""

    quizzes_dir: str = None
    logs_dir: str = None
    csv_dir: str = None
    static_dir: str = None

    def __post_init__(self):
        if self.quizzes_dir is None:
            self.quizzes_dir = resolve_path_relative_to_binary("quizzes")
        if self.logs_dir is None:
            self.logs_dir = resolve_path_relative_to_binary("logs")
        if self.csv_dir is None:
            self.csv_dir = resolve_path_relative_to_binary("data")
        if self.static_dir is None:
            self.static_dir = resolve_path_relative_to_binary("static")


@dataclass
class AdminConfig:
    """Admin configuration data class"""

    master_key: Optional[str] = None
    trusted_ips: List[str] = None

    def __post_init__(self):
        if self.trusted_ips is None:
            self.trusted_ips = ["127.0.0.1"]


@dataclass
class RegistrationConfig:
    """Registration configuration data class"""

    fields: List[str] = None
    approve: bool = False
    username_label: str = "Ім'я користувача"

    def __post_init__(self):
        if self.fields is None:
            self.fields = []


@dataclass
class DownloadableQuiz:
    """Downloadable quiz configuration"""

    name: str
    download_path: str
    folder: str


@dataclass
class QuizzesConfig:
    """Downloadable quizzes configuration data class"""

    quizzes: List[DownloadableQuiz] = None

    def __post_init__(self):
        if self.quizzes is None:
            self.quizzes = []


@dataclass
class TunnelServerConfig:
    """Tunnel server configuration data class (fetched from server or provided locally)"""

    username: str
    socket_directory: str
    base_url: str


@dataclass
class TunnelConfig:
    """SSH Tunnel configuration data class"""

    server: Optional[str] = None
    public_key: Optional[str] = None
    private_key: Optional[str] = None
    socket_name: Optional[str] = None
    config: Optional[TunnelServerConfig] = None

    def __post_init__(self):
        """Resolve key paths relative to binary directory when running as binary"""
        if self.public_key:
            self.public_key = resolve_path_relative_to_binary(self.public_key)
        if self.private_key:
            self.private_key = resolve_path_relative_to_binary(self.private_key)


@dataclass
class WebQuizConfig:
    """Main configuration data class"""

    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    registration: RegistrationConfig = field(default_factory=RegistrationConfig)
    quizzes: QuizzesConfig = field(default_factory=QuizzesConfig)
    tunnel: TunnelConfig = field(default_factory=TunnelConfig)
    config_path: Optional[str] = None  # Path to the config file that was loaded


def load_config_from_yaml(config_path: str) -> WebQuizConfig:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        WebQuizConfig object with loaded configuration or defaults if file not found
    """
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            return WebQuizConfig()

        # Create config objects from YAML data
        server_config = ServerConfig(**(config_data.get("server", {})))
        paths_config = PathsConfig(**(config_data.get("paths", {})))
        admin_config = AdminConfig(**(config_data.get("admin", {})))
        registration_config = RegistrationConfig(**(config_data.get("registration", {})))

        # Parse downloadable quizzes configuration
        quizzes_data = config_data.get("quizzes", [])
        downloadable_quizzes = []
        if quizzes_data:
            for quiz_data in quizzes_data:
                downloadable_quizzes.append(
                    DownloadableQuiz(
                        name=quiz_data["name"], download_path=quiz_data["download_path"], folder=quiz_data["folder"]
                    )
                )
        quizzes_config = QuizzesConfig(quizzes=downloadable_quizzes)

        # Parse tunnel configuration
        tunnel_data = config_data.get("tunnel", {})
        tunnel_server_config = None

        # Check for nested config subsection
        if "config" in tunnel_data:
            config_subsection = tunnel_data.pop("config")  # Remove from dict to avoid unpacking error
            tunnel_server_config = TunnelServerConfig(**config_subsection)

        tunnel_config = TunnelConfig(**tunnel_data, config=tunnel_server_config)

        return WebQuizConfig(
            server=server_config,
            paths=paths_config,
            admin=admin_config,
            registration=registration_config,
            quizzes=quizzes_config,
            tunnel=tunnel_config,
        )
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return WebQuizConfig()
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {e}")
        return WebQuizConfig()
