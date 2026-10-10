"""SSH Tunnel Manager for WebQuiz

This module provides SSH tunnel functionality to make local WebQuiz servers
accessible via public URLs through remote servers.
"""

import asyncio
import asyncssh
import logging
import secrets
import ipaddress
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import httpx
import yaml

from webquiz.config import TunnelConfig


logger = logging.getLogger(__name__)


class TunnelManager:
    """Manages SSH tunnel connections for public access to WebQuiz server"""

    def __init__(self, config: TunnelConfig, local_port: int = 8080):
        """Initialize tunnel manager

        Args:
            config: TunnelConfig with server and key paths
            local_port: Local port where WebQuiz server is running
        """
        self.config = config
        self.local_port = local_port
        self.connection: Optional[asyncssh.SSHClientConnection] = None
        self.listener = None
        self.socket_id: Optional[str] = None
        self.base_url: Optional[str] = None  # Public URL prefix of all sockets, e.g. https://host/start
        self.status = {
            "connected": False,
            "url": None,
            "error": None,
            "retrying": False,  # Not connected, but trying again in the background
            "keys_status": "unchecked",
            "public_key_content": None,
        }
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 5  # Initial reconnect delay in seconds
        self._max_reconnect_delay = 300  # Max 5 minutes
        self._busy_retry_delay = 15  # Delay between attempts while the fixed socket name is taken
        self._socket_busy = False  # Last attempt failed because the fixed socket name is taken
        self._should_be_connected = False  # Track if we should maintain connection
        self.status_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback function to be called when status changes

        Args:
            callback: Async function that receives status dict
        """
        self.status_callback = callback

    async def _notify_status_change(self):
        """Notify listeners of status change via callback"""
        if self.status_callback:
            try:
                await self.status_callback(self.status.copy())
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    async def ensure_keys_exist(self) -> tuple[bool, str]:
        """Check if SSH keys exist and generate them if missing

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.config.public_key or not self.config.private_key:
            self.status["keys_status"] = "not_configured"
            self.status["error"] = "SSH key paths not configured"
            return False, "SSH key paths not configured in tunnel section"

        public_key_path = Path(self.config.public_key)
        private_key_path = Path(self.config.private_key)

        # Check if only one key exists (error condition)
        public_exists = public_key_path.exists()
        private_exists = private_key_path.exists()

        if public_exists and not private_exists:
            self.status["keys_status"] = "partial"
            self.status["error"] = "Public key exists but private key is missing"
            return False, "Public key exists but private key is missing"
        elif private_exists and not public_exists:
            self.status["keys_status"] = "partial"
            self.status["error"] = "Private key exists but public key is missing"
            return False, "Private key exists but public key is missing"
        elif public_exists and private_exists:
            # Both exist - verify they're readable and valid
            try:
                with open(public_key_path, "rb") as f:
                    public_key_content = f.read()
                with open(private_key_path, "rb") as f:
                    private_key_content = f.read()

                # Try to load the keys to verify they're valid
                asyncssh.import_private_key(private_key_content)
                asyncssh.import_public_key(public_key_content)

                # Store public key content for display
                self.status["public_key_content"] = public_key_content.decode("utf-8").strip()
                self.status["keys_status"] = "ok"
                logger.info("SSH keys validated successfully")
                return True, "SSH keys found and validated"
            except Exception as e:
                self.status["keys_status"] = "invalid"
                self.status["error"] = f"Keys exist but are invalid: {e}"
                return False, f"Keys exist but are invalid: {e}"

        # Neither exists - generate new keys
        try:
            logger.info("Generating new ED25519 SSH key pair...")

            # Create parent directories if they don't exist
            private_key_path.parent.mkdir(parents=True, exist_ok=True)
            public_key_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate ED25519 key pair
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            # Serialize private key in OpenSSH format without passphrase
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption(),
            )

            # Serialize public key in OpenSSH format
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH, format=serialization.PublicFormat.OpenSSH
            )

            # Add comment to public key
            public_key_with_comment = public_bytes + b" webquiz@tunnel\n"

            # Write keys to files with proper permissions
            private_key_path.write_bytes(private_bytes)
            private_key_path.chmod(0o600)  # Read/write for owner only

            public_key_path.write_bytes(public_key_with_comment)
            public_key_path.chmod(0o644)  # Read for all, write for owner

            self.status["public_key_content"] = public_key_with_comment.decode("utf-8").strip()
            self.status["keys_status"] = "ok"
            logger.info(f"SSH keys generated successfully at {private_key_path} and {public_key_path}")
            return True, f"SSH keys generated at {private_key_path}"

        except Exception as e:
            self.status["keys_status"] = "error"
            self.status["error"] = f"Failed to generate keys: {e}"
            logger.error(f"Failed to generate SSH keys: {e}")
            return False, f"Failed to generate SSH keys: {e}"

    async def fetch_tunnel_config(self) -> Optional[Dict[str, Any]]:
        """Fetch tunnel configuration from remote server or use local config

        If local config subsection is provided, uses that instead of fetching.

        Returns:
            Dict with username, socket_directory, base_url or None on error
        """
        # Check if local tunnel config is provided
        if self.config.config:
            logger.info("Using local tunnel configuration from config file")
            return {
                "username": self.config.config.username,
                "socket_directory": self.config.config.socket_directory,
                "base_url": self.config.config.base_url,
            }

        # Otherwise fetch from server
        if not self.config.server:
            return None

        # Determine protocol based on whether server is an IP address
        protocol = "http"
        try:
            # Try to parse as IP address
            ipaddress.ip_address(self.config.server)
            protocol = "http"  # Use HTTP for IP addresses
        except ValueError:
            # Not an IP address, assume it's a domain name
            protocol = "https"  # Use HTTPS for domain names

        url = f"{protocol}://{self.config.server}/tunnel_config.yaml"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                config_data = yaml.safe_load(response.text)

                # Validate required fields
                required_fields = ["username", "socket_directory", "base_url"]
                for field in required_fields:
                    if field not in config_data:
                        raise ValueError(f"Missing required field in tunnel config: {field}")

                logger.info(f"Fetched tunnel config from {url}")
                return config_data

        except Exception as e:
            logger.error(f"Failed to fetch tunnel config from {url}: {e}")
            self.status["error"] = f"Failed to fetch config from server: {e}"
            return None

    def _generate_socket_id(self) -> str:
        """Generate random 6-8 character hex socket identifier

        Returns:
            Random hex string like 'a3f7b2'
        """
        # Generate 3-4 random bytes and convert to hex
        num_bytes = secrets.choice([3, 4])  # 3 bytes = 6 hex chars, 4 bytes = 8 hex chars
        return secrets.token_hex(num_bytes)

    async def connect(self) -> tuple[bool, str]:
        """Establish SSH tunnel connection (admin action)

        With a fixed socket_name the tunnel server can still hold the socket of an
        earlier connection: sshd keeps it until it drops that connection, and the
        socket file stays until the server's cleanup job removes it. Then the attempt
        is repeated in the background until the name is free (status "retrying").

        Returns:
            Tuple of (success: bool, url_or_error: str)
        """
        # A new attempt replaces any background reconnect attempts and the current
        # connection: two connections cannot hold the same fixed socket name
        self._should_be_connected = False
        await self._cancel_reconnect()
        self._close_connection()
        self.status["retrying"] = False

        success, result = await self._connect_once()
        if not success and self._socket_busy:
            self._should_be_connected = True
            self._reconnect_task = asyncio.create_task(self._auto_reconnect())
        return success, result

    async def _connect_once(self) -> tuple[bool, str]:
        """Make one attempt to establish the SSH tunnel

        Returns:
            Tuple of (success: bool, url_or_error: str)
        """
        self._socket_busy = False

        # Check if server is configured
        if not self.config.server:
            error_msg = "Tunnel server not configured"
            self.status["error"] = error_msg
            return False, error_msg

        # Ensure keys exist
        keys_ok, keys_msg = await self.ensure_keys_exist()
        if not keys_ok:
            return False, keys_msg

        # Fetch tunnel config from server
        tunnel_config = await self.fetch_tunnel_config()
        if not tunnel_config:
            return False, self.status.get("error", "Failed to fetch tunnel config")

        # Use custom socket name if provided, otherwise generate random ID
        self.socket_id = self.config.socket_name if self.config.socket_name else self._generate_socket_id()

        try:
            # Establish SSH connection
            logger.info(f"Connecting to {self.config.server} as {tunnel_config['username']}...")

            self.connection = await asyncssh.connect(
                self.config.server,
                username=tunnel_config["username"],
                client_keys=[self.config.private_key],
                known_hosts=None,  # Don't verify host keys (can be improved for security)
            )

            # Create Unix socket path on remote server
            remote_socket = f"{tunnel_config['socket_directory']}/{self.socket_id}"

            # Forward local server to remote Unix socket
            # Remote server listens on Unix socket, forwards to local port
            self.listener = await self.connection.forward_remote_path_to_port(
                remote_socket, "127.0.0.1", self.local_port
            )

            # Construct public URL
            base_url = tunnel_config["base_url"].rstrip("/")
            public_url = f"{base_url}/{self.socket_id}/"
            self.base_url = base_url

            # Update status
            self.status["connected"] = True
            self.status["url"] = public_url
            self.status["error"] = None
            self.status["retrying"] = False
            self._should_be_connected = True
            self._reconnect_delay = 5  # Reset reconnect delay on successful connection

            logger.info(f"SSH tunnel established! Public URL: {public_url}")
            await self._notify_status_change()

            # Start monitoring connection
            asyncio.create_task(self._monitor_connection(self.connection))

            return True, public_url

        except Exception as e:
            self._close_connection()
            if isinstance(e, asyncssh.ChannelListenError) and self.config.socket_name:
                self._socket_busy = True
                error_msg = (
                    f"Socket name '{self.socket_id}' is still taken on the tunnel server by an earlier "
                    "connection. The tunnel server frees it when that connection times out."
                )
            else:
                error_msg = f"Failed to establish SSH tunnel: {e}"
            logger.error(error_msg)
            self.status["error"] = error_msg
            self.status["connected"] = False
            self.status["url"] = None
            self.status["retrying"] = self._socket_busy or self._should_be_connected
            await self._notify_status_change()
            return False, error_msg
        except asyncio.CancelledError:
            self._close_connection()
            raise

    def _close_connection(self):
        """Close the SSH connection of a failed or cancelled attempt"""
        if self.connection:
            self.connection.close()
            self.connection = None
        self.listener = None

    async def _cancel_reconnect(self):
        """Stop background reconnect attempts"""
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        self._reconnect_task = None

    async def disconnect(self):
        """Close SSH tunnel connection"""
        self._should_be_connected = False
        await self._cancel_reconnect()

        # Close listener
        if self.listener:
            self.listener.close()
            await self.listener.wait_closed()
            self.listener = None

        # Close SSH connection
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
            self.connection = None

        # Update status
        self.status["connected"] = False
        self.status["url"] = None
        self.status["error"] = None
        self.status["retrying"] = False
        self.socket_id = None
        self.base_url = None

        logger.info("SSH tunnel disconnected")
        await self._notify_status_change()

    async def _monitor_connection(self, connection: asyncssh.SSHClientConnection):
        """Monitor SSH connection and handle disconnections"""
        try:
            await connection.wait_closed()

            # Connection closed; a replaced or deliberately closed connection is not a loss
            if connection is self.connection and self._should_be_connected:
                logger.warning("SSH tunnel connection lost")
                self.status["connected"] = False
                self.status["url"] = None
                self.status["error"] = "Connection lost"
                self.status["retrying"] = True
                await self._notify_status_change()

                # Start reconnect attempts
                self._reconnect_task = asyncio.create_task(self._auto_reconnect())

        except Exception as e:
            logger.error(f"Error monitoring connection: {e}")

    async def _auto_reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        while self._should_be_connected:
            try:
                # A taken socket name is checked often: it becomes free at an unknown moment
                delay = self._busy_retry_delay if self._socket_busy else self._reconnect_delay
                logger.info(f"Attempting to reconnect in {delay} seconds...")
                await asyncio.sleep(delay)

                if not self._should_be_connected:
                    break

                logger.info("Reconnecting SSH tunnel...")
                success, result = await self._connect_once()

                if success:
                    logger.info(f"Reconnected successfully: {result}")
                    break
                else:
                    logger.warning(f"Reconnect attempt failed: {result}")
                    if not self._socket_busy:
                        # Exponential backoff
                        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

            except asyncio.CancelledError:
                logger.info("Reconnect cancelled")
                break
            except Exception as e:
                logger.error(f"Error during reconnect attempt: {e}")
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    def get_public_endpoint(self) -> Optional[tuple[str, str]]:
        """Get the public address of this server while the tunnel is connected

        Other WebQuiz servers on the same tunnel server are reachable at
        "{base_url}/{their socket name}/".

        Returns:
            Tuple of (base_url, socket_id) or None if not connected
        """
        if self.status["connected"] and self.base_url and self.socket_id:
            return self.base_url, self.socket_id
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current tunnel status

        Returns:
            Dict with connected, url, error, keys_status, public_key_content
        """
        return self.status.copy()

    async def cleanup(self):
        """Clean up resources (call on server shutdown)"""
        await self.disconnect()
