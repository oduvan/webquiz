import requests
import yaml

from conftest import custom_webquiz_server


def test_admin_auth_endpoint_with_valid_key():
    """Test admin authentication with valid master key."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert "message" in data


def test_admin_auth_endpoint_without_key():
    """Test admin authentication without master key."""
    with custom_webquiz_server() as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/admin/auth")

        assert response.status_code == 401
        data = response.json()
        assert "error" in data


def test_admin_auth_endpoint_with_invalid_key():
    """Test admin authentication with invalid master key."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "wrong_key"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)

        assert response.status_code == 401
        data = response.json()
        assert "error" in data


def test_admin_list_quizzes_endpoint():
    """Test listing available quizzes via admin API."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get session cookie
        headers = {"X-Master-Key": "test123"}
        auth_response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert auth_response.status_code == 200
        cookies = auth_response.cookies

        # Use session cookie to access admin endpoint
        response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies)

        assert response.status_code == 200
        data = response.json()
        assert "quizzes" in data
        assert "current_quiz" in data
        assert isinstance(data["quizzes"], list)
        assert len(data["quizzes"]) > 0
        assert "test_quiz.yaml" in data["quizzes"]


def test_admin_list_quizzes_without_auth():
    """Test listing quizzes without authentication."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes")

        assert response.status_code == 401


def test_admin_switch_quiz_endpoint():
    """Test switching quiz via admin API."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get session cookie
        headers = {"X-Master-Key": "test123"}
        auth_response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert auth_response.status_code == 200
        cookies = auth_response.cookies

        # First get current quiz list
        list_response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies)
        assert list_response.status_code == 200
        _ = list_response.json()["quizzes"]

        # Switch to test_quiz.yaml
        switch_data = {"quiz_filename": "test_quiz.yaml"}
        response = requests.post(f"http://localhost:{port}/api/admin/switch-quiz", cookies=cookies, json=switch_data)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "test_quiz.yaml" in data["message"]


def test_admin_switch_quiz_nonexistent_file():
    """Test switching to non-existent quiz file."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get session cookie
        headers = {"X-Master-Key": "test123"}
        auth_response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert auth_response.status_code == 200
        cookies = auth_response.cookies

        switch_data = {"quiz_filename": "nonexistent.yaml"}
        response = requests.post(f"http://localhost:{port}/api/admin/switch-quiz", cookies=cookies, json=switch_data)

        assert response.status_code == 500
        data = response.json()
        assert "error" in data


def test_admin_switch_quiz_without_auth():
    """Test switching quiz without authentication."""
    with custom_webquiz_server() as (proc, port):
        switch_data = {"quiz_filename": "test_quiz.yaml"}

        response = requests.post(f"http://localhost:{port}/api/admin/switch-quiz", json=switch_data)

        assert response.status_code == 401


def test_admin_interface_webpage():
    """Test accessing admin interface webpage."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/admin/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "admin" in response.text.lower()


def test_admin_endpoints_require_master_key_configuration():
    """Test that admin endpoints are protected when no master key is set."""
    # Configure server without master key
    config = {"admin": {"master_key": None}}  # Explicitly set no master key

    with custom_webquiz_server(config=config) as (proc, port):
        # Try to access admin endpoints without any master key configured
        response = requests.post(f"http://localhost:{port}/api/admin/auth")
        assert response.status_code == 403  # Forbidden when no master key is configured

        response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes")
        assert response.status_code == 403


def test_trusted_ip_bypass_authentication():
    """Test that trusted IPs can access admin endpoints without master key."""
    config = {"admin": {"trusted_ips": ["127.0.0.1"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Access admin auth from localhost (trusted IP) without providing master key
        auth_response = requests.post(f"http://localhost:{port}/api/admin/auth")
        assert auth_response.status_code == 200  # Should succeed without master key
        data = auth_response.json()
        assert data["authenticated"] is True
        cookies = auth_response.cookies

        # Test another admin endpoint with session cookie
        response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert "quizzes" in data


def test_non_trusted_ip_requires_authentication():
    """Test that non-trusted IPs still require master key authentication."""
    config = {"admin": {"trusted_ips": ["192.168.1.100"]}}  # Different IP, not localhost

    with custom_webquiz_server(config=config) as (proc, port):
        # Access from localhost (which is NOT in trusted list) should require auth
        response = requests.post(f"http://localhost:{port}/api/admin/auth")
        assert response.status_code == 401  # Should fail without master key

        # But should work with master key
        headers = {"X-Master-Key": "test123"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True


def test_trusted_ip_with_proxy_headers():
    """Test IP detection through proxy headers."""
    config = {"admin": {"trusted_ips": ["192.168.1.50", "10.0.0.100"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Test X-Forwarded-For header with trusted IP
        headers = {"X-Forwarded-For": "192.168.1.50, 192.168.1.1"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 200  # Should succeed due to trusted forwarded IP

        # Test X-Real-IP header with trusted IP
        headers = {"X-Real-IP": "10.0.0.100"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 200  # Should succeed due to trusted real IP

        # Test with non-trusted forwarded IP
        headers = {"X-Forwarded-For": "192.168.1.200"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 401  # Should fail - not trusted


def test_multiple_trusted_ips_configuration():
    """Test configuration with multiple trusted IPs."""
    config = {"admin": {"trusted_ips": ["127.0.0.1", "192.168.1.10", "10.0.0.5"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Test localhost (trusted)
        response = requests.post(f"http://localhost:{port}/api/admin/auth")
        assert response.status_code == 200

        # Test simulated trusted IPs via headers
        headers = {"X-Forwarded-For": "192.168.1.10"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 200

        headers = {"X-Real-IP": "10.0.0.5"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 200

        # Test non-trusted IP
        headers = {"X-Forwarded-For": "192.168.1.99"}
        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 401  # Should fail
