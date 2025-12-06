import requests
import yaml

from conftest import custom_webquiz_server, get_admin_session


def test_update_config_with_valid_data():
    """Test updating config with all sections valid."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

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
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # This test explicitly sets paths to different values than the test server
        # so restart is correctly required for those paths
        assert "restart required" in data["message"].lower() or "saved and applied" in data["message"]
        assert "config_path" in data


def test_update_config_with_empty_content():
    """Test updating config with empty content (valid - uses defaults)."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        response = requests.put(f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": ""})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_update_config_with_only_some_sections():
    """Test updating config with only some sections (others use defaults)."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Config with only server section
        config_content = """server:
  port: 9000
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_reject_invalid_yaml_syntax():
    """Test rejecting invalid YAML syntax."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Invalid YAML - unclosed quote
        config_content = 'server:\n  host: "unclosed'

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid YAML syntax" in data["error"]


def test_reject_invalid_port_out_of_range():
    """Test rejecting port numbers out of valid range."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Port too high
        config_content = """server:
  port: 70000
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert "port" in str(data["errors"]).lower()


def test_reject_invalid_port_type():
    """Test rejecting non-integer port."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Port as string
        config_content = """server:
  port: "8080"
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert "port" in str(data["errors"]).lower()
        assert "integer" in str(data["errors"]).lower()


def test_reject_server_section_as_list():
    """Test rejecting wrong type for server section (list instead of dict)."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        config_content = """server:
  - host: "0.0.0.0"
  - port: 8080
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert "server" in str(data["errors"]).lower()
        assert "dictionary" in str(data["errors"]).lower()


def test_reject_invalid_trusted_ips_not_list():
    """Test rejecting trusted_ips that's not a list."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        config_content = """admin:
  trusted_ips: "127.0.0.1"
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert "trusted_ips" in str(data["errors"]).lower()
        assert "list" in str(data["errors"]).lower()


def test_reject_invalid_quizzes_missing_fields():
    """Test rejecting quizzes with missing required fields."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Quiz missing 'folder' field
        config_content = """quizzes:
  - name: "Test Quiz"
    download_path: "https://example.com/quiz.zip"
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert "folder" in str(data["errors"]).lower()


def test_config_requires_authentication():
    """Test that config endpoint requires authentication."""
    with custom_webquiz_server() as (proc, port):
        # Try without authentication
        response = requests.put(f"http://localhost:{port}/api/admin/config", json={"content": "server:\n  port: 8080"})

        assert response.status_code == 401


def test_config_with_registration_fields():
    """Test config with registration fields."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        config_content = """registration:
  fields:
    - "Grade"
    - "School"
    - "Teacher"
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_config_with_quizzes():
    """Test config with downloadable quizzes."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        config_content = """quizzes:
  - name: "Math Quiz"
    download_path: "https://example.com/math.zip"
    folder: "math_questions/"
  - name: "Science Quiz"
    download_path: "https://example.com/science.zip"
    folder: "science/"
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_reject_negative_port():
    """Test rejecting negative port number."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        config_content = """server:
  port: -1
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert "port" in str(data["errors"]).lower()


def test_config_master_key_can_be_null():
    """Test that master_key can be null."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        config_content = """admin:
  master_key: null
"""

        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_config_registration_fields_saved_to_file():
    """Test that registration fields are actually written to the config file.

    This is a comprehensive test that verifies:
    1. The API accepts the config with registration fields
    2. The file is actually written with the correct content
    3. The /files/ page returns the saved content correctly
    """
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Config with registration fields
        config_content = """registration:
  fields:
    - "Grade"
    - "School"
    - "Teacher"
  approve: true
  username_label: "Student Name"
"""

        # Save the config
        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": config_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        config_path = data["config_path"]

        # Read the file directly to verify content was saved
        with open(config_path, "r", encoding="utf-8") as f:
            saved_content = f.read()

        # Verify the fields are in the saved file
        assert "fields:" in saved_content
        assert '"Grade"' in saved_content or "Grade" in saved_content
        assert '"School"' in saved_content or "School" in saved_content
        assert '"Teacher"' in saved_content or "Teacher" in saved_content
        assert "approve: true" in saved_content
        assert "Student Name" in saved_content

        # Parse the saved YAML to verify structure
        saved_yaml = yaml.safe_load(saved_content)
        assert "registration" in saved_yaml
        assert saved_yaml["registration"]["fields"] == ["Grade", "School", "Teacher"]
        assert saved_yaml["registration"]["approve"] is True
        assert saved_yaml["registration"]["username_label"] == "Student Name"


def test_config_registration_fields_reload_from_files_page():
    """Test that saved registration fields are shown correctly on /files/ page reload."""
    import re
    import json

    with custom_webquiz_server() as (proc, port):
        session = requests.Session()
        auth_response = session.post(f"http://localhost:{port}/api/admin/auth", json={"master_key": "test123"})
        assert auth_response.status_code == 200

        # Save config with registration fields
        config_content = """registration:
  fields:
    - "Grade"
    - "School"
"""
        response = session.put(f"http://localhost:{port}/api/admin/config", json={"content": config_content})
        assert response.status_code == 200

        # Load /files/ page and extract CONFIG_CONTENT
        files_response = session.get(f"http://localhost:{port}/files/")
        assert files_response.status_code == 200
        html = files_response.text

        # Extract CONFIG_CONTENT from JavaScript in the page
        match = re.search(r"const CONFIG_CONTENT = (.*?);", html)
        assert match is not None, "CONFIG_CONTENT not found in /files/ page"

        config_content_js = match.group(1)
        config_content_from_page = json.loads(config_content_js)

        # Verify the fields are in the content returned by the page
        assert "fields:" in config_content_from_page
        assert "Grade" in config_content_from_page
        assert "School" in config_content_from_page
