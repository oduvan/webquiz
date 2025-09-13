import subprocess
import time
import requests
import yaml
import pytest

from conftest import get_worker_port


def test_admin_auth_endpoint_with_valid_key(webquiz_server):
    """Test admin authentication with valid master key."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data['authenticated'] is True
    assert 'message' in data


def test_admin_auth_endpoint_without_key(webquiz_server):
    """Test admin authentication without master key."""
    _, port = webquiz_server
    response = requests.post(f'http://localhost:{port}/api/admin/auth')
    
    assert response.status_code == 401
    data = response.json()
    assert 'error' in data


def test_admin_auth_endpoint_with_invalid_key(webquiz_server):
    """Test admin authentication with invalid master key."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'wrong_key'}
    response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
    
    assert response.status_code == 401
    data = response.json()
    assert 'error' in data


def test_admin_list_quizzes_endpoint(webquiz_server):
    """Test listing available quizzes via admin API."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    response = requests.get(f'http://localhost:{port}/api/admin/list-quizzes', headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert 'quizzes' in data
    assert 'current_quiz' in data
    assert isinstance(data['quizzes'], list)
    assert len(data['quizzes']) > 0
    assert 'test_quiz.yaml' in data['quizzes']


def test_admin_list_quizzes_without_auth(webquiz_server):
    """Test listing quizzes without authentication."""
    _, port = webquiz_server
    response = requests.get(f'http://localhost:{port}/api/admin/list-quizzes')
    
    assert response.status_code == 401


def test_admin_switch_quiz_endpoint(webquiz_server):
    """Test switching quiz via admin API."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    
    # First get current quiz list
    list_response = requests.get(f'http://localhost:{port}/api/admin/list-quizzes', headers=headers)
    assert list_response.status_code == 200
    _ = list_response.json()['quizzes']
    
    # Switch to test_quiz.yaml
    switch_data = {'quiz_filename': 'test_quiz.yaml'}
    response = requests.post(f'http://localhost:{port}/api/admin/switch-quiz', 
                           headers=headers, 
                           json=switch_data)
    
    assert response.status_code == 200
    data = response.json()
    assert 'message' in data
    assert 'test_quiz.yaml' in data['message']


def test_admin_switch_quiz_nonexistent_file(webquiz_server):
    """Test switching to non-existent quiz file."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    switch_data = {'quiz_filename': 'nonexistent.yaml'}
    
    response = requests.post(f'http://localhost:{port}/api/admin/switch-quiz', 
                           headers=headers, 
                           json=switch_data)
    
    assert response.status_code == 400
    data = response.json()
    assert 'error' in data


def test_admin_switch_quiz_without_auth(webquiz_server):
    """Test switching quiz without authentication."""
    _, port = webquiz_server
    switch_data = {'quiz_filename': 'test_quiz.yaml'}
    
    response = requests.post(f'http://localhost:{port}/api/admin/switch-quiz', json=switch_data)
    
    assert response.status_code == 401


def test_admin_interface_webpage(webquiz_server):
    """Test accessing admin interface webpage."""
    _, port = webquiz_server
    response = requests.get(f'http://localhost:{port}/admin/')
    
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert 'admin' in response.text.lower()


def test_admin_endpoints_require_master_key_configuration(temp_dir):
    """Test that admin endpoints are protected when no master key is set."""
    port = get_worker_port() + 100  # Use different port to avoid conflict
    
    # Create config file without master key
    config_data = {
        'server': {
            'port': port
        }
    }
    
    with open('no_master_key_config.yaml', 'w') as f:
        yaml.dump(config_data, f)
    
    # Start server without master key
    cmd = ['python', '-m', 'webquiz.cli', '--config', 'no_master_key_config.yaml']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    time.sleep(3)
    
    try:
        # Try to access admin endpoints without any master key configured
        response = requests.post(f'http://localhost:{port}/api/admin/auth')
        assert response.status_code == 403  # Forbidden when no master key is configured
        
        response = requests.get(f'http://localhost:{port}/api/admin/list-quizzes')
        assert response.status_code == 403
        
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def test_admin_get_quiz_endpoint(webquiz_server):
    """Test getting quiz content via admin API."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    
    response = requests.get(f'http://localhost:{port}/api/admin/quiz/test_quiz.yaml', headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert 'content' in data
    
    # Parse the YAML content
    quiz_content = yaml.safe_load(data['content'])
    assert 'title' in quiz_content
    assert quiz_content['title'] == 'Test Quiz'


def test_admin_validate_quiz_endpoint(webquiz_server):
    """Test quiz validation via admin API."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    
    # Test valid quiz data
    valid_quiz = {
        'title': 'Valid Quiz',
        'description': 'A valid quiz',
        'questions': [
            {
                'question': 'What is 1 + 1?',
                'options': ['1', '2', '3'],
                'correct_answer': 1
            }
        ]
    }
    
    # Convert quiz data to YAML string
    quiz_yaml = yaml.dump(valid_quiz)
    
    response = requests.post(f'http://localhost:{port}/api/admin/validate-quiz',
                           headers=headers,
                           json={'content': quiz_yaml})
    
    assert response.status_code == 200
    data = response.json()
    assert data['valid'] is True
    assert 'parsed' in data
    assert 'question_count' in data


def test_admin_validate_invalid_quiz_endpoint(webquiz_server):
    """Test validation of invalid quiz data."""
    _, port = webquiz_server
    headers = {'X-Master-Key': 'test123'}
    
    # Test invalid quiz data (missing required fields)
    invalid_quiz = {
        'title': 'Invalid Quiz'
        # Missing questions
    }
    
    # Convert quiz data to YAML string
    invalid_quiz_yaml = yaml.dump(invalid_quiz)
    
    response = requests.post(f'http://localhost:{port}/api/admin/validate-quiz',
                           headers=headers,
                           json={'content': invalid_quiz_yaml})
    
    assert response.status_code == 200
    data = response.json()
    assert data['valid'] is False
    assert len(data['errors']) > 0


@pytest.mark.parametrize("endpoint_config", [
    ("POST", "/api/admin/auth", {}),
    ("GET", "/api/admin/list-quizzes", {}),
    ("POST", "/api/admin/switch-quiz", {"quiz_filename": "test_quiz.yaml"}),
    ("GET", "/api/admin/quiz/test_quiz.yaml", {}),
    ("POST", "/api/admin/create-quiz", {"title": "Test", "description": "Test", "questions": []}),
    ("PUT", "/api/admin/quiz/test_quiz.yaml", {"content": "title: Test"}),
    ("DELETE", "/api/admin/quiz/test_quiz.yaml", {}),
    ("POST", "/api/admin/validate-quiz", {"content": "title: Test"}),
    ("GET", "/api/admin/list-images", {}),
    ("POST", "/api/admin/download-quiz", {"url": "https://example.com/quiz.zip"})
])
def test_admin_endpoints_require_authentication(webquiz_server, endpoint_config):
    """Test that all admin endpoints require authentication and return 401 without master key."""
    _, port = webquiz_server
    method, endpoint, payload = endpoint_config
    
    url = f'http://localhost:{port}{endpoint}'
    
    if method == "GET":
        response = requests.get(url)
    elif method == "POST":
        response = requests.post(url, json=payload)
    elif method == "PUT":
        response = requests.put(url, json=payload)
    elif method == "DELETE":
        response = requests.delete(url)
    
    assert response.status_code == 401, f"Expected 401 for {method} {endpoint}, got {response.status_code}"


@pytest.mark.parametrize("endpoint_config", [
    ("POST", "/api/admin/auth", {}),
    ("GET", "/api/admin/list-quizzes", {}),
    ("POST", "/api/admin/switch-quiz", {"quiz_filename": "test_quiz.yaml"}),
    ("GET", "/api/admin/quiz/test_quiz.yaml", {}),
    ("POST", "/api/admin/create-quiz", {"title": "Test", "description": "Test", "questions": []}),
    ("PUT", "/api/admin/quiz/test_quiz.yaml", {"content": "title: Test"}),
    ("DELETE", "/api/admin/quiz/test_quiz.yaml", {}),
    ("POST", "/api/admin/validate-quiz", {"content": "title: Test"}),
    ("GET", "/api/admin/list-images", {}),
    ("POST", "/api/admin/download-quiz", {"url": "https://example.com/quiz.zip"})
])
def test_admin_endpoints_reject_invalid_authentication(webquiz_server, endpoint_config):
    """Test that all admin endpoints reject invalid master keys and return 401."""
    _, port = webquiz_server
    method, endpoint, payload = endpoint_config
    
    url = f'http://localhost:{port}{endpoint}'
    headers = {'X-Master-Key': 'invalid_key'}
    
    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, json=payload, headers=headers)
    elif method == "PUT":
        response = requests.put(url, json=payload, headers=headers)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    
    assert response.status_code == 401, f"Expected 401 for {method} {endpoint} with invalid key, got {response.status_code}"