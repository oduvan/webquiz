"""
Integration tests for question points functionality
"""

import pytest
import requests
import time
import csv
import os
from tests.conftest import custom_webquiz_server, get_admin_session


@pytest.fixture
def points_server():
    """Create a test server with questions that have different point values"""
    quiz_data = {
        "title": "Points Test Quiz",
        "show_right_answer": True,
        "questions": [
            # Default points (1)
            {"question": "What is 2+2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
            # Custom points (3)
            {"question": "Hard question worth 3 points", "options": ["A", "B", "C", "D"], "correct_answer": 0, "points": 3},
            # Custom points (5)
            {"question": "Very hard question worth 5 points", "options": ["X", "Y", "Z", "W"], "correct_answer": 2, "points": 5},
        ],
    }

    quizzes = {"default.yaml": quiz_data}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        yield proc, port


@pytest.fixture
def default_points_server():
    """Create a test server with all questions having default points (1)"""
    quiz_data = {
        "title": "Default Points Quiz",
        "show_right_answer": True,
        "questions": [
            {"question": "Question 1", "options": ["A", "B", "C", "D"], "correct_answer": 0},
            {"question": "Question 2", "options": ["A", "B", "C", "D"], "correct_answer": 1},
        ],
    }

    quizzes = {"default.yaml": quiz_data}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        yield proc, port


class TestQuestionPointsIntegration:
    """Integration tests for question points functionality"""

    def test_questions_include_points_in_client_data(self, points_server):
        """Test that points are included in the questions sent to the client"""
        proc, port = points_server
        base_url = f"http://localhost:{port}"

        # Get the index page which contains the questions JSON
        response = requests.get(f"{base_url}/")
        assert response.status_code == 200

        # The questions are embedded in the HTML - look for the JSON
        content = response.text
        assert '"points": 1' in content or '"points":1' in content  # Default points
        assert '"points": 3' in content or '"points":3' in content  # Custom points
        assert '"points": 5' in content or '"points":5' in content  # Custom points

    def test_correct_answer_earns_question_points(self, points_server):
        """Test that a correct answer earns the full points for that question"""
        proc, port = points_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Answer question 1 correctly (1 point)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )
        assert response.status_code == 200
        assert response.json()["is_correct"] == True

        # Answer question 2 correctly (3 points)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": 0}
        )
        assert response.status_code == 200
        assert response.json()["is_correct"] == True

        # Answer question 3 correctly (5 points)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 3, "selected_answer": 2}
        )
        assert response.status_code == 200
        assert response.json()["is_correct"] == True

        # Verify final results
        response = requests.get(f"{base_url}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["test_completed"] == True
        final_results = data["final_results"]
        assert final_results["correct_count"] == 3
        assert final_results["total_count"] == 3
        assert final_results["earned_points"] == 9  # 1 + 3 + 5
        assert final_results["total_points"] == 9
        assert final_results["points_percentage"] == 100

    def test_incorrect_answer_earns_zero_points(self, points_server):
        """Test that incorrect answers earn zero points"""
        proc, port = points_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "testuser2"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Answer question 1 correctly (1 point)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": 1}
        )
        assert response.status_code == 200

        # Answer question 2 incorrectly (0 points out of 3)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": 1}
        )
        assert response.status_code == 200
        assert response.json()["is_correct"] == False

        # Answer question 3 incorrectly (0 points out of 5)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 3, "selected_answer": 0}
        )
        assert response.status_code == 200

        # Verify final results
        response = requests.get(f"{base_url}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["test_completed"] == True
        final_results = data["final_results"]
        assert final_results["correct_count"] == 1
        assert final_results["total_count"] == 3
        assert final_results["earned_points"] == 1  # Only first question correct
        assert final_results["total_points"] == 9
        assert final_results["points_percentage"] == 11  # ~11% (1/9)

    def test_csv_includes_points_columns(self, points_server):
        """Test that the users CSV includes earned_points and total_points columns"""
        proc, port = points_server
        base_url = f"http://localhost:{port}"

        # Register user and answer questions
        response = requests.post(f"{base_url}/api/register", json={"username": "csvtest"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Answer all questions
        for q_id, answer in [(1, 1), (2, 0), (3, 2)]:
            response = requests.post(
                f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": q_id, "selected_answer": answer}
            )
            assert response.status_code == 200

        # Wait for CSV flush (5 seconds interval)
        time.sleep(6)

        # Find and read the CSV file
        csv_dir = f"data_{port}"
        csv_files = [f for f in os.listdir(csv_dir) if f.endswith(".users.csv")]
        assert len(csv_files) > 0, "No users CSV file found"

        csv_path = os.path.join(csv_dir, csv_files[0])
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) > 0, "No rows in CSV"
        row = rows[0]

        # Check that points columns exist
        assert "earned_points" in row, "earned_points column missing"
        assert "total_points" in row, "total_points column missing"
        assert row["earned_points"] == "9"  # All correct
        assert row["total_points"] == "9"

    def test_default_points_when_not_specified(self, default_points_server):
        """Test that questions without explicit points default to 1 point"""
        proc, port = default_points_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "defaulttest"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Answer both questions correctly
        for q_id in [1, 2]:
            response = requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": q_id, "selected_answer": q_id - 1},
            )
            assert response.status_code == 200

        # Verify final results
        response = requests.get(f"{base_url}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        final_results = data["final_results"]
        # When all questions have default points, total_count == total_points
        assert final_results["total_count"] == 2
        assert final_results["total_points"] == 2  # 1 + 1
        assert final_results["earned_points"] == 2

    def test_test_results_include_question_points(self, points_server):
        """Test that individual test results include points for each question"""
        proc, port = points_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "resultstest"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Answer all questions (q1 correct, q2 wrong, q3 correct)
        for q_id, answer in [(1, 1), (2, 1), (3, 2)]:
            response = requests.post(
                f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": q_id, "selected_answer": answer}
            )
            assert response.status_code == 200

        # Verify final results include points per question
        response = requests.get(f"{base_url}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        final_results = data["final_results"]
        test_results = final_results["test_results"]

        assert len(test_results) == 3

        # Check points and earned_points for each result
        assert test_results[0]["points"] == 1
        assert test_results[0]["earned_points"] == 1  # Correct

        assert test_results[1]["points"] == 3
        assert test_results[1]["earned_points"] == 0  # Wrong

        assert test_results[2]["points"] == 5
        assert test_results[2]["earned_points"] == 5  # Correct

        # Total earned should be 1 + 0 + 5 = 6
        assert final_results["earned_points"] == 6
        assert final_results["total_points"] == 9


class TestPointsWithRandomization:
    """Test points work correctly with randomized question order"""

    @pytest.fixture
    def randomized_points_server(self):
        """Create a test server with points and randomization enabled"""
        quiz_data = {
            "title": "Randomized Points Quiz",
            "show_right_answer": True,
            "randomize_questions": True,
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 2},
                {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "points": 3},
                {"question": "Q3", "options": ["E", "F"], "correct_answer": 0, "points": 5},
            ],
        }

        quizzes = {"default.yaml": quiz_data}

        with custom_webquiz_server(quizzes=quizzes) as (proc, port):
            yield proc, port

    def test_points_with_randomized_order(self, randomized_points_server):
        """Test that points are tracked correctly regardless of question order"""
        proc, port = randomized_points_server
        base_url = f"http://localhost:{port}"

        # Register user - should get randomized question order
        response = requests.post(f"{base_url}/api/register", json={"username": "randomtest"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]
        question_order = data.get("question_order", [1, 2, 3])

        # Answer questions in the randomized order
        correct_answers = {1: 0, 2: 1, 3: 0}  # Correct answer for each question ID
        for q_id in question_order:
            response = requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": q_id, "selected_answer": correct_answers[q_id]},
            )
            assert response.status_code == 200
            assert response.json()["is_correct"] == True

        # Verify final results
        response = requests.get(f"{base_url}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        final_results = data["final_results"]
        assert final_results["total_points"] == 10  # 2 + 3 + 5
        assert final_results["earned_points"] == 10  # All correct
