import requests
import importlib.resources as pkg_resources

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


def test_version_mismatch_detected_when_file_changed():
    """Test that version mismatch is detected when __init__.py file is modified after server starts."""
    import webquiz

    # Get the path to the __init__.py file
    init_file = pkg_resources.files("webquiz") / "__init__.py"

    # Read original content
    original_content = init_file.read_text(encoding="utf-8")
    original_version = webquiz.__version__

    # Create modified content with a different version
    modified_version = "99.99.99"
    modified_content = original_content.replace(
        f'__version__ = "{original_version}"',
        f'__version__ = "{modified_version}"'
    )

    # Get the actual file path for writing
    import pathlib
    init_path = pathlib.Path(init_file)

    # Start server first with original version
    with custom_webquiz_server() as (proc, port):
        # Verify initial state - versions should match
        response = requests.get(f"http://localhost:{port}/api/admin/version-check")
        assert response.status_code == 200
        data = response.json()
        assert data["running_version"] == original_version
        assert data["file_version"] == original_version
        assert data["restart_required"] is False

        try:
            # Modify the file WHILE server is running (simulating pip upgrade)
            with open(init_path, "w", encoding="utf-8") as f:
                f.write(modified_content)

            # Check version mismatch after file modification
            response = requests.get(f"http://localhost:{port}/api/admin/version-check")

            assert response.status_code == 200
            data = response.json()

            # Running version should still be the original (loaded at server start)
            assert data["running_version"] == original_version
            # File version should be the modified version (read from disk)
            assert data["file_version"] == modified_version
            # Restart should be required due to mismatch
            assert data["restart_required"] is True

        finally:
            # Always restore original content
            with open(init_path, "w", encoding="utf-8") as f:
                f.write(original_content)
