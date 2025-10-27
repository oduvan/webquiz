import os
import yaml
import requests
import json
from pathlib import Path
from tests.conftest import custom_webquiz_server


def test_basic_functionality_answers_hidden_until_all_complete():
    """Test that answers are hidden until all students complete, then shown."""
    quiz_data = {
        "default.yaml": {
            "title": "Show Answers On Completion Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
                {"question": "What is 3 + 3?", "options": ["5", "6", "7", "8"], "correct_answer": 1},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        assert user1_response.status_code == 200
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        assert user2_response.status_code == 200
        user2_id = user2_response.json()["user_id"]

        # User 1 completes the quiz
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 1},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 2, "selected_answer": 1},
        )

        # Verify user 1 - should NOT have correct answers yet
        verify1_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        assert verify1_response.status_code == 200
        verify1_data = verify1_response.json()
        assert verify1_data["test_completed"] is True
        assert "final_results" in verify1_data
        final_results1 = verify1_data["final_results"]

        # Check flags
        assert final_results1["show_answers_on_completion"] is True
        assert final_results1["all_completed"] is False

        # Verify correct answers are NOT shown
        for result in final_results1["test_results"]:
            assert "correct_answer" not in result
            assert "is_correct" not in result

        # User 2 completes the quiz
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 1, "selected_answer": 1},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 2, "selected_answer": 1},
        )

        # Verify user 1 again - NOW should have correct answers
        verify1_after_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        assert verify1_after_response.status_code == 200
        verify1_after_data = verify1_after_response.json()
        final_results1_after = verify1_after_data["final_results"]

        # Check flags
        assert final_results1_after["show_answers_on_completion"] is True
        assert final_results1_after["all_completed"] is True

        # Verify correct answers ARE now shown
        for result in final_results1_after["test_results"]:
            assert "correct_answer" in result
            assert "is_correct" in result

        # Verify user 2 also has correct answers
        verify2_response = requests.get(f"http://localhost:{port}/api/verify-user/{user2_id}")
        assert verify2_response.status_code == 200
        verify2_data = verify2_response.json()
        final_results2 = verify2_data["final_results"]

        assert final_results2["all_completed"] is True
        for result in final_results2["test_results"]:
            assert "correct_answer" in result
            assert "is_correct" in result


def test_waiting_message_displayed_when_not_all_complete():
    """Test that API response includes correct flags for waiting message display."""
    quiz_data = {
        "default.yaml": {
            "title": "Waiting Message Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "What is 5 + 5?", "options": ["8", "9", "10", "11"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]

        # User 1 completes
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 2},
        )

        # Verify response includes necessary flags
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        assert verify_response.status_code == 200
        data = verify_response.json()

        assert data["test_completed"] is True
        final_results = data["final_results"]
        assert final_results["show_answers_on_completion"] is True
        assert final_results["all_completed"] is False

        # Frontend should display waiting message based on these flags


def test_dynamic_behavior_new_registration_hides_answers():
    """Test that new registration dynamically hides answers again."""
    quiz_data = {
        "default.yaml": {
            "title": "Dynamic Behavior Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "What is 7 + 7?", "options": ["12", "13", "14", "15"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register and complete with two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]

        # Both complete
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 2},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 1, "selected_answer": 2},
        )

        # Verify answers are visible
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results = verify_response.json()["final_results"]
        assert final_results["all_completed"] is True
        assert "correct_answer" in final_results["test_results"][0]

        # New user registers
        user3_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user3"})
        user3_id = user3_response.json()["user_id"]

        # Verify answers are now hidden again for user 1
        verify_after_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results_after = verify_after_response.json()["final_results"]
        assert final_results_after["all_completed"] is False
        assert "correct_answer" not in final_results_after["test_results"][0]

        # User 3 completes
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user3_id, "question_id": 1, "selected_answer": 2},
        )

        # Now answers are visible again
        verify_final_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results_final = verify_final_response.json()["final_results"]
        assert final_results_final["all_completed"] is True
        assert "correct_answer" in final_results_final["test_results"][0]


def test_approval_mode_counts_only_approved():
    """Test that only approved students are counted for completion check."""
    quiz_data = {
        "default.yaml": {
            "title": "Approval Mode Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "What is 9 + 9?", "options": ["16", "17", "18", "19"], "correct_answer": 2}],
        }
    }

    config_data = {"registration": {"approve": True}}

    with custom_webquiz_server(quizzes=quiz_data, config=config_data) as (proc, port):
        # Register 3 users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]

        user3_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user3"})
        user3_id = user3_response.json()["user_id"]

        # Admin approves only user1 and user2
        headers = {"X-Master-Key": "test123"}
        requests.put(
            f"http://localhost:{port}/api/admin/approve-user",
            headers=headers,
            json={"user_id": user1_id, "approved": True},
        )
        requests.put(
            f"http://localhost:{port}/api/admin/approve-user",
            headers=headers,
            json={"user_id": user2_id, "approved": True},
        )

        # User 1 and 2 complete
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 2},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 1, "selected_answer": 2},
        )

        # Verify answers are shown (only approved students count)
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results = verify_response.json()["final_results"]
        assert final_results["all_completed"] is True
        assert "correct_answer" in final_results["test_results"][0]

        # Even if user3 (unapproved) hasn't completed, answers should still be visible


def test_single_student_immediate_visibility():
    """Test that single student sees answers immediately upon completion."""
    quiz_data = {
        "default.yaml": {
            "title": "Single Student Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "What is 4 + 4?", "options": ["6", "7", "8", "9"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register single user
        user_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user_id = user_response.json()["user_id"]

        # User completes
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 2},
        )

        # Verify answers are immediately visible
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        data = verify_response.json()
        final_results = data["final_results"]

        assert final_results["all_completed"] is True
        assert final_results["show_answers_on_completion"] is True
        assert "correct_answer" in final_results["test_results"][0]
        assert "is_correct" in final_results["test_results"][0]


def test_interaction_with_show_right_answer_true():
    """Test that show_right_answer: true takes precedence."""
    quiz_data = {
        "default.yaml": {
            "title": "Precedence Quiz",
            "show_right_answer": True,
            "show_answers_on_completion": True,
            "questions": [{"question": "What is 6 + 6?", "options": ["10", "11", "12", "13"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]

        # Only user 1 completes
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 2},
        )

        # Verify answers are shown even though not all students completed
        # (show_right_answer: true takes precedence)
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results = verify_response.json()["final_results"]

        assert final_results["all_completed"] is False
        assert "correct_answer" in final_results["test_results"][0]
        assert "is_correct" in final_results["test_results"][0]


def test_interaction_with_show_right_answer_false():
    """Test that show_right_answer: false and show_answers_on_completion: false never shows answers."""
    quiz_data = {
        "default.yaml": {
            "title": "Never Show Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": False,
            "questions": [{"question": "What is 8 + 8?", "options": ["14", "15", "16", "17"], "correct_answer": 2}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register and complete single user
        user_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user_id = user_response.json()["user_id"]

        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 2},
        )

        # Verify answers are NOT shown even though all (one) students completed
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        final_results = verify_response.json()["final_results"]

        assert final_results["all_completed"] is True
        assert final_results["show_answers_on_completion"] is False
        assert "correct_answer" not in final_results["test_results"][0]
        assert "is_correct" not in final_results["test_results"][0]


def test_works_with_randomize_questions():
    """Test that show_answers_on_completion works correctly with randomized questions."""
    quiz_data = {
        "default.yaml": {
            "title": "Randomized Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "randomize_questions": True,
            "questions": [
                {"question": "What is 1 + 1?", "options": ["1", "2", "3", "4"], "correct_answer": 1},
                {"question": "What is 2 + 2?", "options": ["2", "3", "4", "5"], "correct_answer": 2},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]
        question_order_1 = user1_response.json()["question_order"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]
        question_order_2 = user2_response.json()["question_order"]

        # Complete quiz for user 1 following their order
        for question_id in question_order_1:
            requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user1_id, "question_id": question_id, "selected_answer": 1},
            )

        # Verify answers NOT shown yet
        verify1_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results1 = verify1_response.json()["final_results"]
        assert final_results1["all_completed"] is False
        assert "correct_answer" not in final_results1["test_results"][0]

        # Complete quiz for user 2 following their order
        for question_id in question_order_2:
            requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user2_id, "question_id": question_id, "selected_answer": 1},
            )

        # Now answers should be shown for both users
        verify1_after_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results1_after = verify1_after_response.json()["final_results"]
        assert final_results1_after["all_completed"] is True
        assert "correct_answer" in final_results1_after["test_results"][0]

        verify2_response = requests.get(f"http://localhost:{port}/api/verify-user/{user2_id}")
        final_results2 = verify2_response.json()["final_results"]
        assert final_results2["all_completed"] is True
        assert "correct_answer" in final_results2["test_results"][0]


def test_api_response_structure():
    """Test that API response includes all necessary fields."""
    quiz_data = {
        "default.yaml": {
            "title": "API Structure Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "Test question?", "options": ["A", "B", "C", "D"], "correct_answer": 0}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register and complete
        user_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user_id = user_response.json()["user_id"]

        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
        )

        # Verify response structure
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify_response.status_code == 200
        data = verify_response.json()

        assert "final_results" in data
        final_results = data["final_results"]

        # Check all required fields
        assert "all_completed" in final_results
        assert "show_answers_on_completion" in final_results
        assert "test_results" in final_results
        assert "correct_count" in final_results
        assert "total_count" in final_results
        assert "percentage" in final_results
        assert "total_time" in final_results

        # Check field types
        assert isinstance(final_results["all_completed"], bool)
        assert isinstance(final_results["show_answers_on_completion"], bool)
        assert isinstance(final_results["test_results"], list)


def test_no_students_edge_case():
    """Test that server handles no students gracefully."""
    quiz_data = {
        "default.yaml": {
            "title": "No Students Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Just verify server is running and accepts requests
        # No registrations, just check that the server doesn't crash

        # Try to verify a non-existent user
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/999999")
        # Should return invalid, not crash
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["valid"] is False
