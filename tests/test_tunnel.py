"""
Tests for SSH tunnel functionality.

These tests ensure that tunnel configuration, key management, and connection
logic work correctly.
"""

import asyncio
import json
import os
import tempfile
import yaml
import asyncssh
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from webquiz.config import (
    load_config_from_yaml,
    TunnelConfig,
    TunnelServerConfig,
    WebQuizConfig,
)
from webquiz.tunnel import TunnelManager


def test_tunnel_config_defaults():
    """Test that TunnelConfig has proper defaults."""
    tunnel = TunnelConfig()
    assert tunnel.server is None
    assert tunnel.public_key is None
    assert tunnel.private_key is None


def test_tunnel_config_with_values():
    """Test TunnelConfig with provided values."""
    tunnel = TunnelConfig(server="example.com", public_key="/path/to/public", private_key="/path/to/private")
    assert tunnel.server == "example.com"
    assert tunnel.public_key == "/path/to/public"
    assert tunnel.private_key == "/path/to/private"


def test_tunnel_config_with_socket_name():
    """Test TunnelConfig with custom socket_name."""
    tunnel = TunnelConfig(
        server="example.com",
        public_key="/path/to/public",
        private_key="/path/to/private",
        socket_name="my-custom-socket",
    )
    assert tunnel.server == "example.com"
    assert tunnel.socket_name == "my-custom-socket"


def test_tunnel_config_path_resolution():
    """Test that TunnelConfig resolves relative paths when running as binary."""
    # Set WEBQUIZ_BINARY_DIR
    old_value = os.environ.get("WEBQUIZ_BINARY_DIR")
    test_binary_dir = "/test/binary/dir"
    os.environ["WEBQUIZ_BINARY_DIR"] = test_binary_dir

    try:
        tunnel = TunnelConfig(server="example.com", public_key="keys/public.pub", private_key="keys/private")
        assert tunnel.server == "example.com"
        assert tunnel.public_key == str(Path(test_binary_dir) / "keys/public.pub")
        assert tunnel.private_key == str(Path(test_binary_dir) / "keys/private")
    finally:
        # Restore environment
        if old_value is not None:
            os.environ["WEBQUIZ_BINARY_DIR"] = old_value
        else:
            del os.environ["WEBQUIZ_BINARY_DIR"]


def test_tunnel_config_absolute_paths_unchanged():
    """Test that absolute paths are not modified by TunnelConfig."""
    tunnel = TunnelConfig(
        server="example.com", public_key="/absolute/path/public.pub", private_key="/absolute/path/private"
    )
    assert tunnel.public_key == "/absolute/path/public.pub"
    assert tunnel.private_key == "/absolute/path/private"


def test_load_config_with_tunnel():
    """Test loading config with tunnel settings."""
    config_data = {
        "tunnel": {
            "server": "tunnel.example.com",
            "public_key": "keys/id_ed25519.pub",
            "private_key": "keys/id_ed25519",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.tunnel.server == "tunnel.example.com"
        assert config.tunnel.public_key == "keys/id_ed25519.pub"
        assert config.tunnel.private_key == "keys/id_ed25519"
    finally:
        os.unlink(config_path)


def test_load_config_with_tunnel_socket_name():
    """Test loading config with tunnel settings including socket_name."""
    config_data = {
        "tunnel": {
            "server": "tunnel.example.com",
            "public_key": "keys/id_ed25519.pub",
            "private_key": "keys/id_ed25519",
            "socket_name": "my-custom-socket",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.tunnel.server == "tunnel.example.com"
        assert config.tunnel.public_key == "keys/id_ed25519.pub"
        assert config.tunnel.private_key == "keys/id_ed25519"
        assert config.tunnel.socket_name == "my-custom-socket"
    finally:
        os.unlink(config_path)


def test_load_config_without_tunnel():
    """Test loading config without tunnel section uses defaults."""
    config_data = {"server": {"port": 8080}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.tunnel.server is None
        assert config.tunnel.public_key is None
        assert config.tunnel.private_key is None
    finally:
        os.unlink(config_path)


def test_load_config_with_nested_tunnel_config():
    """Test loading config with nested tunnel config subsection."""
    config_data = {
        "tunnel": {
            "server": "tunnel.example.com",
            "public_key": "keys/id_ed25519.pub",
            "private_key": "keys/id_ed25519",
            "config": {
                "username": "tunneluser",
                "socket_directory": "/var/run/tunnels",
                "base_url": "https://tunnel.example.com/tests",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.tunnel.server == "tunnel.example.com"
        assert config.tunnel.public_key == "keys/id_ed25519.pub"
        assert config.tunnel.private_key == "keys/id_ed25519"
        assert config.tunnel.config is not None
        assert config.tunnel.config.username == "tunneluser"
        assert config.tunnel.config.socket_directory == "/var/run/tunnels"
        assert config.tunnel.config.base_url == "https://tunnel.example.com/tests"
    finally:
        os.unlink(config_path)


def test_load_config_with_tunnel_no_nested_config():
    """Test loading config with tunnel but no nested config subsection."""
    config_data = {
        "tunnel": {
            "server": "tunnel.example.com",
            "public_key": "keys/id_ed25519.pub",
            "private_key": "keys/id_ed25519",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.tunnel.server == "tunnel.example.com"
        assert config.tunnel.config is None  # No nested config
    finally:
        os.unlink(config_path)


def test_tunnel_manager_initialization():
    """Test TunnelManager initializes with correct defaults."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config, local_port=8080)

    assert manager.config == config
    assert manager.local_port == 8080
    assert manager.connection is None
    assert manager.listener is None
    assert manager.socket_id is None
    assert manager.status["connected"] is False
    assert manager.status["url"] is None
    assert manager.status["keys_status"] == "unchecked"


@pytest.mark.asyncio
async def test_ensure_keys_not_configured():
    """Test ensure_keys_exist when paths are not configured."""
    config = TunnelConfig()  # No paths set
    manager = TunnelManager(config)

    success, message = await manager.ensure_keys_exist()

    assert success is False
    assert "not configured" in message.lower()
    assert manager.status["keys_status"] == "not_configured"


@pytest.mark.asyncio
async def test_ensure_keys_generate_new():
    """Test that new SSH keys are generated when they don't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_key_path = os.path.join(tmpdir, "id_ed25519.pub")
        private_key_path = os.path.join(tmpdir, "id_ed25519")

        config = TunnelConfig(server="example.com", public_key=public_key_path, private_key=private_key_path)
        manager = TunnelManager(config)

        # Keys should not exist yet
        assert not os.path.exists(public_key_path)
        assert not os.path.exists(private_key_path)

        success, message = await manager.ensure_keys_exist()

        # Keys should now exist
        assert success is True
        assert "generated" in message.lower()
        assert os.path.exists(public_key_path)
        assert os.path.exists(private_key_path)

        # Check permissions (private key should be 0o600)
        private_stat = os.stat(private_key_path)
        assert oct(private_stat.st_mode)[-3:] == "600"

        # Check key format
        with open(public_key_path, "r") as f:
            public_content = f.read()
            assert public_content.startswith("ssh-ed25519 ")
            assert "webquiz@tunnel" in public_content

        # Status should be updated
        assert manager.status["keys_status"] == "ok"
        assert manager.status["public_key_content"] is not None


@pytest.mark.asyncio
async def test_ensure_keys_both_exist():
    """Test ensure_keys_exist when both keys already exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_key_path = os.path.join(tmpdir, "id_ed25519.pub")
        private_key_path = os.path.join(tmpdir, "id_ed25519")

        config = TunnelConfig(server="example.com", public_key=public_key_path, private_key=private_key_path)
        manager = TunnelManager(config)

        # Generate keys first
        await manager.ensure_keys_exist()

        # Reset status
        manager.status["keys_status"] = "unchecked"

        # Check again - should validate existing keys
        success, message = await manager.ensure_keys_exist()

        assert success is True
        assert "validated" in message.lower()
        assert manager.status["keys_status"] == "ok"


@pytest.mark.asyncio
async def test_ensure_keys_only_public_exists():
    """Test error when only public key exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_key_path = os.path.join(tmpdir, "id_ed25519.pub")
        private_key_path = os.path.join(tmpdir, "id_ed25519")

        # Create only public key
        Path(public_key_path).write_text("fake public key")

        config = TunnelConfig(server="example.com", public_key=public_key_path, private_key=private_key_path)
        manager = TunnelManager(config)

        success, message = await manager.ensure_keys_exist()

        assert success is False
        assert "private key is missing" in message.lower()
        assert manager.status["keys_status"] == "partial"


@pytest.mark.asyncio
async def test_ensure_keys_only_private_exists():
    """Test error when only private key exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_key_path = os.path.join(tmpdir, "id_ed25519.pub")
        private_key_path = os.path.join(tmpdir, "id_ed25519")

        # Create only private key
        Path(private_key_path).write_text("fake private key")

        config = TunnelConfig(server="example.com", public_key=public_key_path, private_key=private_key_path)
        manager = TunnelManager(config)

        success, message = await manager.ensure_keys_exist()

        assert success is False
        assert "public key is missing" in message.lower()
        assert manager.status["keys_status"] == "partial"


@pytest.mark.asyncio
async def test_fetch_tunnel_config_no_server():
    """Test fetch_tunnel_config when server is not configured."""
    config = TunnelConfig()  # No server
    manager = TunnelManager(config)

    result = await manager.fetch_tunnel_config()

    assert result is None


@pytest.mark.asyncio
async def test_fetch_tunnel_config_success():
    """Test successful tunnel config fetch from domain (uses HTTPS)."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    tunnel_config_data = {
        "username": "tunneluser",
        "socket_directory": "/var/run/tunnels",
        "base_url": "https://example.com/tests",
    }

    # Mock httpx client
    with patch("webquiz.tunnel.httpx.AsyncClient") as mock_client_class:
        mock_response = Mock()
        mock_response.text = yaml.dump(tunnel_config_data)
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await manager.fetch_tunnel_config()

        assert result is not None
        assert result["username"] == "tunneluser"
        assert result["socket_directory"] == "/var/run/tunnels"
        assert result["base_url"] == "https://example.com/tests"

        # Verify HTTPS was used for domain name
        mock_client.get.assert_called_once_with("https://example.com/tunnel_config.yaml")


@pytest.mark.asyncio
async def test_fetch_tunnel_config_from_ip_address():
    """Test that IP address uses HTTP instead of HTTPS."""
    config = TunnelConfig(server="192.168.1.100")
    manager = TunnelManager(config)

    tunnel_config_data = {
        "username": "tunneluser",
        "socket_directory": "/var/run/tunnels",
        "base_url": "http://192.168.1.100/tests",
    }

    # Mock httpx client
    with patch("webquiz.tunnel.httpx.AsyncClient") as mock_client_class:
        mock_response = Mock()
        mock_response.text = yaml.dump(tunnel_config_data)
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await manager.fetch_tunnel_config()

        assert result is not None
        assert result["username"] == "tunneluser"
        assert result["socket_directory"] == "/var/run/tunnels"
        assert result["base_url"] == "http://192.168.1.100/tests"

        # Verify HTTP was used for IP address
        mock_client.get.assert_called_once_with("http://192.168.1.100/tunnel_config.yaml")


@pytest.mark.asyncio
async def test_fetch_tunnel_config_from_ipv6_address():
    """Test that IPv6 address uses HTTP instead of HTTPS."""
    config = TunnelConfig(server="2001:db8::1")
    manager = TunnelManager(config)

    tunnel_config_data = {
        "username": "tunneluser",
        "socket_directory": "/var/run/tunnels",
        "base_url": "http://[2001:db8::1]/tests",
    }

    # Mock httpx client
    with patch("webquiz.tunnel.httpx.AsyncClient") as mock_client_class:
        mock_response = Mock()
        mock_response.text = yaml.dump(tunnel_config_data)
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await manager.fetch_tunnel_config()

        assert result is not None

        # Verify HTTP was used for IPv6 address
        mock_client.get.assert_called_once_with("http://2001:db8::1/tunnel_config.yaml")


@pytest.mark.asyncio
async def test_fetch_tunnel_config_uses_local_config():
    """Test that local config is used instead of fetching from server."""
    from webquiz.config import TunnelServerConfig

    local_config = TunnelServerConfig(
        username="localuser", socket_directory="/local/sockets", base_url="https://local.example.com/app"
    )

    config = TunnelConfig(server="example.com", config=local_config)
    manager = TunnelManager(config)

    # Should use local config without making HTTP request
    result = await manager.fetch_tunnel_config()

    assert result is not None
    assert result["username"] == "localuser"
    assert result["socket_directory"] == "/local/sockets"
    assert result["base_url"] == "https://local.example.com/app"


@pytest.mark.asyncio
async def test_fetch_tunnel_config_missing_fields():
    """Test tunnel config fetch with missing required fields."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    # Incomplete config (missing socket_directory)
    tunnel_config_data = {
        "username": "tunneluser",
        "base_url": "https://example.com/tests",
    }

    with patch("webquiz.tunnel.httpx.AsyncClient") as mock_client_class:
        mock_response = Mock()
        mock_response.text = yaml.dump(tunnel_config_data)
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await manager.fetch_tunnel_config()

        assert result is None
        assert "socket_directory" in manager.status.get("error", "")


def test_generate_socket_id():
    """Test socket ID generation."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    socket_id = manager._generate_socket_id()

    # Should be 6-8 hex characters
    assert len(socket_id) in [6, 8]
    assert all(c in "0123456789abcdef" for c in socket_id)

    # Generate multiple to ensure randomness
    ids = set(manager._generate_socket_id() for _ in range(10))
    assert len(ids) > 1  # Should not all be the same


@pytest.mark.asyncio
async def test_connect_no_server():
    """Test connect when server is not configured."""
    config = TunnelConfig()  # No server
    manager = TunnelManager(config)

    success, message = await manager.connect()

    assert success is False
    assert "not configured" in message.lower()


@pytest.mark.asyncio
async def test_connect_success():
    """Test successful tunnel connection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_key_path = os.path.join(tmpdir, "id_ed25519.pub")
        private_key_path = os.path.join(tmpdir, "id_ed25519")

        config = TunnelConfig(server="example.com", public_key=public_key_path, private_key=private_key_path)
        manager = TunnelManager(config, local_port=8080)

        # Generate keys first
        await manager.ensure_keys_exist()

        # Mock tunnel config fetch
        tunnel_config_data = {
            "username": "tunneluser",
            "socket_directory": "/var/run/tunnels",
            "base_url": "https://example.com/tests",
        }

        # Mock SSH connection
        mock_connection = AsyncMock()
        mock_listener = AsyncMock()

        # Make forward method async and return the listener
        async def forward_mock(*_args, **_kwargs):
            return mock_listener

        mock_connection.forward_remote_path_to_port = forward_mock

        with (
            patch("webquiz.tunnel.httpx.AsyncClient") as mock_client_class,
            patch(
                "webquiz.tunnel.asyncssh.connect", new_callable=AsyncMock, return_value=mock_connection
            ) as mock_connect,
        ):

            # Setup HTTP client mock
            mock_response = Mock()
            mock_response.text = yaml.dump(tunnel_config_data)
            mock_response.raise_for_status = Mock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            success, result = await manager.connect()

            assert success is True
            assert result.startswith("https://example.com/tests/")
            assert manager.status["connected"] is True
            assert manager.status["url"] == result
            assert manager.socket_id is not None

            # Verify SSH connection was called correctly
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args.kwargs
            assert call_kwargs["username"] == "tunneluser"
            assert private_key_path in call_kwargs["client_keys"]


@pytest.mark.asyncio
async def test_connect_with_custom_socket_name():
    """Test successful tunnel connection with custom socket_name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_key_path = os.path.join(tmpdir, "id_ed25519.pub")
        private_key_path = os.path.join(tmpdir, "id_ed25519")

        config = TunnelConfig(
            server="example.com",
            public_key=public_key_path,
            private_key=private_key_path,
            socket_name="my-custom-socket",
        )
        manager = TunnelManager(config, local_port=8080)

        # Generate keys first
        await manager.ensure_keys_exist()

        # Mock tunnel config fetch
        tunnel_config_data = {
            "username": "tunneluser",
            "socket_directory": "/var/run/tunnels",
            "base_url": "https://example.com/tests",
        }

        # Mock SSH connection
        mock_connection = AsyncMock()
        mock_listener = AsyncMock()

        # Make forward method async and return the listener
        async def forward_mock(remote_socket, *_args, **_kwargs):
            # Verify custom socket name is used in remote socket path
            assert remote_socket == "/var/run/tunnels/my-custom-socket"
            return mock_listener

        mock_connection.forward_remote_path_to_port = forward_mock

        with (
            patch("webquiz.tunnel.httpx.AsyncClient") as mock_client_class,
            patch(
                "webquiz.tunnel.asyncssh.connect", new_callable=AsyncMock, return_value=mock_connection
            ) as mock_connect,
        ):

            # Setup HTTP client mock
            mock_response = Mock()
            mock_response.text = yaml.dump(tunnel_config_data)
            mock_response.raise_for_status = Mock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            success, result = await manager.connect()

            assert success is True
            assert result == "https://example.com/tests/my-custom-socket/"
            assert manager.status["connected"] is True
            assert manager.status["url"] == result
            assert manager.socket_id == "my-custom-socket"
            assert manager.base_url == "https://example.com/tests"
            assert manager.get_public_endpoint() == ("https://example.com/tests", "my-custom-socket")

            # Verify SSH connection was called correctly
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args.kwargs
            assert call_kwargs["username"] == "tunneluser"
            assert private_key_path in call_kwargs["client_keys"]


def test_public_endpoint_requires_connection():
    """The public endpoint is known only while the tunnel is connected."""
    manager = TunnelManager(TunnelConfig(server="example.com"))
    assert manager.get_public_endpoint() is None

    manager.socket_id = "abc123"
    manager.base_url = "https://example.com/tests"
    assert manager.get_public_endpoint() is None  # Connection lost: status is not connected

    manager.status["connected"] = True
    assert manager.get_public_endpoint() == ("https://example.com/tests", "abc123")


@pytest.mark.asyncio
async def test_disconnect():
    """Test tunnel disconnection."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    # Setup mock connection and listener with proper close/wait_closed
    mock_connection = Mock()
    mock_connection.close = Mock()
    mock_connection.wait_closed = AsyncMock()

    mock_listener = Mock()
    mock_listener.close = Mock()
    mock_listener.wait_closed = AsyncMock()

    manager.connection = mock_connection
    manager.listener = mock_listener
    manager.status["connected"] = True
    manager.status["url"] = "https://example.com/tests/abc123/"
    manager.socket_id = "abc123"
    manager.base_url = "https://example.com/tests"
    assert manager.get_public_endpoint() == ("https://example.com/tests", "abc123")

    await manager.disconnect()

    # Verify cleanup
    assert manager.connection is None
    assert manager.listener is None
    assert manager.status["connected"] is False
    assert manager.status["url"] is None
    assert manager.socket_id is None
    assert manager.base_url is None
    assert manager.get_public_endpoint() is None

    mock_listener.close.assert_called_once()
    mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_status_callback():
    """Test that status callback is called on status changes."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    callback_called = []

    async def status_callback(status):
        callback_called.append(status.copy())

    manager.set_status_callback(status_callback)

    # Trigger status change
    await manager._notify_status_change()

    assert len(callback_called) == 1
    assert callback_called[0]["connected"] is False


def test_get_status():
    """Test get_status returns status dict."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    status = manager.get_status()

    assert isinstance(status, dict)
    assert "connected" in status
    assert "url" in status
    assert "error" in status
    assert "keys_status" in status
    assert status["connected"] is False


@pytest.mark.asyncio
async def test_cleanup():
    """Test cleanup disconnects tunnel."""
    config = TunnelConfig(server="example.com")
    manager = TunnelManager(config)

    # Setup mock connection with proper close/wait_closed
    mock_connection = Mock()
    mock_connection.close = Mock()
    mock_connection.wait_closed = AsyncMock()

    mock_listener = Mock()
    mock_listener.close = Mock()
    mock_listener.wait_closed = AsyncMock()

    manager.connection = mock_connection
    manager.listener = mock_listener
    manager.status["connected"] = True

    await manager.cleanup()

    assert manager.connection is None
    assert manager.listener is None
    assert manager.status["connected"] is False


class FakeSSHConnection:
    """SSH connection whose remote Unix socket listener can be refused by the tunnel server"""

    def __init__(self, listen_error=False):
        self.listen_error = listen_error
        self.closed = asyncio.Event()
        self.forwarded = []

    async def forward_remote_path_to_port(self, remote_path, *_args):
        self.forwarded.append(remote_path)
        if self.listen_error:
            raise asyncssh.ChannelListenError("Failed to create remote UNIX listener")
        listener = Mock()
        listener.close = Mock()
        listener.wait_closed = AsyncMock()
        return listener

    def close(self):
        self.closed.set()

    async def wait_closed(self):
        await self.closed.wait()


async def make_tunnel_manager(tmpdir, socket_name="racoon"):
    """Tunnel manager with generated keys and local tunnel server config (no HTTP fetch)"""
    config = TunnelConfig(
        server="example.com",
        public_key=os.path.join(tmpdir, "id_ed25519.pub"),
        private_key=os.path.join(tmpdir, "id_ed25519"),
        socket_name=socket_name,
        config=TunnelServerConfig(
            username="tunneluser", socket_directory="/var/run/tunnels", base_url="https://example.com/start"
        ),
    )
    manager = TunnelManager(config, local_port=8080)
    await manager.ensure_keys_exist()
    manager._busy_retry_delay = 0
    return manager


async def wait_for_reconnect_task(manager):
    for _ in range(200):
        if manager._reconnect_task:
            return manager._reconnect_task
        await asyncio.sleep(0.01)
    raise AssertionError("Reconnect task was not started")


async def test_busy_socket_name_is_retried_until_free():
    """A fixed socket name still held on the tunnel server is retried in the background."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = await make_tunnel_manager(tmpdir)
        statuses = []

        async def status_callback(status):
            statuses.append(status)

        manager.set_status_callback(status_callback)
        busy = FakeSSHConnection(listen_error=True)
        free = FakeSSHConnection()

        with patch("webquiz.tunnel.asyncssh.connect", new_callable=AsyncMock, side_effect=[busy, free]):
            success, message = await manager.connect()

            assert success is False
            assert "racoon" in message
            assert "still taken" in message
            assert manager.status["connected"] is False
            assert manager.status["retrying"] is True
            assert manager.status["error"] == message
            assert statuses[-1]["retrying"] is True
            # The refused attempt does not leave an SSH connection open
            assert busy.closed.is_set()

            await asyncio.wait_for(manager._reconnect_task, timeout=5)

        assert manager.status["connected"] is True
        assert manager.status["retrying"] is False
        assert manager.status["error"] is None
        assert manager.status["url"] == "https://example.com/start/racoon/"
        assert free.forwarded == ["/var/run/tunnels/racoon"]
        assert statuses[-1]["connected"] is True

        await manager.disconnect()
        await asyncio.sleep(0)


async def test_listener_error_with_random_socket_name_is_not_retried():
    """Without a fixed socket name a refused listener is a plain error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = await make_tunnel_manager(tmpdir, socket_name=None)
        connection = FakeSSHConnection(listen_error=True)

        with patch("webquiz.tunnel.asyncssh.connect", new_callable=AsyncMock, return_value=connection):
            success, message = await manager.connect()

        assert success is False
        assert "Failed to create remote UNIX listener" in message
        assert manager.status["retrying"] is False
        assert manager._reconnect_task is None
        assert manager.connection is None
        assert connection.closed.is_set()


async def test_disconnect_stops_busy_socket_retry():
    """Disconnect (the Cancel button) stops retrying a busy socket name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = await make_tunnel_manager(tmpdir)
        manager._busy_retry_delay = 60

        with patch(
            "webquiz.tunnel.asyncssh.connect",
            new_callable=AsyncMock,
            side_effect=lambda *_args, **_kwargs: FakeSSHConnection(listen_error=True),
        ):
            await manager.connect()
            task = manager._reconnect_task
            assert task is not None and not task.done()

            await manager.disconnect()

        assert task.cancelled()
        assert manager.status["retrying"] is False
        assert manager.status["connected"] is False
        assert manager.status["error"] is None


async def test_connect_replaces_pending_busy_retry():
    """Connecting again while a busy socket name is retried does not start a second retry loop."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = await make_tunnel_manager(tmpdir)
        manager._busy_retry_delay = 60
        free = FakeSSHConnection()

        with patch(
            "webquiz.tunnel.asyncssh.connect",
            new_callable=AsyncMock,
            side_effect=[FakeSSHConnection(listen_error=True), free],
        ):
            await manager.connect()
            pending = manager._reconnect_task

            success, url = await manager.connect()

        assert success is True
        assert url == "https://example.com/start/racoon/"
        assert pending.cancelled()
        assert manager.status["retrying"] is False

        await manager.disconnect()
        await asyncio.sleep(0)


async def test_lost_connection_is_shown_as_retrying():
    """While reconnecting after a lost connection the status says so."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = await make_tunnel_manager(tmpdir)
        statuses = []

        async def status_callback(status):
            statuses.append(status)

        manager.set_status_callback(status_callback)
        first = FakeSSHConnection()

        with patch("webquiz.tunnel.asyncssh.connect", new_callable=AsyncMock, side_effect=[first, FakeSSHConnection()]):
            success, _ = await manager.connect()
            assert success is True
            manager._reconnect_delay = 0

            first.close()  # Connection drops
            task = await wait_for_reconnect_task(manager)
            await asyncio.wait_for(task, timeout=5)

        lost = [s for s in statuses if s["error"] == "Connection lost"]
        assert lost and lost[0]["retrying"] is True and lost[0]["connected"] is False
        assert manager.status["connected"] is True
        assert manager.status["retrying"] is False

        await manager.disconnect()
        await asyncio.sleep(0)


async def test_connect_endpoint_reports_retrying():
    """The admin endpoint answers 202 while a busy socket name is retried."""
    from aiohttp.test_utils import make_mocked_request
    from webquiz.server import TestingServer

    manager = Mock()
    manager.status = {"connected": False, "retrying": True}
    manager.connect = AsyncMock(return_value=(False, "Socket name 'racoon' is still taken"))
    server = SimpleNamespace(
        tunnel_manager=manager, admin_config=SimpleNamespace(trusted_ips=["127.0.0.1"]), translations={}
    )

    response = await TestingServer.tunnel_connect(server, make_mocked_request("POST", "/api/admin/tunnel/connect"))

    assert response.status == 202
    data = json.loads(response.body)
    assert data == {"retrying": True, "message": "Socket name 'racoon' is still taken"}

    manager.status = {"connected": False, "retrying": False}
    manager.connect = AsyncMock(return_value=(False, "Failed to establish SSH tunnel: refused"))
    response = await TestingServer.tunnel_connect(server, make_mocked_request("POST", "/api/admin/tunnel/connect"))
    assert response.status == 500
