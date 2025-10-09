import pytest
import subprocess
import time
import tempfile
import shutil
import os
import yaml
from contextlib import contextmanager


# Predefined ports for parallel testing (8 workers max)
TEST_PORTS = [8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087]


def get_worker_port():
    """Get port based on pytest worker ID."""
    # Try to get worker ID from pytest-xdist
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")

    if worker_id == "master":
        return TEST_PORTS[0]

    # Extract worker number from worker_id like 'gw0', 'gw1', etc.
    if isinstance(worker_id, str) and worker_id.startswith("gw"):
        try:
            worker_index = int(worker_id[2:])
            return TEST_PORTS[worker_index % len(TEST_PORTS)]
        except (ValueError, IndexError):
            return TEST_PORTS[0]

    return TEST_PORTS[0]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing and change to it."""
    old_cwd = os.getcwd()
    temp_dir = tempfile.mkdtemp()
    os.chdir(temp_dir)
    try:
        yield temp_dir
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(temp_dir)


@contextmanager
def custom_webquiz_server(config=None, quizzes=None):
    """Context manager for creating webquiz servers with custom configurations.

    Args:
        config: Full configuration dictionary (uses default if None)
        quizzes: Dictionary of quiz_filename -> quiz_data (uses default if None)

    Yields:
        Tuple of (process, port)
    """
    port = get_worker_port()

    # Create default config with port-specific directories to avoid conflicts
    default_config = {
        "server": {"port": port},
        "paths": {
            "quizzes_dir": f"quizzes_{port}",
            "logs_dir": f"logs_{port}",
            "csv_dir": f"data_{port}",
            "static_dir": f"static_{port}",
        },
        "admin": {"master_key": "test123", "trusted_ips": []},
    }

    # Default quiz set
    default_quizzes = {
        "test_quiz.yaml": {
            "title": "Test Quiz",
            "description": "A test quiz for admin API testing",
            "questions": [{"question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1}],
        }
    }

    # Start with default config and deep merge with provided config
    final_config = default_config.copy()
    if config is not None:

        def deep_merge(base, override):
            """Deep merge configuration dictionaries."""
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value

        deep_merge(final_config, config)

    # Always ensure port is set correctly
    final_config["server"]["port"] = port

    # Use provided quizzes or default
    final_quizzes = quizzes if quizzes is not None else default_quizzes

    # Create quiz directory and quiz files
    quizzes_dir = final_config["paths"]["quizzes_dir"]
    os.makedirs(quizzes_dir, exist_ok=True)

    for quiz_filename, quiz_data in final_quizzes.items():
        quiz_file_path = os.path.join(quizzes_dir, quiz_filename)
        with open(quiz_file_path, "w") as f:
            yaml.dump(quiz_data, f)

    # Write config file
    config_filename = f"custom_config_{port}.yaml"
    with open(config_filename, "w") as f:
        yaml.dump(final_config, f)

    # Start server using sys.executable to ensure we use the same Python interpreter
    import sys

    cmd = [sys.executable, "-m", "webquiz.cli", "--config", config_filename]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        # Wait for server to be ready
        import socket

        max_attempts = 30
        for _ in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.1)
                    result = sock.connect_ex(("localhost", port))
                    if result == 0:  # Port is open
                        break
            except (socket.error, OSError):
                pass
            time.sleep(0.1)
        else:
            # Server failed to start
            stdout, stderr = proc.communicate()
            raise Exception(f"Server failed to start within {max_attempts * 0.1}s\nSTDOUT: {stdout}\nSTDERR: {stderr}")

        yield proc, port

    finally:
        # Cleanup server process
        if proc.poll() is None:  # Process is still running
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        # Cleanup directories and config file to prevent data contamination between tests
        try:
            for directory in [
                quizzes_dir,
                final_config["paths"]["logs_dir"],
                final_config["paths"]["csv_dir"],
                final_config["paths"]["static_dir"],
            ]:
                if os.path.exists(directory):
                    shutil.rmtree(directory)

            if os.path.exists(config_filename):
                os.remove(config_filename)
        except Exception as e:
            # Log cleanup errors but don't fail the test
            print(f"Warning: Cleanup error: {e}")
