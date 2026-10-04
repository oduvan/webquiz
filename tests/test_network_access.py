"""Tests for local network access control.

Tests that admin and live-stats pages are restricted to local/private networks only.
"""

import requests
import pytest
from types import SimpleNamespace

from conftest import custom_webquiz_server
from webquiz.server import get_client_ip


def make_request(remote, headers=None):
    """Minimal stand-in for an aiohttp request (only what get_client_ip reads)."""
    return SimpleNamespace(remote=remote, headers=headers or {})


def test_client_ip_uses_last_forwarded_entry_from_loopback():
    """Behind a local proxy or the SSH tunnel the proxy appends the real IP last."""
    request = make_request("127.0.0.1", {"X-Forwarded-For": "127.0.0.1, 8.8.8.8"})
    assert get_client_ip(request) == "8.8.8.8"


def test_client_ip_prefers_forwarded_for_over_real_ip():
    request = make_request("127.0.0.1", {"X-Forwarded-For": "8.8.8.8", "X-Real-IP": "192.168.1.5"})
    assert get_client_ip(request) == "8.8.8.8"


def test_client_ip_uses_real_ip_from_loopback():
    request = make_request("127.0.0.1", {"X-Real-IP": " 8.8.4.4 "})
    assert get_client_ip(request) == "8.8.4.4"


def test_client_ip_ignores_headers_from_network_clients():
    """A client on the LAN connects directly, so its headers cannot be trusted."""
    request = make_request("192.168.1.20", {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"})
    assert get_client_ip(request) == "192.168.1.20"


def test_client_ip_without_headers():
    assert get_client_ip(make_request("127.0.0.1")) == "127.0.0.1"
    assert get_client_ip(make_request(None)) == "127.0.0.1"
    assert get_client_ip(make_request("127.0.0.1", {"X-Forwarded-For": " , "})) == "127.0.0.1"


def test_spoofed_localhost_through_tunnel_is_blocked():
    """Tunnel traffic arrives from 127.0.0.1 with nginx headers.

    nginx appends the real address to X-Forwarded-For, so a visitor who sends
    "X-Forwarded-For: 127.0.0.1" must not be treated as the trusted localhost.
    """
    config = {"admin": {"trusted_ips": ["127.0.0.1"]}}
    with custom_webquiz_server(config=config) as (proc, port):
        headers = {"X-Forwarded-For": "127.0.0.1, 8.8.8.8", "X-Real-IP": "8.8.8.8"}

        response = requests.get(f"http://localhost:{port}/api/files/list", headers=headers)
        assert response.status_code == 403

        response = requests.post(f"http://localhost:{port}/api/admin/auth", headers=headers)
        assert response.status_code == 403

        # The real localhost (no proxy headers) is still trusted
        response = requests.get(f"http://localhost:{port}/api/files/list")
        assert response.status_code == 200


def test_admin_page_from_local_ip():
    """Test admin page access from local IP (127.0.0.1)."""
    with custom_webquiz_server() as (proc, port):
        # Direct access from localhost (no X-Forwarded-For header)
        response = requests.get(f"http://localhost:{port}/admin/")

        # Should allow access from localhost
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")


def test_admin_page_from_private_ip():
    """Test admin page access from private network IP."""
    with custom_webquiz_server() as (proc, port):
        # Simulate request from private network via X-Forwarded-For
        headers = {"X-Forwarded-For": "192.168.1.100"}
        response = requests.get(f"http://localhost:{port}/admin/", headers=headers)

        # Should allow access from private IP
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")


def test_admin_page_from_public_ip():
    """Test admin page access from public IP (should be blocked)."""
    with custom_webquiz_server() as (proc, port):
        # Simulate request from public IP via X-Forwarded-For
        headers = {"X-Forwarded-For": "8.8.8.8"}
        response = requests.get(f"http://localhost:{port}/admin/", headers=headers)

        # Should deny access from public IP
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "локальної мережі" in data["error"]


def test_live_stats_page_from_local_ip():
    """Test live stats page access from local IP."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/live-stats/")

        # Should allow access from localhost
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")


def test_live_stats_page_from_public_ip():
    """Test live stats page access from public IP (should be blocked)."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Forwarded-For": "1.1.1.1"}
        response = requests.get(f"http://localhost:{port}/live-stats/", headers=headers)

        # Should deny access from public IP
        assert response.status_code == 403
        data = response.json()
        assert "error" in data


def test_files_page_from_local_ip():
    """Test files page access from local IP."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/files/")

        # Should allow access from localhost
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")


def test_files_page_from_public_ip():
    """Test files page access from public IP (should be blocked)."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Forwarded-For": "93.184.216.34"}
        response = requests.get(f"http://localhost:{port}/files/", headers=headers)

        # Should deny access from public IP
        assert response.status_code == 403
        data = response.json()
        assert "error" in data


def test_multiple_private_ip_ranges():
    """Test access from different private IP ranges."""
    with custom_webquiz_server() as (proc, port):
        # Test various private IP ranges
        private_ips = [
            "127.0.0.1",  # Localhost
            "10.0.0.1",  # Class A private
            "172.16.0.1",  # Class B private
            "172.31.255.254",  # Class B private (edge)
            "192.168.0.1",  # Class C private
            "192.168.255.254",  # Class C private (edge)
        ]

        for ip in private_ips:
            headers = {"X-Forwarded-For": ip}
            response = requests.get(f"http://localhost:{port}/admin/", headers=headers)
            assert response.status_code == 200, f"Access denied for private IP {ip}"


def test_multiple_public_ip_addresses():
    """Test that various public IPs are blocked."""
    with custom_webquiz_server() as (proc, port):
        # Test various public IP addresses
        public_ips = [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "93.184.216.34",  # Example.com
            "151.101.1.195",  # Fastly CDN
        ]

        for ip in public_ips:
            headers = {"X-Forwarded-For": ip}
            response = requests.get(f"http://localhost:{port}/admin/", headers=headers)
            assert response.status_code == 403, f"Access allowed for public IP {ip}"


def test_x_real_ip_header():
    """Test that X-Real-IP header is also respected."""
    with custom_webquiz_server() as (proc, port):
        # Test with public IP in X-Real-IP
        headers = {"X-Real-IP": "8.8.8.8"}
        response = requests.get(f"http://localhost:{port}/admin/", headers=headers)

        # Should deny access
        assert response.status_code == 403

        # Test with private IP in X-Real-IP
        headers = {"X-Real-IP": "192.168.1.1"}
        response = requests.get(f"http://localhost:{port}/admin/", headers=headers)

        # Should allow access
        assert response.status_code == 200


def test_invalid_ip_format():
    """Test that invalid IP addresses are rejected."""
    with custom_webquiz_server() as (proc, port):
        # Test with invalid IP format
        headers = {"X-Forwarded-For": "not-an-ip"}
        response = requests.get(f"http://localhost:{port}/admin/", headers=headers)

        # Should deny access for invalid IP
        assert response.status_code == 403
        data = response.json()
        assert "error" in data


def test_quiz_page_not_restricted():
    """Test that the main quiz page is NOT restricted (public access)."""
    with custom_webquiz_server() as (proc, port):
        # Test from public IP - quiz page should still be accessible
        headers = {"X-Forwarded-For": "8.8.8.8"}
        response = requests.get(f"http://localhost:{port}/", headers=headers)

        # Quiz page should be accessible from anywhere
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")


def test_admin_api_from_local_ip():
    """Test admin API access from local IP."""
    with custom_webquiz_server() as (proc, port):
        response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            json={"master_key": "test123"}
        )

        # Should allow access from localhost
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True


def test_admin_api_from_public_ip():
    """Test admin API access from public IP (should be blocked)."""
    with custom_webquiz_server() as (proc, port):
        # Even with valid key in body, should be blocked by network check
        headers = {"X-Forwarded-For": "8.8.8.8"}
        response = requests.post(
            f"http://localhost:{port}/api/admin/auth",
            headers=headers,
            json={"master_key": "test123"}
        )

        # Should deny access from public IP (network restriction comes before auth)
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "локальної мережі" in data["error"]


def test_admin_list_quizzes_from_public_ip():
    """Test admin list quizzes API from public IP (should be blocked)."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Forwarded-For": "1.1.1.1"}
        response = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", headers=headers)

        # Should deny access from public IP
        assert response.status_code == 403
        data = response.json()
        assert "error" in data


def test_admin_approve_user_from_public_ip():
    """Test admin approve user API from public IP (should be blocked)."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Forwarded-For": "93.184.216.34"}
        response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", headers=headers, json={"user_id": "123456"}
        )

        # Should deny access from public IP
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
