"""
Tests for configuration loading and utility functions in server.py.

These tests ensure that config loading, path resolution, and other utility
functions work correctly.
"""

import os
import tempfile
import yaml
from pathlib import Path

from webquiz.config import (
    load_config_from_yaml,
    resolve_path_relative_to_binary,
    WebQuizConfig,
    ServerConfig,
    PathsConfig,
    AdminConfig,
    RegistrationConfig,
)
from webquiz.server import (
    load_config_with_overrides,
    get_default_config_path,
    read_package_resource,
    get_package_version,
    ensure_directory_exists,
)


def test_ensure_directory_exists():
    """Test that ensure_directory_exists creates directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = os.path.join(tmpdir, "test_dir")
        assert not os.path.exists(test_dir)

        result = ensure_directory_exists(test_dir)

        assert os.path.exists(test_dir)
        assert os.path.isdir(test_dir)
        assert result == test_dir


def test_ensure_directory_exists_already_exists():
    """Test that ensure_directory_exists works with existing directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Directory already exists
        result = ensure_directory_exists(tmpdir)
        assert result == tmpdir
        assert os.path.isdir(tmpdir)


def test_resolve_path_relative_to_binary_absolute_path():
    """Test that absolute paths are returned unchanged."""
    abs_path = "/absolute/path/to/something"
    result = resolve_path_relative_to_binary(abs_path)
    assert result == abs_path


def test_resolve_path_relative_to_binary_empty_path():
    """Test that empty paths are returned unchanged."""
    result = resolve_path_relative_to_binary("")
    assert result == ""

    result = resolve_path_relative_to_binary(None)
    assert result is None


def test_resolve_path_relative_to_binary_no_binary_dir():
    """Test path resolution when not running as binary."""
    # Save and clear WEBQUIZ_BINARY_DIR
    old_value = os.environ.get("WEBQUIZ_BINARY_DIR")
    if "WEBQUIZ_BINARY_DIR" in os.environ:
        del os.environ["WEBQUIZ_BINARY_DIR"]

    try:
        result = resolve_path_relative_to_binary("relative/path")
        assert result == "relative/path"
    finally:
        # Restore environment
        if old_value is not None:
            os.environ["WEBQUIZ_BINARY_DIR"] = old_value


def test_resolve_path_relative_to_binary_with_binary_dir():
    """Test path resolution when running as binary."""
    # Set WEBQUIZ_BINARY_DIR
    old_value = os.environ.get("WEBQUIZ_BINARY_DIR")
    test_binary_dir = "/test/binary/dir"
    os.environ["WEBQUIZ_BINARY_DIR"] = test_binary_dir

    try:
        result = resolve_path_relative_to_binary("relative/path")
        expected = str(Path(test_binary_dir) / "relative/path")
        assert result == expected
    finally:
        # Restore environment
        if old_value is not None:
            os.environ["WEBQUIZ_BINARY_DIR"] = old_value
        else:
            del os.environ["WEBQUIZ_BINARY_DIR"]


def test_read_package_resource():
    """Test reading package resources (templates)."""
    # Read a known template file
    content = read_package_resource("server_config.yaml.example")
    assert content is not None
    assert len(content) > 0
    # Check for expected content in config example
    assert "server:" in content or "admin:" in content


def test_get_package_version():
    """Test getting package version."""
    version = get_package_version()
    assert version is not None
    assert isinstance(version, str)
    # Version should be either a semver string or "unknown"
    assert version == "unknown" or version[0].isdigit()


def test_load_config_from_yaml_empty_file():
    """Test loading config from empty YAML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config is not None
        assert isinstance(config, WebQuizConfig)
        # Should have defaults
        assert config.server.port == 8080
        assert config.server.host == "0.0.0.0"
    finally:
        os.unlink(config_path)


def test_load_config_from_yaml_with_server_config():
    """Test loading config with server settings."""
    config_data = {
        "server": {
            "host": "127.0.0.1",
            "port": 9090,
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9090
    finally:
        os.unlink(config_path)


def test_load_config_from_yaml_with_paths():
    """Test loading config with custom paths."""
    config_data = {
        "paths": {
            "quizzes_dir": "custom_quizzes",
            "logs_dir": "custom_logs",
            "csv_dir": "custom_data",
            "static_dir": "custom_static",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.paths.quizzes_dir == "custom_quizzes"
        assert config.paths.logs_dir == "custom_logs"
        assert config.paths.csv_dir == "custom_data"
        assert config.paths.static_dir == "custom_static"
    finally:
        os.unlink(config_path)


def test_load_config_from_yaml_with_admin():
    """Test loading config with admin settings."""
    config_data = {
        "admin": {
            "master_key": "test_key_123",
            "trusted_ips": ["192.168.1.1", "10.0.0.1"],
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.admin.master_key == "test_key_123"
        assert "192.168.1.1" in config.admin.trusted_ips
        assert "10.0.0.1" in config.admin.trusted_ips
    finally:
        os.unlink(config_path)


def test_load_config_from_yaml_with_registration():
    """Test loading config with registration settings."""
    config_data = {
        "registration": {
            "fields": ["grade", "school"],
            "approve": True,
            "username_label": "Student Name",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.registration.fields == ["grade", "school"]
        assert config.registration.approve is True
        assert config.registration.username_label == "Student Name"
    finally:
        os.unlink(config_path)


def test_load_config_from_yaml_with_downloadable_quizzes():
    """Test loading config with downloadable quizzes."""
    config_data = {
        "quizzes": [
            {
                "name": "Test Quiz 1",
                "download_path": "https://example.com/quiz1.zip",
                "folder": "quiz1",
            },
            {
                "name": "Test Quiz 2",
                "download_path": "https://example.com/quiz2.zip",
                "folder": "quiz2",
            },
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert len(config.quizzes.quizzes) == 2
        assert config.quizzes.quizzes[0].name == "Test Quiz 1"
        assert config.quizzes.quizzes[0].download_path == "https://example.com/quiz1.zip"
        assert config.quizzes.quizzes[0].folder == "quiz1"
        assert config.quizzes.quizzes[1].name == "Test Quiz 2"
    finally:
        os.unlink(config_path)


def test_load_config_with_overrides_cli_overrides():
    """Test that CLI overrides take precedence over config file."""
    config_data = {
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
        },
        "admin": {
            "master_key": "file_key",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Override with CLI parameters
        config = load_config_with_overrides(
            config_path=config_path,
            port=9999,
            master_key="cli_key",
        )

        # CLI overrides should win
        assert config.server.port == 9999
        assert config.admin.master_key == "cli_key"
        # File value should be used for non-overridden settings
        assert config.server.host == "0.0.0.0"
    finally:
        os.unlink(config_path)


def test_load_config_with_overrides_env_variable():
    """Test that environment variable for master key is respected."""
    # Set environment variable
    old_value = os.environ.get("WEBQUIZ_MASTER_KEY")
    os.environ["WEBQUIZ_MASTER_KEY"] = "env_key_123"

    try:
        config = load_config_with_overrides()
        assert config.admin.master_key == "env_key_123"
    finally:
        # Restore environment
        if old_value is not None:
            os.environ["WEBQUIZ_MASTER_KEY"] = old_value
        else:
            del os.environ["WEBQUIZ_MASTER_KEY"]


def test_load_config_with_overrides_no_config_file():
    """Test loading config without a config file (uses defaults)."""
    config = load_config_with_overrides(config_path=None)
    assert config is not None
    assert isinstance(config, WebQuizConfig)
    assert config.server.port == 8080


def test_dataclass_defaults():
    """Test that dataclass defaults are properly set."""
    # ServerConfig
    server = ServerConfig()
    assert server.host == "0.0.0.0"
    assert server.port == 8080

    # PathsConfig
    paths = PathsConfig()
    assert paths.quizzes_dir is not None  # Should be set by __post_init__
    assert paths.logs_dir is not None

    # AdminConfig
    admin = AdminConfig()
    assert admin.master_key is None
    assert admin.trusted_ips == ["127.0.0.1"]  # Default

    # RegistrationConfig
    registration = RegistrationConfig()
    assert registration.fields == []
    assert registration.approve is False
    assert registration.username_label == "Ім'я користувача"

    # WebQuizConfig
    config = WebQuizConfig()
    assert config.server is not None
    assert config.paths is not None
    assert config.admin is not None
    assert config.registration is not None
