"""Tests for downloading quizzes from private (token-protected) archives."""

import io
import os
import http.server
import socketserver
import threading
import zipfile

import requests
from conftest import custom_webquiz_server, get_admin_session


QUIZ_CONTENT = """title: Private Quiz
description: A quiz from a private repository
questions:
  - question: What is 2 + 2?
    options: ["3", "4", "5", "6"]
    correct_answer: 1
"""


def make_zip_bytes(entries):
    """Build a ZIP archive in memory from a {path: content} dictionary."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


class ZipFileServer:
    """Serves a single ZIP archive over HTTP, optionally requiring a bearer token.

    Records the Authorization header of every request so tests can check
    what the webquiz server actually sent.
    """

    def __init__(self, zip_bytes, required_token=None):
        self.zip_bytes = zip_bytes
        self.required_token = required_token
        self.auth_headers = []
        self.httpd = None
        self.port = None

    def __enter__(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                server.auth_headers.append(self.headers.get("Authorization"))

                if server.required_token:
                    expected = f"Bearer {server.required_token}"
                    if self.headers.get("Authorization") != expected:
                        self.send_response(401)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                        self.wfile.write(b"Not Found")
                        return

                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(server.zip_bytes)))
                self.end_headers()
                self.wfile.write(server.zip_bytes)

            def log_message(self, format, *args):
                pass  # Suppress logging

        self.httpd = socketserver.TCPServer(("", 0), Handler)
        self.httpd.allow_reuse_address = True
        self.port = self.httpd.server_address[1]

        thread = threading.Thread(target=self.httpd.serve_forever)
        thread.daemon = True
        thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.httpd.shutdown()
        self.httpd.server_close()

    def url(self):
        return f"http://localhost:{self.port}/archive.zip"


def download_quiz(port, name, download_path, folder):
    """Call the download-quiz endpoint as an authenticated admin."""
    cookies = get_admin_session(port)
    return requests.post(
        f"http://localhost:{port}/api/admin/download-quiz",
        cookies=cookies,
        json={"name": name, "download_path": download_path, "folder": folder},
    )


def test_download_quiz_sends_token_from_config():
    """A token in the quizzes config is sent as a bearer token."""
    zip_bytes = make_zip_bytes({"owner-repo-abc123/data/private_quiz.yaml": QUIZ_CONTENT})

    with ZipFileServer(zip_bytes, required_token="secret-token-123") as zip_server:
        config = {
            "quizzes": [
                {
                    "name": "Private Quiz",
                    "download_path": zip_server.url(),
                    "folder": "owner-repo-abc123/data",
                    "auth_header_token": "secret-token-123",
                }
            ]
        }

        with custom_webquiz_server(config=config) as (proc, port):
            response = download_quiz(port, "Private Quiz", zip_server.url(), "owner-repo-abc123/data")

            assert response.status_code == 200, response.text
            assert response.json()["success"] is True
            assert zip_server.auth_headers == ["Bearer secret-token-123"]
            assert os.path.exists(os.path.join(f"quizzes_{port}", "private_quiz.yaml"))


def test_download_quiz_without_token_sends_no_authorization_header():
    """Quizzes configured without a token keep working unauthenticated."""
    zip_bytes = make_zip_bytes({"data/public_quiz.yaml": QUIZ_CONTENT})

    with ZipFileServer(zip_bytes) as zip_server:
        config = {
            "quizzes": [
                {
                    "name": "Public Quiz",
                    "download_path": zip_server.url(),
                    "folder": "data",
                }
            ]
        }

        with custom_webquiz_server(config=config) as (proc, port):
            response = download_quiz(port, "Public Quiz", zip_server.url(), "data")

            assert response.status_code == 200, response.text
            assert zip_server.auth_headers == [None]


def test_download_quiz_token_uses_configured_url_not_the_request_one():
    """The token goes to the configured URL, never to one supplied in the request."""
    zip_bytes = make_zip_bytes({"data/private_quiz.yaml": QUIZ_CONTENT})

    with ZipFileServer(zip_bytes, required_token="secret-token-123") as configured_server:
        with ZipFileServer(zip_bytes) as other_server:
            config = {
                "quizzes": [
                    {
                        "name": "Private Quiz",
                        "download_path": configured_server.url(),
                        "folder": "data",
                        "auth_header_token": "secret-token-123",
                    }
                ]
            }

            with custom_webquiz_server(config=config) as (proc, port):
                response = download_quiz(port, "Private Quiz", other_server.url(), "data")

                assert response.status_code == 200, response.text
                assert configured_server.auth_headers == ["Bearer secret-token-123"]
                assert other_server.auth_headers == []


def test_download_quiz_token_refused_over_plain_http():
    """A token is never sent over plain HTTP to a remote host."""
    config = {
        "quizzes": [
            {
                "name": "Private Quiz",
                "download_path": "http://example.com/archive.zip",
                "folder": "data",
                "auth_header_token": "secret-token-123",
            }
        ]
    }

    with custom_webquiz_server(config=config) as (proc, port):
        response = download_quiz(port, "Private Quiz", "http://example.com/archive.zip", "data")

        assert response.status_code == 400
        assert "https" in response.json()["error"].lower()


def test_download_quiz_folder_resolved_inside_archive_root():
    """A folder path may be given relative to the archive's single root directory."""
    zip_bytes = make_zip_bytes({"owner-repo-9f8e7d6/data/private_quiz.yaml": QUIZ_CONTENT})

    with ZipFileServer(zip_bytes) as zip_server:
        with custom_webquiz_server() as (proc, port):
            response = download_quiz(port, "Private Quiz", zip_server.url(), "data")

            assert response.status_code == 200, response.text
            assert os.path.exists(os.path.join(f"quizzes_{port}", "private_quiz.yaml"))


def test_admin_page_does_not_expose_the_token():
    """The token stays on the server and never reaches the admin page."""
    config = {
        "quizzes": [
            {
                "name": "Private Quiz",
                "download_path": "https://example.com/archive.zip",
                "folder": "data",
                "auth_header_token": "secret-token-123",
            }
        ]
    }

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)
        response = requests.get(f"http://localhost:{port}/admin/", cookies=cookies)

        assert response.status_code == 200
        assert "Private Quiz" in response.text
        assert "secret-token-123" not in response.text
