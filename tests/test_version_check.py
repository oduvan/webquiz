import requests
from unittest.mock import patch

from conftest import custom_webquiz_server


def test_version_check_endpoint_returns_versions():
    """Test that version check endpoint returns version info."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/api/admin/version-check")

        assert response.status_code == 200
        data = response.json()
        assert "running_version" in data
        assert "file_version" in data
        assert "restart_required" in data
        # When versions match, restart should not be required
        assert data["restart_required"] is False


def test_version_check_returns_matching_versions():
    """Test that running and file versions match under normal conditions."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/api/admin/version-check")

        assert response.status_code == 200
        data = response.json()
        # Under normal conditions, both versions should be the same
        assert data["running_version"] == data["file_version"]
        assert data["restart_required"] is False


def test_version_check_endpoint_requires_local_network():
    """Test that version check endpoint is restricted to local network."""
    with custom_webquiz_server() as (proc, port):
        # The test runs locally, so it should have access
        response = requests.get(f"http://localhost:{port}/api/admin/version-check")
        assert response.status_code == 200


def test_get_file_version_function():
    """Test the get_file_version function directly."""
    from webquiz.server import get_file_version, get_package_version

    file_version = get_file_version()
    package_version = get_package_version()

    # Both should return the same version under normal conditions
    assert file_version != "unknown"
    assert file_version == package_version


def test_get_file_version_parses_correctly():
    """Test that get_file_version correctly parses version from file."""
    from webquiz.server import get_file_version
    import webquiz

    file_version = get_file_version()

    # Should match the actual __version__ from the package
    assert file_version == webquiz.__version__
