import pytest
import subprocess
import time
import tempfile
import shutil
import os
import yaml


# Predefined ports for parallel testing (8 workers max)
TEST_PORTS = [8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087]


def get_worker_port():
    """Get port based on pytest worker ID."""
    # Try to get worker ID from pytest-xdist
    worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'master')
    
    if worker_id == 'master':
        return TEST_PORTS[0]
    
    # Extract worker number from worker_id like 'gw0', 'gw1', etc.
    if isinstance(worker_id, str) and worker_id.startswith('gw'):
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


@pytest.fixture
def webquiz_server(temp_dir):  # temp_dir dependency ensures working directory is changed
    """Start webquiz server with master key for admin testing."""
    _ = temp_dir  # Needed for fixture dependency but not used directly
    port = get_worker_port()
    
    # Create a simple quiz file
    os.makedirs('quizzes', exist_ok=True)
    quiz_data = {
        'title': 'Test Quiz',
        'description': 'A test quiz for admin API testing',
        'questions': [
            {
                'question': 'What is 2 + 2?',
                'options': ['3', '4', '5', '6'],
                'correct_answer': 1
            }
        ]
    }
    
    with open('quizzes/test_quiz.yaml', 'w') as f:
        yaml.dump(quiz_data, f)
    
    # Create config file with custom port
    config_data = {
        'server': {
            'port': port
        },
        'admin': {
            'master_key': 'test123',
            'trusted_ips': []  # Empty trusted IPs to force authentication
        }
    }
    
    with open('webquiz_config.yaml', 'w') as f:
        yaml.dump(config_data, f)
    
    # Start server with config file
    cmd = ['python', '-m', 'webquiz.cli', '--config', 'webquiz_config.yaml']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Wait for server port to be ready
    import socket
    max_attempts = 30  # 30 attempts with 0.1s delay = max 3s
    for _ in range(max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.1)
                result = sock.connect_ex(('localhost', port))
                if result == 0:  # Port is open
                    break
        except (socket.error, OSError):
            pass
        time.sleep(0.1)  # Wait 100ms before retry
    else:
        # If we get here, server didn't start in time
        proc.terminate()
        stdout, stderr = proc.communicate()
        raise Exception(f"Server failed to start within {max_attempts * 0.1}s\nSTDOUT: {stdout}\nSTDERR: {stderr}")
    
    try:
        yield proc, port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()