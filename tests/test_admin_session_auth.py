import requests

from conftest import custom_webquiz_server


def test_admin_auth_sets_session_cookie():
    """Test that admin authentication sets a session cookie."""
    with custom_webquiz_server() as (proc, port):
        response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )

        assert response.status_code == 200
        assert "admin_session" in response.cookies
        assert len(response.cookies["admin_session"]) > 0


def test_check_session_valid_cookie():
    """Test check-session endpoint with valid session cookie."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get a session cookie
        auth_response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )
        assert auth_response.status_code == 200

        # Use the session cookie to check session validity
        cookies = auth_response.cookies
        check_response = requests.get(f"http://localhost:{port}/api/admin/check-session", cookies=cookies)

        assert check_response.status_code == 200
        data = check_response.json()
        assert data["valid"] is True


def test_check_session_no_cookie():
    """Test check-session endpoint without session cookie."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/api/admin/check-session")

        assert response.status_code == 401
        data = response.json()
        assert data["valid"] is False


def test_check_session_invalid_cookie():
    """Test check-session endpoint with invalid session cookie."""
    with custom_webquiz_server() as (proc, port):
        cookies = {"admin_session": "invalid_session_token_12345"}
        response = requests.get(f"http://localhost:{port}/api/admin/check-session", cookies=cookies)

        assert response.status_code == 401
        data = response.json()
        assert data["valid"] is False


def test_admin_endpoint_with_session_cookie():
    """Test admin endpoint works with valid session cookie instead of master key."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get a session cookie
        auth_response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )
        assert auth_response.status_code == 200

        # Use the session cookie to access admin endpoint without master key header
        cookies = auth_response.cookies
        list_response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies)

        assert list_response.status_code == 200
        data = list_response.json()
        assert "quizzes" in data


def test_session_persists_across_requests():
    """Test that session persists across multiple requests."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get a session cookie
        auth_response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )
        assert auth_response.status_code == 200
        cookies = auth_response.cookies

        # Make multiple requests with the session cookie
        for _ in range(3):
            response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies)
            assert response.status_code == 200

        # Verify session is still valid
        check_response = requests.get(f"http://localhost:{port}/api/admin/check-session", cookies=cookies)
        assert check_response.status_code == 200


def test_multiple_sessions():
    """Test that multiple authentication creates separate sessions."""
    with custom_webquiz_server() as (proc, port):
        # Create first session
        auth1 = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )
        assert auth1.status_code == 200
        session1 = auth1.cookies["admin_session"]

        # Create second session
        auth2 = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )
        assert auth2.status_code == 200
        session2 = auth2.cookies["admin_session"]

        # Tokens should be different
        assert session1 != session2

        # Both sessions should be valid
        check1 = requests.get(
            f"http://localhost:{port}/api/admin/check-session",
            cookies={"admin_session": session1}
        )
        check2 = requests.get(
            f"http://localhost:{port}/api/admin/check-session",
            cookies={"admin_session": session2}
        )

        assert check1.status_code == 200
        assert check2.status_code == 200


def test_session_cookie_for_files_endpoint():
    """Test that session cookie works for files endpoint."""
    with custom_webquiz_server() as (proc, port):
        # First authenticate to get a session cookie
        auth_response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )
        assert auth_response.status_code == 200

        # Use the session cookie to access files endpoint
        cookies = auth_response.cookies
        files_response = requests.get(f"http://localhost:{port}/api/files/list", cookies=cookies)

        assert files_response.status_code == 200
        data = files_response.json()
        assert "quizzes" in data
