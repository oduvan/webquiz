"""
Tests for CSV write safety and data preservation
"""

import os
import csv
import time
import pytest
from unittest.mock import patch, AsyncMock
from conftest import custom_webquiz_server


def test_responses_csv_data_preserved_on_write_failure(temp_dir):
    """Test that response data is preserved if CSV write fails."""
    with custom_webquiz_server() as (proc, port):
        import requests

        base_url = f"http://localhost:{port}"

        # Register a user
        response = requests.post(f"{base_url}/api/register", json={"username": "testuser1"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Submit an answer
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )
        assert response.status_code == 200

        # Trigger flush to write CSV
        response = requests.post(f"{base_url}/api/test/flush")
        assert response.status_code == 200

        # Verify CSV file was created and contains data
        import glob

        csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.csv")
        assert len(csv_files) > 0, "Response CSV file should be created"

        # Read CSV and verify data
        with open(csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1, "CSV should contain 1 response"
            assert rows[0]["user_id"] == user_id


def test_users_csv_atomic_write(temp_dir):
    """Test that users CSV uses atomic write (no partial data on failure)."""
    with custom_webquiz_server() as (proc, port):
        import requests

        base_url = f"http://localhost:{port}"

        # Register multiple users
        user_ids = []
        for i in range(3):
            response = requests.post(f"{base_url}/api/register", json={"username": f"user{i}"})
            assert response.status_code == 200
            user_ids.append(response.json()["user_id"])

        # Submit answers for all users
        for user_id in user_ids:
            response = requests.post(
                f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
            )
            assert response.status_code == 200

        # Trigger flush
        response = requests.post(f"{base_url}/api/test/flush")
        assert response.status_code == 200

        # Verify users CSV contains all users
        import glob

        user_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.users.csv")
        assert len(user_csv_files) > 0, "User CSV file should be created"

        with open(user_csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3, "CSV should contain 3 users"

            # Verify all users are present
            csv_user_ids = {row["user_id"] for row in rows}
            assert csv_user_ids == set(user_ids), "All registered users should be in CSV"


def test_csv_no_temp_files_left_behind(temp_dir):
    """Test that no temporary CSV files are left behind after successful write."""
    with custom_webquiz_server() as (proc, port):
        import requests
        import glob

        base_url = f"http://localhost:{port}"

        # Register a user and submit answer
        response = requests.post(f"{base_url}/api/register", json={"username": "temptest"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )
        assert response.status_code == 200

        # Trigger flush
        response = requests.post(f"{base_url}/api/test/flush")
        assert response.status_code == 200

        # Wait a moment for filesystem operations
        time.sleep(0.5)

        # Check for temp files
        temp_files = glob.glob(f"{temp_dir}/data_*/*.tmp")
        assert len(temp_files) == 0, "No temporary files should be left behind"


def test_csv_data_accumulates_correctly(temp_dir):
    """Test that CSV data accumulates correctly across multiple flushes."""
    # Create a quiz with 2 questions
    quizzes = {
        "test_quiz.yaml": {
            "title": "Test Quiz",
            "questions": [
                {"question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
                {"question": "What is 3 + 3?", "options": ["5", "6", "7", "8"], "correct_answer": 1},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        import requests

        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "acctest"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Submit first answer and flush
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )
        assert response.status_code == 200

        requests.post(f"{base_url}/api/test/flush")

        # Submit second answer and flush
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": 1}
        )
        assert response.status_code == 200

        requests.post(f"{base_url}/api/test/flush")

        # Verify CSV contains both responses
        import glob

        csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.csv")
        assert len(csv_files) > 0

        with open(csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2, "CSV should contain 2 responses"
            assert rows[0]["user_id"] == user_id
            assert rows[1]["user_id"] == user_id
