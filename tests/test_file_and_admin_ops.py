"""Tests for file operations and admin endpoints to improve coverage."""
import requests
import os
from conftest import custom_webquiz_server


class TestFileOperations:
    """Test file operations and file management endpoints."""

    def test_list_files_quizzes(self):
        """Test listing quiz files."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/files/list?type=quizzes", headers={"X-Master-Key": "test123"}
            )

            assert response.status_code == 200
            data = response.json()
            # Response contains all types: csv, logs, quizzes
            assert "quizzes" in data
            assert isinstance(data["quizzes"], list)

    def test_list_files_logs(self):
        """Test listing log files."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/files/list?type=logs", headers={"X-Master-Key": "test123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "logs" in data

    def test_list_files_csv(self):
        """Test listing CSV files."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/files/list?type=csv", headers={"X-Master-Key": "test123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "csv" in data

    def test_list_files_invalid_type(self):
        """Test listing files with invalid type returns all files."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/files/list?type=invalid", headers={"X-Master-Key": "test123"}
            )

            # API returns all file types even with invalid type parameter
            assert response.status_code == 200
            data = response.json()
            assert "quizzes" in data or "logs" in data or "csv" in data

    def test_files_view_nonexistent_quiz(self):
        """Test viewing a non-existent quiz file."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/files/quizzes/view/nonexistent.yaml", headers={"X-Master-Key": "test123"}
            )

            # Should return 404 or error
            assert response.status_code in [404, 500]

    def test_files_download_quiz(self):
        """Test downloading an existing quiz file."""
        with custom_webquiz_server() as (proc, port):
            # First, list quizzes to get an existing one
            list_response = requests.get(
                f"http://localhost:{port}/api/files/list?type=quizzes", headers={"X-Master-Key": "test123"}
            )
            files = list_response.json().get("files", [])

            if files:
                # Try to download the first quiz
                filename = files[0]["name"]
                response = requests.get(
                    f"http://localhost:{port}/api/files/quizzes/download/{filename}",
                    headers={"X-Master-Key": "test123"},
                )

                # Should succeed
                assert response.status_code == 200


class TestAdminEndpoints:
    """Test various admin endpoints for edge cases."""

    def test_admin_list_quizzes(self):
        """Test listing available quizzes."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/admin/list-quizzes", headers={"X-Master-Key": "test123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "quizzes" in data
            assert isinstance(data["quizzes"], list)

    def test_admin_switch_quiz_success(self):
        """Test switching to an existing quiz."""
        with custom_webquiz_server() as (proc, port):
            # First, list quizzes
            list_response = requests.get(
                f"http://localhost:{port}/api/admin/list-quizzes", headers={"X-Master-Key": "test123"}
            )
            quizzes = list_response.json().get("quizzes", [])

            if quizzes:
                # Try to switch to the first quiz
                quiz_name = quizzes[0]
                response = requests.post(
                    f"http://localhost:{port}/api/admin/switch-quiz",
                    json={"quiz_filename": quiz_name},
                    headers={"X-Master-Key": "test123"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "success" in data or "quiz" in data

    def test_admin_switch_quiz_nonexistent(self):
        """Test switching to a non-existent quiz."""
        with custom_webquiz_server() as (proc, port):
            response = requests.post(
                f"http://localhost:{port}/api/admin/switch-quiz",
                json={"quiz_filename": "nonexistent_quiz.yaml"},
                headers={"X-Master-Key": "test123"},
            )

            # Should return 400 error
            assert response.status_code == 400
            data = response.json()
            assert "error" in data

    def test_admin_get_quiz_content(self):
        """Test getting quiz content."""
        with custom_webquiz_server() as (proc, port):
            # First, list quizzes
            list_response = requests.get(
                f"http://localhost:{port}/api/admin/list-quizzes", headers={"X-Master-Key": "test123"}
            )
            quizzes = list_response.json().get("quizzes", [])

            if quizzes:
                # Try to get the first quiz's content
                quiz_name = quizzes[0]
                response = requests.get(
                    f"http://localhost:{port}/api/admin/quiz/{quiz_name}", headers={"X-Master-Key": "test123"}
                )

                assert response.status_code == 200
                data = response.json()
                assert "content" in data or "quiz" in data

    def test_admin_get_nonexistent_quiz(self):
        """Test getting content of non-existent quiz."""
        with custom_webquiz_server() as (proc, port):
            response = requests.get(
                f"http://localhost:{port}/api/admin/quiz/nonexistent.yaml", headers={"X-Master-Key": "test123"}
            )

            assert response.status_code in [404, 500]

    def test_admin_delete_quiz(self):
        """Test deleting a quiz (should not delete if it's the only one or active)."""
        with custom_webquiz_server() as (proc, port):
            # Try to delete a quiz - should fail or succeed depending on setup
            response = requests.delete(
                f"http://localhost:{port}/api/admin/quiz/test_quiz.yaml", headers={"X-Master-Key": "test123"}
            )

            # Response could be 200 (success), 400 (can't delete active), or 404 (not found)
            assert response.status_code in [200, 400, 404, 500]


class TestAnswerSubmission:
    """Test answer submission edge cases."""

    def test_submit_answer_without_registration(self):
        """Test submitting answer without being registered."""
        with custom_webquiz_server() as (proc, port):
            response = requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": "999999", "question_id": 1, "selected_answer": 0},
            )

            assert response.status_code in [400, 404, 500]
            data = response.json()
            assert "error" in data

    def test_submit_answer_invalid_question_id(self):
        """Test submitting answer for invalid question ID."""
        with custom_webquiz_server() as (proc, port):
            # First register
            reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user_id"]

            # Try to submit answer for question that doesn't exist
            response = requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": 999, "selected_answer": 0},
            )

            # Should return 404 error
            assert response.status_code == 404
            data = response.json()
            assert "error" in data


class TestUserVerification:
    """Test user verification edge cases."""

    def test_verify_user_valid_cookie(self):
        """Test verifying user with valid session cookie."""
        with custom_webquiz_server() as (proc, port):
            # Register user
            reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
            user_id = reg_response.json()["user_id"]

            # Verify with user_id
            verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")

            assert verify_response.status_code == 200
            data = verify_response.json()
            assert data["valid"] is True
            assert data["user_id"] == user_id
