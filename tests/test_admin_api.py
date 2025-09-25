import subprocess
import time
import requests
import yaml

from conftest import get_worker_port, custom_webquiz_server


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


def test_trusted_ip_bypass_authentication(temp_dir):
    """Test that trusted IPs can access admin endpoints without master key."""
    config = {
        'admin': {
            'trusted_ips': ['127.0.0.1']
        }
    }

    with custom_webquiz_server(config=config) as (proc, port):
        # Access admin endpoint from localhost (trusted IP) without providing master key
        response = requests.post(f'http://localhost:{port}/api/admin/auth')
        assert response.status_code == 200  # Should succeed without master key
        data = response.json()
        assert data['authenticated'] is True

        # Test another admin endpoint
        response = requests.get(f'http://localhost:{port}/api/admin/list-quizzes')
        assert response.status_code == 200  # Should also succeed without master key
        data = response.json()
        assert 'quizzes' in data


def test_non_trusted_ip_requires_authentication(temp_dir):
    """Test that non-trusted IPs still require master key authentication."""
    config = {
        'admin': {
            'trusted_ips': ['192.168.1.100']  # Different IP, not localhost
        }
    }

    with custom_webquiz_server(config=config) as (proc, port):
        # Access from localhost (which is NOT in trusted list) should require auth
        response = requests.post(f'http://localhost:{port}/api/admin/auth')
        assert response.status_code == 401  # Should fail without master key

        # But should work with master key
        headers = {'X-Master-Key': 'test123'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data['authenticated'] is True


def test_trusted_ip_with_proxy_headers(temp_dir):
    """Test IP detection through proxy headers."""
    config = {
        'admin': {
            'trusted_ips': ['192.168.1.50', '10.0.0.100']
        }
    }

    with custom_webquiz_server(config=config) as (proc, port):
        # Test X-Forwarded-For header with trusted IP
        headers = {'X-Forwarded-For': '192.168.1.50, 192.168.1.1'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 200  # Should succeed due to trusted forwarded IP

        # Test X-Real-IP header with trusted IP
        headers = {'X-Real-IP': '10.0.0.100'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 200  # Should succeed due to trusted real IP

        # Test with non-trusted forwarded IP
        headers = {'X-Forwarded-For': '192.168.1.200'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 401  # Should fail - not trusted


def test_multiple_trusted_ips_configuration(temp_dir):
    """Test configuration with multiple trusted IPs."""
    config = {
        'admin': {
            'trusted_ips': ['127.0.0.1', '192.168.1.10', '10.0.0.5']
        }
    }

    with custom_webquiz_server(config=config) as (proc, port):
        # Test localhost (trusted)
        response = requests.post(f'http://localhost:{port}/api/admin/auth')
        assert response.status_code == 200

        # Test simulated trusted IPs via headers
        headers = {'X-Forwarded-For': '192.168.1.10'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 200

        headers = {'X-Real-IP': '10.0.0.5'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 200

        # Test non-trusted IP
        headers = {'X-Forwarded-For': '192.168.1.99'}
        response = requests.post(f'http://localhost:{port}/api/admin/auth', headers=headers)
        assert response.status_code == 401  # Should fail