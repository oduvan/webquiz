"""Tests for quiz file download feature.

Tests the ability to attach downloadable files to quiz questions.
"""

import json
import os
import re
from pathlib import Path

import requests

from tests.conftest import custom_webquiz_server, get_admin_session


def test_admin_list_files_empty_directory(temp_dir):
    """Test listing files when files directory doesn't exist."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        response = requests.get(f"http://localhost:{port}/api/admin/list-files", cookies=cookies)

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert data["files"] == []


def test_admin_list_files_with_files(temp_dir):
    """Test listing files when files directory contains files."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        # Create files directory with test files
        files_dir = f"quizzes_{port}/attach"
        os.makedirs(files_dir, exist_ok=True)

        # Create test files with different content sizes
        test_files = {
            "data.xlsx": "spreadsheet content here",
            "code.py": "print('hello')",
            "report.pdf": "x" * 1000,  # 1KB file
        }
        for filename, content in test_files.items():
            with open(os.path.join(files_dir, filename), "w") as f:
                f.write(content)

        response = requests.get(f"http://localhost:{port}/api/admin/list-files", cookies=cookies)

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 3

        # Verify structure
        for file_info in data["files"]:
            assert "filename" in file_info
            assert "path" in file_info
            assert "size" in file_info
            assert file_info["path"].startswith("/attach/")
            assert isinstance(file_info["size"], int)
            assert file_info["size"] > 0

        # Verify filenames are sorted alphabetically
        filenames = [f["filename"] for f in data["files"]]
        assert filenames == sorted(filenames, key=str.lower)


def test_admin_list_files_requires_auth(temp_dir):
    """Test that list-files endpoint requires authentication."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/api/admin/list-files")
        assert response.status_code == 401


def test_quiz_file_download(temp_dir):
    """Test downloading a quiz file with Content-Disposition header."""
    with custom_webquiz_server() as (proc, port):
        # Create files directory with a test file
        files_dir = f"quizzes_{port}/attach"
        os.makedirs(files_dir, exist_ok=True)

        test_content = "This is test file content"
        with open(os.path.join(files_dir, "testfile.txt"), "w") as f:
            f.write(test_content)

        # Download the file (no auth required for file download)
        response = requests.get(f"http://localhost:{port}/attach/testfile.txt")

        assert response.status_code == 200
        assert response.text == test_content

        # Check Content-Disposition header for forced download
        assert "Content-Disposition" in response.headers
        assert 'attachment' in response.headers["Content-Disposition"]
        assert 'filename="testfile.txt"' in response.headers["Content-Disposition"]


def test_quiz_file_download_not_found(temp_dir):
    """Test downloading a non-existent file returns 404."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/attach/nonexistent.txt")
        assert response.status_code == 404


def test_quiz_file_download_path_traversal_blocked(temp_dir):
    """Test that path traversal attempts are blocked."""
    with custom_webquiz_server() as (proc, port):
        # Create files directory with a test file to ensure the directory exists
        files_dir = f"quizzes_{port}/attach"
        os.makedirs(files_dir, exist_ok=True)
        with open(os.path.join(files_dir, "safe.txt"), "w") as f:
            f.write("safe content")

        # Also create a file we're trying to access via path traversal
        with open(f"quizzes_{port}/secret.yaml", "w") as f:
            f.write("secret: data")

        # Try various path traversal attacks
        malicious_paths = [
            "../secret.yaml",
            "..%2Fsecret.yaml",
            "subfolder/../../../etc/passwd",
        ]

        for path in malicious_paths:
            response = requests.get(f"http://localhost:{port}/attach/{path}")
            # Should return 400 (invalid filename) or 404 (not found after validation)
            # The important thing is that the file is NOT served with 200
            assert response.status_code in [400, 404], f"Path traversal not blocked for: {path} (got {response.status_code})"
            # Make sure we didn't get the secret content
            assert "secret" not in response.text.lower(), f"Path traversal allowed access to secret for: {path}"


def test_question_with_file_field_in_index(temp_dir):
    """Test that file field is properly included in embedded questions.

    Note: In YAML, files are specified as just filenames (e.g., "data.xlsx").
    The server automatically prepends "/attach/" when serving to the client.
    """
    quiz_data = {
        "file_test.yaml": {
            "title": "File Download Test",
            "questions": [
                {"question": "Text only question?", "options": ["A", "B"], "correct_answer": 0},
                {
                    "question": "Question with file?",
                    "options": ["Yes", "No"],
                    "correct_answer": 0,
                    "file": "data.xlsx",  # Just filename, server prepends /attach/
                },
                {
                    # Question with both image and file
                    "question": "Question with image and file?",
                    "options": ["Option 1", "Option 2"],
                    "correct_answer": 1,
                    "image": "/imgs/diagram.png",
                    "file": "analysis.csv",  # Just filename, server prepends /attach/
                },
                {
                    # File-only question (just file, no text)
                    "options": ["A", "B", "C"],
                    "correct_answer": 0,
                    "image": "/imgs/chart.png",
                    "file": "raw_data.json",  # Just filename, server prepends /attach/
                },
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f"static_{port}"
        index_path = static_path / "index.html"

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        questions_match = re.search(r"let questions = (\[.*?\]);", html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))

        assert len(embedded_questions) == 4

        # Question 1: text only, no file
        q1 = embedded_questions[0]
        assert "question" in q1
        assert "file" not in q1

        # Question 2: text and file (server prepends /attach/)
        q2 = embedded_questions[1]
        assert "question" in q2
        assert "file" in q2
        assert q2["file"] == "/attach/data.xlsx"

        # Question 3: text, image, and file
        q3 = embedded_questions[2]
        assert "question" in q3
        assert "image" in q3
        assert "file" in q3
        assert q3["file"] == "/attach/analysis.csv"

        # Question 4: image and file, no text
        q4 = embedded_questions[3]
        assert "image" in q4
        assert "file" in q4
        assert q4["file"] == "/attach/raw_data.json"


def test_files_directory_created_on_startup(temp_dir):
    """Test that the files directory is created automatically on server startup."""
    with custom_webquiz_server() as (proc, port):
        files_dir = Path(f"quizzes_{port}/attach")
        assert files_dir.exists(), "Files directory should be created on startup"
        assert files_dir.is_dir(), "Files directory should be a directory"
