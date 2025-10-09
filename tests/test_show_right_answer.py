import os
import yaml
import requests
import json
from pathlib import Path
from tests.conftest import custom_webquiz_server


def test_show_right_answer_true_explicit():
    """Test that show_right_answer works when explicitly set to true."""
    quiz_data = {
        "default.yaml": {  # Use default.yaml to ensure it gets loaded automatically
            "title": "Show Answers Quiz",
            "show_right_answer": True,
            "questions": [{"question": "What is 3 + 3?", "options": ["5", "6", "7", "8"], "correct_answer": 1}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register a user
        register_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data["user_id"]

        # Submit a wrong answer
        submit_response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},  # Wrong answer (5)
        )
        assert submit_response.status_code == 200
        submit_data = submit_response.json()

        # Should include correct_answer since show_right_answer is true
        assert "correct_answer" in submit_data
        assert submit_data["correct_answer"] == 1
        assert submit_data["is_correct"] is False

        # Verify user final results
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()

        assert verify_data["test_completed"] is True
        assert "final_results" in verify_data
        final_results = verify_data["final_results"]
        assert len(final_results["test_results"]) == 1

        # Final results should include correct_answer
        result = final_results["test_results"][0]
        assert "correct_answer" in result
        assert result["correct_answer"] == "6"  # The correct option text


def test_show_right_answer_false():
    """Test that show_right_answer=false hides correct answers."""
    quiz_data = {
        "default.yaml": {  # Use default.yaml to ensure it gets loaded automatically
            "title": "Hide Answers Quiz",
            "show_right_answer": False,
            "questions": [{"question": "What is 4 + 4?", "options": ["6", "7", "8", "9"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register a user
        register_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data["user_id"]

        # Submit a wrong answer
        submit_response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},  # Wrong answer (6)
        )
        assert submit_response.status_code == 200
        submit_data = submit_response.json()

        # Should NOT include correct_answer or is_correct since show_right_answer is false
        assert "correct_answer" not in submit_data
        assert "is_correct" not in submit_data

        # Verify user final results
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()

        assert verify_data["test_completed"] is True
        assert "final_results" in verify_data
        final_results = verify_data["final_results"]
        assert len(final_results["test_results"]) == 1

        # Final results should NOT include correct_answer or is_correct
        result = final_results["test_results"][0]
        assert "correct_answer" not in result
        assert "is_correct" not in result


def test_show_right_answer_correct_answers_not_leaked():
    """Test that correct answers are not leaked when show_right_answer=false, even for correct submissions."""
    quiz_data = {
        "default.yaml": {  # Use default.yaml to ensure it gets loaded automatically
            "title": "Hide Answers Quiz",
            "show_right_answer": False,
            "questions": [{"question": "What is 5 + 5?", "options": ["8", "9", "10", "11"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register a user
        register_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data["user_id"]

        # Submit a CORRECT answer
        submit_response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 2},  # Correct answer (10)
        )
        assert submit_response.status_code == 200
        submit_data = submit_response.json()

        # Should NOT include correct_answer or is_correct even for correct submissions when show_right_answer is false
        assert "correct_answer" not in submit_data
        assert "is_correct" not in submit_data


def test_show_right_answer_multiple_questions():
    """Test show_right_answer behavior with multiple questions."""
    quiz_data = {
        "default.yaml": {  # Use default.yaml to ensure it gets loaded automatically
            "title": "Multi Question Quiz",
            "show_right_answer": False,
            "questions": [
                {"question": "What is 1 + 1?", "options": ["1", "2", "3", "4"], "correct_answer": 1},
                {"question": "What is 2 * 2?", "options": ["2", "3", "4", "5"], "correct_answer": 2},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register a user
        register_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data["user_id"]

        # Submit answer for question 1 (wrong)
        submit_response1 = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},  # Wrong answer
        )
        assert submit_response1.status_code == 200
        submit_data1 = submit_response1.json()
        assert "correct_answer" not in submit_data1
        assert "is_correct" not in submit_data1

        # Submit answer for question 2 (correct)
        submit_response2 = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 2, "selected_answer": 2},  # Correct answer
        )
        assert submit_response2.status_code == 200
        submit_data2 = submit_response2.json()
        assert "correct_answer" not in submit_data2
        assert "is_correct" not in submit_data2

        # Verify final results
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()

        assert verify_data["test_completed"] is True
        final_results = verify_data["final_results"]
        assert len(final_results["test_results"]) == 2

        # Neither result should have correct_answer field
        for result in final_results["test_results"]:
            assert "correct_answer" not in result


def test_show_right_answer_admin_quiz_update():
    """Test that admin can update show_right_answer setting via wizard mode."""
    original_quiz = {
        "title": "Original Quiz",
        "show_right_answer": True,
        "questions": [{"question": "Original question?", "options": ["A", "B"], "correct_answer": 0}],
    }

    quizzes = {"update_test.yaml": original_quiz}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        updated_quiz_data = {
            "title": "Updated Quiz",
            "show_right_answer": False,  # Changed to false
            "questions": [{"question": "Updated question?", "options": ["X", "Y", "Z"], "correct_answer": 1}],
        }

        update_data = {"mode": "wizard", "quiz_data": updated_quiz_data}

        headers = {"X-Master-Key": "test123"}
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/update_test.yaml", headers=headers, json=update_data
        )
        assert response.status_code == 200

        # Verify the file was actually updated
        get_response = requests.get(f"http://localhost:{port}/api/admin/quiz/update_test.yaml", headers=headers)
        assert get_response.status_code == 200
        updated_content = get_response.json()
        updated_quiz = yaml.safe_load(updated_content["content"])

        # Verify the show_right_answer setting was updated
        assert updated_quiz["show_right_answer"] is False
