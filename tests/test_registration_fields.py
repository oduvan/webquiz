import pytest
import requests
import csv
import os
import time
from conftest import custom_webquiz_server


def test_registration_with_no_fields():
    """Test registration works without any additional fields (backward compatibility)"""
    config = {"registration": {"fields": []}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register user without additional fields
        response = requests.post(f"{base_url}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert data["username"] == "testuser"


def test_registration_with_single_field():
    """Test registration with one additional field"""
    config = {"registration": {"fields": ["Grade"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register user with grade field
        response = requests.post(f"{base_url}/api/register", json={"username": "student1", "grade": "10"})
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert data["username"] == "student1"


def test_registration_with_multiple_fields():
    """Test registration with multiple additional fields"""
    config = {"registration": {"fields": ["Grade", "School"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register user with both fields
        response = requests.post(
            f"{base_url}/api/register", json={"username": "student2", "grade": "11", "school": "Central HS"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data


def test_registration_field_validation():
    """Test missing required registration fields"""
    config = {"registration": {"fields": ["Grade", "School"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Missing grade field
        response = requests.post(f"{base_url}/api/register", json={"username": "student3", "school": "Test School"})
        assert response.status_code == 400
        assert "error" in response.json()

        # Missing school field
        response = requests.post(f"{base_url}/api/register", json={"username": "student3", "grade": "9"})
        assert response.status_code == 400
        assert "error" in response.json()


def test_user_csv_creation(temp_dir):
    """Test that user CSV file is created with correct headers"""
    config = {"registration": {"fields": ["Grade", "School"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register a user
        response = requests.post(
            f"{base_url}/api/register", json={"username": "student4", "grade": "12", "school": "North HS"}
        )
        assert response.status_code == 200

        # Wait for periodic CSV flush (runs every 5 seconds)
        time.sleep(6)

        # Find and read the user CSV file
        import glob

        user_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.users.csv")
        assert len(user_csv_files) > 0, "User CSV file should be created"

        # Check CSV headers
        with open(user_csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            assert "user_id" in headers
            assert "username" in headers
            assert "grade" in headers
            assert "school" in headers
            assert "registered_at" in headers
            assert "total_questions_asked" in headers
            assert "correct_answers" in headers


def test_user_csv_content(temp_dir):
    """Test that user data is written correctly to CSV"""
    config = {"registration": {"fields": ["Grade"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register a user
        response = requests.post(f"{base_url}/api/register", json={"username": "student5", "grade": "9"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Wait for periodic CSV flush (runs every 5 seconds)
        time.sleep(6)

        # Read user CSV
        import glob

        user_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.users.csv")
        assert len(user_csv_files) > 0

        with open(user_csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["user_id"] == user_id
            assert rows[0]["username"] == "student5"
            assert rows[0]["grade"] == "9"
            assert rows[0]["total_questions_asked"] == "0"
            assert rows[0]["correct_answers"] == "0"


def test_answers_csv_uses_user_id(temp_dir):
    """Test that answers CSV uses user_id instead of username"""
    with custom_webquiz_server() as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register and submit answer
        reg_response = requests.post(f"{base_url}/api/register", json={"username": "answeruser"})
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user_id"]

        # Submit an answer
        answer_response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )
        assert answer_response.status_code == 200

        # Wait for periodic CSV flush (runs every 5 seconds)
        time.sleep(6)

        # Read answers CSV
        import glob

        answer_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.csv")
        # Filter out .users.csv files
        answer_csv_files = [f for f in answer_csv_files if not f.endswith(".users.csv")]
        assert len(answer_csv_files) > 0

        with open(answer_csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            assert "user_id" in headers
            assert "username" not in headers  # Should not have username anymore

            rows = list(reader)
            if len(rows) > 0:
                assert rows[0]["user_id"] == user_id


def test_csv_naming_convention(temp_dir):
    """Test that paired CSV files use same number (quiz_0001.csv and quiz_0001.users.csv)"""
    config = {"registration": {"fields": ["Grade"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register user
        reg_response = requests.post(f"{base_url}/api/register", json={"username": "pairtest", "grade": "10"})
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user_id"]

        # Submit answer
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )

        # Wait for periodic CSV flush (runs every 5 seconds)
        time.sleep(6)

        # Check that both files exist with same number
        import glob
        import re

        user_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.users.csv")
        answer_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.csv")
        answer_csv_files = [f for f in answer_csv_files if not f.endswith(".users.csv")]

        assert len(user_csv_files) > 0
        assert len(answer_csv_files) > 0

        # Extract numbers from filenames
        user_number = re.search(r"_(\d{4})\.users\.csv", user_csv_files[0]).group(1)
        answer_number = re.search(r"_(\d{4})\.csv", answer_csv_files[0]).group(1)

        assert user_number == answer_number, "CSV files should use same number"


def test_user_id_format():
    """Test that user_id is 6 digits"""
    with custom_webquiz_server() as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "formattest"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Check user_id is 6 digits
        assert len(user_id) == 6
        assert user_id.isdigit()
        assert 100000 <= int(user_id) <= 999999


def test_user_id_uniqueness():
    """Test that user_ids are unique"""
    with custom_webquiz_server() as (proc, port):
        base_url = f"http://localhost:{port}"

        user_ids = set()

        # Register multiple users
        for i in range(10):
            response = requests.post(f"{base_url}/api/register", json={"username": f"user{i}"})
            assert response.status_code == 200
            user_id = response.json()["user_id"]
            assert user_id not in user_ids, f"Duplicate user_id: {user_id}"
            user_ids.add(user_id)

        assert len(user_ids) == 10


def test_registration_with_cyrillic_field_labels(temp_dir):
    """Test registration with Cyrillic field labels"""
    config = {"registration": {"fields": ["Клас", "Школа"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register user with Cyrillic fields
        response = requests.post(
            f"{base_url}/api/register", json={"username": "ukrainian_student", "клас": "8", "школа": "Гімназія №5"}
        )
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Wait for periodic CSV flush (runs every 5 seconds)
        time.sleep(6)

        # Read user CSV
        import glob

        user_csv_files = glob.glob(f"{temp_dir}/data_*/test_quiz_*.users.csv")
        assert len(user_csv_files) > 0

        with open(user_csv_files[0], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            assert "клас" in headers
            assert "школа" in headers

            rows = list(reader)
            assert len(rows) >= 1
            user_row = [r for r in rows if r["user_id"] == user_id][0]
            assert user_row["клас"] == "8"
            assert user_row["школа"] == "Гімназія №5"


def test_user_csv_statistics(temp_dir):
    """Test that user statistics (total questions asked and correct answers) are calculated correctly"""
    # Create a custom quiz with 3 questions to test statistics
    quizzes = {
        "stats_quiz.yaml": {
            "title": "Statistics Test Quiz",
            "questions": [
                {"question": "Question 1", "options": ["A", "B", "C"], "correct_answer": 0},
                {"question": "Question 2", "options": ["A", "B", "C"], "correct_answer": 1},
                {"question": "Question 3", "options": ["A", "B", "C"], "correct_answer": 2},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Register a user
        response = requests.post(f"{base_url}/api/register", json={"username": "stats_user"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Submit 3 answers: 2 correct, 1 incorrect
        # Question 1 - Correct (correct_answer is 0, selecting 0)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 0}
        )
        assert response.status_code == 200

        # Question 2 - Incorrect (correct_answer is 1, selecting 0)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": 0}
        )
        assert response.status_code == 200

        # Question 3 - Correct (correct_answer is 2, selecting 2)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 3, "selected_answer": 2}
        )
        assert response.status_code == 200

        # Wait for periodic CSV flush (runs every 5 seconds)
        time.sleep(6)

        # Read user CSV
        import glob

        user_csv_files = glob.glob(f"{temp_dir}/data_*/stats_quiz_*.users.csv")
        assert len(user_csv_files) > 0

        with open(user_csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1

            # Verify statistics: 3 questions asked, 2 correct answers
            assert rows[0]["user_id"] == user_id
            assert rows[0]["username"] == "stats_user"
            assert (
                rows[0]["total_questions_asked"] == "3"
            ), f"Expected 3 questions, got {rows[0]['total_questions_asked']}"
            assert rows[0]["correct_answers"] == "2", f"Expected 2 correct answers, got {rows[0]['correct_answers']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
