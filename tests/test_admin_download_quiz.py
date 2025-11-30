import os
import json
import requests
import tempfile
import zipfile
from conftest import custom_webquiz_server, get_admin_session


def test_download_quiz_path_validation_valid_subfolder(temp_dir):
    """Test that valid subfolder paths are accepted."""
    with custom_webquiz_server() as (proc, port):
        # Create a temporary ZIP file with a quiz
        with tempfile.NamedTemporaryFile(mode="w", suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name

        try:
            # Create a ZIP with a quiz file
            with zipfile.ZipFile(zip_path, "w") as zf:
                quiz_content = """title: Test Quiz
description: A test quiz
questions:
  - question: What is 2 + 2?
    options: ["3", "4", "5", "6"]
    correct_answer: 1
"""
                zf.writestr("webquiz-quizzes-master/data/test_quiz.yaml", quiz_content)

            # Start a simple HTTP server to serve the ZIP file
            import http.server
            import socketserver
            import threading

            os.chdir(os.path.dirname(zip_path))

            class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass  # Suppress logging

            handler = QuietHTTPRequestHandler
            # Use port 0 to let the OS assign a free port
            httpd = socketserver.TCPServer(("", 0), handler)
            httpd.allow_reuse_address = True
            file_port = httpd.server_address[1]  # Get the assigned port

            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()

            # Test the download endpoint with a valid subfolder path
            cookies = get_admin_session(port)
            download_data = {
                "name": "Test Quiz",
                "download_path": f"http://localhost:{file_port}/{os.path.basename(zip_path)}",
                "folder": "webquiz-quizzes-master/data/",
            }

            response = requests.post(
                f"http://localhost:{port}/api/admin/download-quiz", cookies=cookies, json=download_data
            )

            httpd.shutdown()

            # Should succeed with valid subfolder path
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "message" in data
            assert "Test Quiz" in data["message"]

        finally:
            # Clean up
            if os.path.exists(zip_path):
                os.unlink(zip_path)


def test_download_quiz_path_validation_parent_directory_blocked():
    """Test that parent directory traversal is blocked."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Test various path traversal attempts
        malicious_paths = [
            "../etc/passwd",
            "foo/../../etc/passwd",
            "foo/../../../etc/passwd",
        ]

        for malicious_path in malicious_paths:
            download_data = {
                "name": "Malicious Quiz",
                "download_path": "http://example.com/quiz.zip",
                "folder": malicious_path,
            }

            response = requests.post(
                f"http://localhost:{port}/api/admin/download-quiz", cookies=cookies, json=download_data
            )

            # Should be blocked
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "parent directory" in data["error"].lower() or "traversal" in data["error"].lower()


def test_download_quiz_path_validation_absolute_path_blocked():
    """Test that absolute paths are blocked."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Test absolute path attempts
        absolute_paths = [
            "/etc/passwd",
            "/tmp/malicious",
            "C:\\Windows\\System32",
        ]

        for absolute_path in absolute_paths:
            download_data = {
                "name": "Malicious Quiz",
                "download_path": "http://example.com/quiz.zip",
                "folder": absolute_path,
            }

            response = requests.post(
                f"http://localhost:{port}/api/admin/download-quiz", cookies=cookies, json=download_data
            )

            # Should be blocked
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "absolute" in data["error"].lower() or "not allowed" in data["error"].lower()


def test_download_quiz_empty_folder_path():
    """Test that empty folder path is allowed (extracts to quizzes root)."""
    with custom_webquiz_server() as (proc, port):
        # Create a temporary ZIP file with a quiz
        with tempfile.NamedTemporaryFile(mode="w", suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name

        try:
            # Create a ZIP with a quiz file in root
            with zipfile.ZipFile(zip_path, "w") as zf:
                quiz_content = """title: Root Quiz
description: A quiz in root directory
questions:
  - question: What is 1 + 1?
    options: ["1", "2", "3", "4"]
    correct_answer: 1
"""
                zf.writestr("root_quiz.yaml", quiz_content)

            # Start a simple HTTP server
            import http.server
            import socketserver
            import threading

            os.chdir(os.path.dirname(zip_path))

            class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass

            handler = QuietHTTPRequestHandler
            # Use port 0 to let the OS assign a free port
            httpd = socketserver.TCPServer(("", 0), handler)
            httpd.allow_reuse_address = True
            file_port = httpd.server_address[1]  # Get the assigned port

            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()

            # Test with empty folder path
            cookies = get_admin_session(port)
            download_data = {
                "name": "Root Quiz",
                "download_path": f"http://localhost:{file_port}/{os.path.basename(zip_path)}",
                "folder": "",  # Empty folder path
            }

            response = requests.post(
                f"http://localhost:{port}/api/admin/download-quiz", cookies=cookies, json=download_data
            )

            httpd.shutdown()

            # Should succeed
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

        finally:
            if os.path.exists(zip_path):
                os.unlink(zip_path)


def test_download_quiz_missing_parameters():
    """Test that missing required parameters are rejected."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Test missing name
        response = requests.post(
            f"http://localhost:{port}/api/admin/download-quiz",
            cookies=cookies,
            json={"download_path": "http://example.com/quiz.zip"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

        # Test missing download_path
        response = requests.post(
            f"http://localhost:{port}/api/admin/download-quiz", cookies=cookies, json={"name": "Test Quiz"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
