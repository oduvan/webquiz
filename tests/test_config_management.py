import requests
import yaml

from conftest import custom_webquiz_server


def test_update_config_with_valid_data():
    """Test updating config with all sections valid."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Valid config with all sections
        config_content = """server:
  host: "0.0.0.0"
  port: 8080

paths:
  quizzes_dir: "quizzes"
  logs_dir: "logs"
  csv_dir: "data"
  static_dir: "static"

admin:
  master_key: "test123"
  trusted_ips:
    - "127.0.0.1"

options:
  flush_interval: 30

registration:
  fields:
    - "Grade"
    - "School"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'Restart server' in data['message']
        assert 'config_path' in data


def test_update_config_with_empty_content():
    """Test updating config with empty content (valid - uses defaults)."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': ''}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


def test_update_config_with_only_some_sections():
    """Test updating config with only some sections (others use defaults)."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Config with only server section
        config_content = """server:
  port: 9000
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


def test_reject_invalid_yaml_syntax():
    """Test rejecting invalid YAML syntax."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Invalid YAML - unclosed quote
        config_content = 'server:\n  host: "unclosed'

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'Invalid YAML syntax' in data['error']


def test_reject_invalid_port_out_of_range():
    """Test rejecting port numbers out of valid range."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Port too high
        config_content = """server:
  port: 70000
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'port' in str(data['errors']).lower()


def test_reject_invalid_port_type():
    """Test rejecting non-integer port."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Port as string
        config_content = """server:
  port: "8080"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'port' in str(data['errors']).lower()
        assert 'integer' in str(data['errors']).lower()


def test_reject_invalid_flush_interval_zero():
    """Test rejecting flush_interval of 0."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """options:
  flush_interval: 0
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'flush_interval' in str(data['errors']).lower()


def test_reject_invalid_flush_interval_type():
    """Test rejecting non-integer flush_interval."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """options:
  flush_interval: "30"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'flush_interval' in str(data['errors']).lower()
        assert 'integer' in str(data['errors']).lower()


def test_reject_server_section_as_list():
    """Test rejecting wrong type for server section (list instead of dict)."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """server:
  - host: "0.0.0.0"
  - port: 8080
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'server' in str(data['errors']).lower()
        assert 'dictionary' in str(data['errors']).lower()


def test_reject_invalid_trusted_ips_not_list():
    """Test rejecting trusted_ips that's not a list."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """admin:
  trusted_ips: "127.0.0.1"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'trusted_ips' in str(data['errors']).lower()
        assert 'list' in str(data['errors']).lower()


def test_reject_invalid_quizzes_missing_fields():
    """Test rejecting quizzes with missing required fields."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Quiz missing 'folder' field
        config_content = """quizzes:
  - name: "Test Quiz"
    download_path: "https://example.com/quiz.zip"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'folder' in str(data['errors']).lower()


def test_config_requires_authentication():
    """Test that config endpoint requires authentication."""
    with custom_webquiz_server() as (proc, port):
        # Try without authentication
        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            json={'content': 'server:\n  port: 8080'}
        )

        assert response.status_code == 401


def test_config_with_registration_fields():
    """Test config with registration fields."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """registration:
  fields:
    - "Grade"
    - "School"
    - "Teacher"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


def test_config_with_quizzes():
    """Test config with downloadable quizzes."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """quizzes:
  - name: "Math Quiz"
    download_path: "https://example.com/math.zip"
    folder: "math_questions/"
  - name: "Science Quiz"
    download_path: "https://example.com/science.zip"
    folder: "science/"
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


def test_reject_negative_port():
    """Test rejecting negative port number."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """server:
  port: -1
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'validation failed' in data['error'].lower()
        assert 'port' in str(data['errors']).lower()


def test_config_master_key_can_be_null():
    """Test that master_key can be null."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        config_content = """admin:
  master_key: null
"""

        response = requests.put(
            f'http://localhost:{port}/api/admin/config',
            headers=headers,
            json={'content': config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
