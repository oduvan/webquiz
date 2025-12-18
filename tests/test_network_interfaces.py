"""Tests for get_network_interfaces function.

Tests that local/loopback addresses are filtered from the URL list.
"""

import pytest
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webquiz.server import get_network_interfaces, is_loopback_address


class TestIsLoopbackAddress:
    """Tests for is_loopback_address helper function."""

    def test_ipv4_localhost(self):
        """Test that 127.0.0.1 is identified as loopback."""
        assert is_loopback_address("127.0.0.1") is True

    def test_ipv4_loopback_range(self):
        """Test various 127.x.x.x addresses are identified as loopback."""
        assert is_loopback_address("127.0.0.2") is True
        assert is_loopback_address("127.0.1.1") is True
        assert is_loopback_address("127.255.255.255") is True

    def test_ipv6_loopback(self):
        """Test that IPv6 loopback (::1) is identified as loopback."""
        assert is_loopback_address("::1") is True

    def test_private_ip_not_loopback(self):
        """Test that private IPs are NOT loopback addresses."""
        assert is_loopback_address("192.168.1.1") is False
        assert is_loopback_address("10.0.0.1") is False
        assert is_loopback_address("172.16.0.1") is False

    def test_public_ip_not_loopback(self):
        """Test that public IPs are NOT loopback addresses."""
        assert is_loopback_address("8.8.8.8") is False
        assert is_loopback_address("1.1.1.1") is False

    def test_invalid_ip(self):
        """Test that invalid IPs return True (treated as loopback to be safe)."""
        assert is_loopback_address("not-an-ip") is True
        assert is_loopback_address("") is True


class TestGetNetworkInterfaces:
    """Tests for get_network_interfaces function."""

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    def test_filters_localhost(self, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that 127.0.0.1 is filtered from results."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("127.0.0.1", 0)),
            (None, None, None, None, ("192.168.1.100", 0)),
        ]
        mock_system.return_value = "Windows"  # Skip hostname -I call

        interfaces = get_network_interfaces()

        assert "127.0.0.1" not in interfaces
        assert "192.168.1.100" in interfaces

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    def test_filters_loopback_range(self, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that entire 127.x.x.x range is filtered."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("127.0.0.2", 0)),
            (None, None, None, None, ("127.0.1.1", 0)),
            (None, None, None, None, ("10.0.0.5", 0)),
        ]
        mock_system.return_value = "Windows"

        interfaces = get_network_interfaces()

        assert "127.0.0.2" not in interfaces
        assert "127.0.1.1" not in interfaces
        assert "10.0.0.5" in interfaces

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    @patch("webquiz.server.subprocess.run")
    def test_filters_loopback_from_hostname_command(self, mock_run, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that loopback addresses from hostname -I are also filtered."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = []
        mock_system.return_value = "Linux"

        # Simulate hostname -I returning both loopback and real IPs
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "127.0.0.1 192.168.1.50 10.0.0.10"
        mock_run.return_value = mock_result

        interfaces = get_network_interfaces()

        assert "127.0.0.1" not in interfaces
        assert "192.168.1.50" in interfaces
        assert "10.0.0.10" in interfaces

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    def test_empty_when_only_loopback(self, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that result is empty when only loopback addresses exist."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("127.0.0.1", 0)),
        ]
        mock_system.return_value = "Windows"

        interfaces = get_network_interfaces()

        assert interfaces == []

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    @patch("webquiz.server.subprocess.run")
    def test_filters_ipv6_by_default(self, mock_run, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that IPv6 addresses are filtered out by default."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("192.168.1.100", 0)),
        ]
        mock_system.return_value = "Linux"

        # Simulate hostname -I returning both IPv4 and IPv6 addresses
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "192.168.1.100 fe80::1 2001:db8::1"
        mock_run.return_value = mock_result

        interfaces = get_network_interfaces()

        assert "192.168.1.100" in interfaces
        assert "fe80::1" not in interfaces
        assert "2001:db8::1" not in interfaces

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    @patch("webquiz.server.subprocess.run")
    def test_includes_ipv6_when_enabled(self, mock_run, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that IPv6 addresses are included when include_ipv6=True."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("192.168.1.100", 0)),
        ]
        mock_system.return_value = "Linux"

        # Simulate hostname -I returning both IPv4 and IPv6 addresses
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "192.168.1.100 fe80::1 2001:db8::1"
        mock_run.return_value = mock_result

        interfaces = get_network_interfaces(include_ipv6=True)

        assert "192.168.1.100" in interfaces
        assert "fe80::1" in interfaces
        assert "2001:db8::1" in interfaces

    @patch("webquiz.server.socket.gethostname")
    @patch("webquiz.server.socket.getaddrinfo")
    @patch("webquiz.server.platform.system")
    @patch("webquiz.server.subprocess.run")
    def test_filters_ipv6_explicitly_disabled(self, mock_run, mock_system, mock_getaddrinfo, mock_gethostname):
        """Test that IPv6 addresses are filtered when include_ipv6=False."""
        mock_gethostname.return_value = "testhost"
        mock_getaddrinfo.return_value = []
        mock_system.return_value = "Linux"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "10.0.0.5 fe80::abc:def"
        mock_run.return_value = mock_result

        interfaces = get_network_interfaces(include_ipv6=False)

        assert "10.0.0.5" in interfaces
        assert "fe80::abc:def" not in interfaces


class TestUrlFormat:
    """Tests for URL format configuration."""

    def test_default_url_format(self):
        """Test that default URL format produces correct URLs."""
        from webquiz.config import ServerConfig

        config = ServerConfig()
        assert config.url_format == "http://{IP}:{PORT}/"

        # Test URL generation
        ip = "192.168.1.100"
        port = 8080
        url = config.url_format.replace("{IP}", ip).replace("{PORT}", str(port))
        assert url == "http://192.168.1.100:8080/"

    def test_custom_url_format_without_port(self):
        """Test custom URL format without port placeholder (for reverse proxy)."""
        from webquiz.config import ServerConfig

        config = ServerConfig(url_format="http://{IP}/webquiz/")

        ip = "192.168.1.100"
        port = 8080
        url = config.url_format.replace("{IP}", ip).replace("{PORT}", str(port))
        assert url == "http://192.168.1.100/webquiz/"

    def test_custom_url_format_with_https(self):
        """Test custom URL format with HTTPS."""
        from webquiz.config import ServerConfig

        config = ServerConfig(url_format="https://{IP}:{PORT}/quiz/")

        ip = "10.0.0.5"
        port = 443
        url = config.url_format.replace("{IP}", ip).replace("{PORT}", str(port))
        assert url == "https://10.0.0.5:443/quiz/"

    def test_url_format_preserves_placeholders_case(self):
        """Test that lowercase placeholders are not replaced."""
        from webquiz.config import ServerConfig

        config = ServerConfig(url_format="http://{ip}:{port}/")

        ip = "192.168.1.100"
        port = 8080
        url = config.url_format.replace("{IP}", ip).replace("{PORT}", str(port))
        # Lowercase placeholders should NOT be replaced
        assert url == "http://{ip}:{port}/"


class TestPort80Normalization:
    """Tests for port 80 URL normalization in admin page."""

    def test_admin_page_urls_include_port_for_non_80(self):
        """Test that admin page URLs include port number for non-80 ports."""
        import requests
        import re
        from conftest import custom_webquiz_server

        with custom_webquiz_server() as (proc, port):
            # Fetch admin page
            response = requests.get(f"http://localhost:{port}/admin/")
            assert response.status_code == 200

            # Extract NETWORK_INFO from HTML
            html = response.text
            match = re.search(r"const NETWORK_INFO = ({.*?});", html, re.DOTALL)
            assert match, "NETWORK_INFO not found in admin page"

            network_info = match.group(1)
            # Verify port is included in URLs (for non-80 ports)
            assert f":{port}/" in network_info, f"Port {port} should be in URL"

    def test_normalize_url_removes_port_80(self):
        """Test that normalize_url helper removes :80 from URLs."""
        from webquiz.server import normalize_url

        assert normalize_url("http://192.168.1.100:80/") == "http://192.168.1.100/"
        assert normalize_url("http://10.0.0.5:80/quiz/") == "http://10.0.0.5/quiz/"

    def test_normalize_url_preserves_other_ports(self):
        """Test that normalize_url preserves non-80 ports."""
        from webquiz.server import normalize_url

        assert normalize_url("http://192.168.1.100:8080/") == "http://192.168.1.100:8080/"
        assert normalize_url("http://10.0.0.5:3000/") == "http://10.0.0.5:3000/"
        assert normalize_url("http://10.0.0.5:81/") == "http://10.0.0.5:81/"

    def test_normalize_url_does_not_affect_8080(self):
        """Test that :8080 in URL is not affected by :80 replacement."""
        from webquiz.server import normalize_url

        # :8080 should not be touched because we replace ":80/" not ":80"
        assert normalize_url("http://192.168.1.100:8080/") == "http://192.168.1.100:8080/"
        assert normalize_url("http://192.168.1.100:800/") == "http://192.168.1.100:800/"
