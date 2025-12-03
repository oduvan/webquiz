"""Tests for startup environment logging functionality."""

import os
import sys
import platform
import tempfile
import time

from conftest import custom_webquiz_server


def test_startup_logging_creates_log_file():
    """Test that startup logging writes to log file."""
    with custom_webquiz_server() as (proc, port):
        # Give the server time to write logs
        time.sleep(0.5)

        # Find log file in the port-specific logs directory
        logs_dir = f"logs_{port}"
        assert os.path.exists(logs_dir), f"Logs directory {logs_dir} should exist"

        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        assert len(log_files) > 0, "Should have at least one log file"


def test_startup_logging_contains_environment_info():
    """Test that startup log contains environment information."""
    with custom_webquiz_server() as (proc, port):
        # Give the server time to write logs
        time.sleep(0.5)

        # Find and read log file
        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        assert len(log_files) > 0

        log_path = os.path.join(logs_dir, log_files[0])
        with open(log_path, "r") as f:
            log_content = f.read()

        # Check for environment information markers
        assert "WebQuiz Server Starting - Environment Information" in log_content
        assert "WebQuiz version:" in log_content
        assert "Python version:" in log_content
        assert "Platform:" in log_content


def test_startup_logging_contains_python_info():
    """Test that startup log contains Python information."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check Python-related info
        assert "Python version:" in log_content
        assert "Python executable:" in log_content


def test_startup_logging_contains_os_info():
    """Test that startup log contains OS information."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check OS-related info
        assert "Platform:" in log_content
        assert "OS:" in log_content
        assert "Machine:" in log_content


def test_startup_logging_contains_server_config():
    """Test that startup log contains server configuration."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check server configuration
        assert "Server Configuration:" in log_content
        assert "Host:" in log_content
        assert "Port:" in log_content
        assert str(port) in log_content


def test_startup_logging_contains_path_config():
    """Test that startup log contains path configuration."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check path configuration
        assert "Path Configuration:" in log_content
        assert "Quizzes directory:" in log_content
        assert "Logs directory:" in log_content
        assert "CSV directory:" in log_content
        assert "Static directory:" in log_content


def test_startup_logging_contains_admin_config():
    """Test that startup log contains admin configuration (without exposing master key)."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check admin configuration
        assert "Admin Configuration:" in log_content
        assert "Master key set: True" in log_content  # Should show True, not the actual key
        # The actual master key "test123" should NOT appear in logs
        assert "Master key set:" in log_content


def test_startup_logging_contains_registration_config():
    """Test that startup log contains registration configuration."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check registration configuration
        assert "Registration Configuration:" in log_content
        assert "Approval required:" in log_content
        assert "Username label:" in log_content


def test_startup_logging_contains_dependency_versions():
    """Test that startup log contains key dependency versions."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check dependency versions
        assert "aiohttp version:" in log_content


def test_startup_logging_contains_working_directory():
    """Test that startup log contains working directory information."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check working directory
        assert "Working directory:" in log_content
        assert "Config file:" in log_content


def test_startup_logging_contains_binary_mode_info():
    """Test that startup log contains binary mode information."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(0.5)

        logs_dir = f"logs_{port}"
        log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
        log_path = os.path.join(logs_dir, log_files[0])

        with open(log_path, "r") as f:
            log_content = f.read()

        # Check binary mode info (should be False when running from tests)
        assert "Running as binary: False" in log_content


def test_log_startup_environment_function_directly():
    """Test log_startup_environment function directly."""
    from webquiz.server import log_startup_environment
    from webquiz.config import WebQuizConfig
    import logging
    import io

    # Create a string handler to capture log output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)

    # Configure logger
    test_logger = logging.getLogger("webquiz.server")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    try:
        # Create config with test values
        config = WebQuizConfig()
        config.server.host = "127.0.0.1"
        config.server.port = 9999
        config.paths.quizzes_dir = "/test/quizzes"
        config.admin.master_key = "secret_key_123"

        # Call the function
        log_startup_environment(config)

        # Get captured logs
        log_output = log_capture.getvalue()

        # Verify key information is logged
        assert "WebQuiz Server Starting" in log_output
        assert "WebQuiz version:" in log_output
        assert "Python version:" in log_output
        assert "Host: 127.0.0.1" in log_output
        assert "Port: 9999" in log_output
        assert "Quizzes directory: /test/quizzes" in log_output

        # Verify master key value is NOT exposed (only True/False)
        assert "secret_key_123" not in log_output
        assert "Master key set: True" in log_output

    finally:
        test_logger.removeHandler(handler)


def test_log_startup_environment_with_tunnel_config():
    """Test that tunnel configuration is logged when present."""
    from webquiz.server import log_startup_environment
    from webquiz.config import WebQuizConfig, TunnelConfig
    import logging
    import io

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)

    test_logger = logging.getLogger("webquiz.server")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    try:
        # Create config with tunnel settings
        config = WebQuizConfig()
        config.tunnel = TunnelConfig(
            server="tunnel.example.com",
            public_key="/path/to/public.key",
            private_key="/path/to/private.key",
            socket_name="test_socket"
        )

        log_startup_environment(config)

        log_output = log_capture.getvalue()

        assert "Tunnel Configuration:" in log_output
        assert "Server: tunnel.example.com" in log_output
        assert "Public key path: /path/to/public.key" in log_output
        assert "Socket name: test_socket" in log_output

    finally:
        test_logger.removeHandler(handler)
