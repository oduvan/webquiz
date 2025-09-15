"""
Test CLI interface directory and file creation functionality.

This test verifies that the webquiz CLI creates the expected directories
and files when initialized.
"""
import pytest
import tempfile
import shutil
import os
import subprocess
import time


def run_webquiz_cli_briefly(args=None):
    """Helper to start webquiz CLI briefly for directory creation tests."""
    env = os.environ.copy()
    # Add parent directory to PYTHONPATH so webquiz module can be found
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env['PYTHONPATH'] = parent_dir + ':' + env.get('PYTHONPATH', '')
    
    cmd = ['python', '-m', 'webquiz.cli']
    if args:
        cmd += args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    # Let it initialize
    time.sleep(2)
    # Terminate the process
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

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


def test_webquiz_cli_creates_default_directories(temp_dir):
    """Test that webquiz CLI creates expected default directories."""
    run_webquiz_cli_briefly()
    expected_dirs = ['quizzes', 'logs', 'data', 'static']
    for dir_name in expected_dirs:
        dir_path = os.path.join(temp_dir, dir_name)
        assert os.path.exists(dir_path), f"Directory {dir_name} was not created by CLI"
        assert os.path.isdir(dir_path), f"Path {dir_name} is not a directory"


def test_webquiz_cli_creates_all_files(temp_dir):
    """Test that webquiz CLI creates all expected directories and files."""
    run_webquiz_cli_briefly()
    print(f"Contents of temp_dir: {os.listdir(temp_dir)}")
    expected_dirs = ['quizzes', 'logs', 'data', 'static']
    for dir_name in expected_dirs:
        dir_path = os.path.join(temp_dir, dir_name)
        assert os.path.exists(dir_path), f"Directory {dir_name} was not created by CLI command"
        assert os.path.isdir(dir_path), f"Path {dir_name} is not a directory"
    imgs_dir = os.path.join(temp_dir, 'quizzes', 'imgs')
    assert os.path.exists(imgs_dir), "quizzes/imgs directory was not created"
    default_quiz = os.path.join(temp_dir, 'quizzes', 'default.yaml')
    assert os.path.exists(default_quiz), "Default quiz file was not created by CLI command"
    logs_dir = os.path.join(temp_dir, 'logs')
    log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
    assert len(log_files) > 0, "No log files were created by CLI command"
    index_file = os.path.join(temp_dir, 'static', 'index.html')
    assert os.path.exists(index_file), "index.html was not created in static directory"


def test_webquiz_cli_with_custom_directories(temp_dir):
    """Test that webquiz CLI respects custom directory arguments."""
    custom_quizzes = os.path.join(temp_dir, 'my_quizzes')
    custom_logs = os.path.join(temp_dir, 'my_logs')
    custom_data = os.path.join(temp_dir, 'my_data')
    custom_static = os.path.join(temp_dir, 'my_static')
    run_webquiz_cli_briefly([
        '--quizzes-dir', custom_quizzes,
        '--logs-dir', custom_logs,
        '--csv-dir', custom_data,
        '--static', custom_static
    ])
    custom_dirs = [custom_quizzes, custom_logs, custom_data, custom_static]
    for dir_path in custom_dirs:
        assert os.path.exists(dir_path), f"Custom directory {dir_path} was not created"
        assert os.path.isdir(dir_path), f"Path {dir_path} is not a directory"
    default_quiz = os.path.join(custom_quizzes, 'default.yaml')
    assert os.path.exists(default_quiz), "Default quiz file was not created in custom quizzes directory"


def test_webquiz_cli_handles_existing_directories(temp_dir):
    """Test that webquiz CLI handles pre-existing directories gracefully."""
    quizzes_dir = os.path.join(temp_dir, 'quizzes')
    os.makedirs(quizzes_dir)
    custom_file = os.path.join(quizzes_dir, 'custom.yaml')
    with open(custom_file, 'w') as f:
        f.write("title: Custom Quiz\nquestions: []")
    run_webquiz_cli_briefly()
    assert os.path.exists(quizzes_dir)
    assert os.path.exists(custom_file)
    with open(custom_file, 'r') as f:
        content = f.read()
        assert "Custom Quiz" in content
    for dir_name in ['logs', 'data', 'static']:
        dir_path = os.path.join(temp_dir, dir_name)
        assert os.path.exists(dir_path), f"Directory {dir_name} was not created"


def test_webquiz_cli_with_config_file(temp_dir):
    """Test that webquiz CLI respects configuration file."""
    # Create a custom config file
    config_content = """
server:
  host: "127.0.0.1"
  port: 9090

paths:
  quizzes_dir: "custom_quizzes"
  logs_dir: "custom_logs"
  csv_dir: "custom_data"
  static_dir: "custom_static"

admin:
  master_key: "test123"
"""
    config_file = os.path.join(temp_dir, 'test_config.yaml')
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    run_webquiz_cli_briefly(['--config', config_file])
    
    # Check that custom directories from config were created
    expected_dirs = ['custom_quizzes', 'custom_logs', 'custom_data', 'custom_static']
    for dir_name in expected_dirs:
        dir_path = os.path.join(temp_dir, dir_name)
        assert os.path.exists(dir_path), f"Config directory {dir_name} was not created"
        assert os.path.isdir(dir_path), f"Path {dir_name} is not a directory"
    
    # Check that default quiz file was created in custom quizzes directory
    default_quiz = os.path.join(temp_dir, 'custom_quizzes', 'default.yaml')
    assert os.path.exists(default_quiz), "Default quiz file was not created in custom quizzes directory"


def test_webquiz_cli_config_file_with_cli_overrides(temp_dir):
    """Test that CLI arguments override configuration file settings."""
    # Create a config file with one set of paths
    config_content = """
paths:
  quizzes_dir: "config_quizzes"
  logs_dir: "config_logs"
  csv_dir: "config_data"
  static_dir: "config_static"
"""
    config_file = os.path.join(temp_dir, 'test_config.yaml')
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    # Run with config file but override some paths via CLI
    override_quizzes = os.path.join(temp_dir, 'cli_override_quizzes')
    override_logs = os.path.join(temp_dir, 'cli_override_logs')
    
    run_webquiz_cli_briefly([
        '--config', config_file,
        '--quizzes-dir', override_quizzes,
        '--logs-dir', override_logs
    ])
    
    # CLI overrides should take precedence
    assert os.path.exists(override_quizzes), "CLI override for quizzes directory failed"
    assert os.path.exists(override_logs), "CLI override for logs directory failed"
    
    # Config file values should be used where no CLI override exists
    assert os.path.exists(os.path.join(temp_dir, 'config_data')), "Config CSV directory not created"
    assert os.path.exists(os.path.join(temp_dir, 'config_static')), "Config static directory not created"
    
    # Config directories that were overridden should NOT exist
    assert not os.path.exists(os.path.join(temp_dir, 'config_quizzes')), "Config quizzes dir should not exist (overridden)"
    assert not os.path.exists(os.path.join(temp_dir, 'config_logs')), "Config logs dir should not exist (overridden)"


def test_webquiz_cli_with_master_key(temp_dir):
    """Test that webquiz CLI accepts master key configuration."""
    # Test with master key via CLI argument
    run_webquiz_cli_briefly(['--master-key', 'secret123'])
    
    # Check that all directories are still created normally
    expected_dirs = ['quizzes', 'logs', 'data', 'static']
    for dir_name in expected_dirs:
        dir_path = os.path.join(temp_dir, dir_name)
        assert os.path.exists(dir_path), f"Directory {dir_name} was not created with master key"
    
    # Check that webquiz.yaml config file was created (it contains master key info)
    config_file = os.path.join(temp_dir, 'webquiz.yaml')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            content = f.read()
            # Config file should contain admin section when master key is set
            assert 'admin:' in content or 'master_key:' in content


def test_webquiz_cli_creates_webquiz_yaml_config(temp_dir):
    """Test that webquiz CLI creates a webquiz.yaml configuration file."""
    run_webquiz_cli_briefly()
    
    # Check that webquiz.yaml was created
    config_file = os.path.join(temp_dir, 'webquiz.yaml')
    assert os.path.exists(config_file), "webquiz.yaml configuration file was not created"
    
    # Check that the config file contains expected sections
    with open(config_file, 'r') as f:
        content = f.read()
        expected_sections = ['server:', 'paths:', 'admin:', 'options:']
        for section in expected_sections:
            assert section in content, f"Config file missing {section} section"