"""Tests for question randomization feature."""

import pytest
import requests
import os
from conftest import custom_webquiz_server, get_admin_session


def test_randomization_disabled_by_default(temp_dir):
    """Test that randomization is disabled by default when not specified in YAML."""
    quiz_data = {
        "title": "Default Behavior Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Verify user - should not have question_order when randomization disabled
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"]
        assert "question_order" not in data  # No question order when randomization disabled


def test_randomization_enabled(temp_dir):
    """Test that question_order is generated when randomize_questions is true."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Verify user - should have question_order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"]
        assert "question_order" in data
        assert isinstance(data["question_order"], list)
        assert len(data["question_order"]) == 5
        # Should contain all question IDs (1-5)
        assert set(data["question_order"]) == {1, 2, 3, 4, 5}


def test_different_users_get_different_orders(temp_dir):
    """Test that different users get different randomized question orders."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
            {"question": "Q6", "options": ["K", "L"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        question_orders = []

        # Register 5 different users and collect their question orders
        for i in range(5):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            assert response.status_code == 200
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            assert response.status_code == 200
            data = response.json()
            question_orders.append(tuple(data["question_order"]))

        # With 6 questions and 5 users, it's very unlikely all orders are identical
        # (probability = 1/6! ^ 4 ≈ 1.16 × 10^-14)
        unique_orders = set(question_orders)
        assert len(unique_orders) > 1, "Expected at least some users to have different question orders"


def test_question_order_persists_across_verifications(temp_dir):
    """Test that question order persists across multiple user verification calls."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        # Get question order first time
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        first_order = response.json()["question_order"]

        # Verify multiple times - order should remain the same
        for _ in range(5):
            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["question_order"] == first_order


def test_randomization_with_approval_workflow(temp_dir):
    """Test that question order is generated during approval workflow."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config, quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user (not yet approved)
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]
        assert data["requires_approval"]
        assert not data["approved"]

        # Verify user before approval - should have question_order already generated
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "question_order" in data
        pre_approval_order = data["question_order"]

        # Approve user
        response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user",
            json={"user_id": user_id},
            cookies = get_admin_session(port),
        )
        assert response.status_code == 200

        # Verify user after approval - question_order should be the same
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["approved"]
        assert data["question_order"] == pre_approval_order


def test_yaml_validation_accepts_randomize_questions_boolean(temp_dir):
    """Test that YAML validation accepts randomize_questions as boolean."""
    import yaml

    valid_quiz = {
        "title": "Valid Quiz",
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(quizzes={"test.yaml": valid_quiz}) as (proc, port):
        # Validate quiz via admin API (send as YAML string in content field)
        yaml_content = yaml.dump(valid_quiz)
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": yaml_content},
            cookies = get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"]
        assert len(data.get("errors", [])) == 0


def test_yaml_validation_rejects_non_boolean_randomize_questions(temp_dir):
    """Test that YAML validation rejects non-boolean randomize_questions values."""
    import yaml

    invalid_quiz = {
        "title": "Invalid Quiz",
        "randomize_questions": "yes",  # String instead of boolean
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(
        quizzes={
            "test.yaml": {"title": "Default", "questions": [{"question": "Q", "options": ["A"], "correct_answer": 0}]}
        }
    ) as (proc, port):
        # Validate quiz via admin API (send as YAML string in content field)
        yaml_content = yaml.dump(invalid_quiz)
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": yaml_content},
            cookies = get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert not data["valid"]
        assert any("randomize_questions" in error and "boolean" in error for error in data["errors"])


def test_randomization_false_behaves_like_disabled(temp_dir):
    """Test that randomize_questions: false behaves the same as omitting the field."""
    quiz_data = {
        "title": "Non-Randomized Quiz",
        "randomize_questions": False,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        # Verify user - should not have question_order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        data = response.json()
        assert "question_order" not in data


def test_question_order_all_ids_present(temp_dir):
    """Test that question_order contains all question IDs exactly once."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": f"Q{i}", "options": ["A", "B"], "correct_answer": 0} for i in range(1, 11)  # 10 questions
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        data = response.json()
        question_order = data["question_order"]

        # Should have exactly 10 items
        assert len(question_order) == 10

        # Should contain all IDs from 1-10 exactly once
        assert sorted(question_order) == list(range(1, 11))

        # Check for duplicates
        assert len(set(question_order)) == len(question_order)


def test_randomization_with_single_question(temp_dir):
    """Test that randomization works (trivially) with a single question."""
    quiz_data = {
        "title": "Single Question Quiz",
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        data = response.json()
        assert data["question_order"] == [1]


def test_yaml_validation_accepts_other_top_level_fields(temp_dir):
    """Test that validation still accepts title and show_right_answer alongside randomize_questions."""
    import yaml

    quiz_data = {
        "title": "Full Featured Quiz",
        "show_right_answer": False,
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Server should start successfully and accept the quiz
        yaml_content = yaml.dump(quiz_data)
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": yaml_content},
            cookies = get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"]


def test_progress_tracking_with_randomization(temp_dir):
    """Test that progress tracking works correctly with randomized questions after page refresh."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "show_right_answer": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Get user's randomized question order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        question_order = data["question_order"]

        # User should start at index 0
        assert data["next_question_index"] == 0

        # Answer the first question in the randomized order
        first_question_id = question_order[0]
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": first_question_id, "selected_answer": 0},
        )
        assert response.status_code == 200

        # Simulate page refresh by verifying user again
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        # Next question index should be 1 (second question in randomized order)
        assert data["next_question_index"] == 1, (
            f"After answering question {first_question_id}, next_question_index should be 1, "
            f"but got {data['next_question_index']}"
        )

        # Answer the second question in the randomized order
        second_question_id = question_order[1]
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": second_question_id, "selected_answer": 0},
        )
        assert response.status_code == 200

        # Verify again after second answer
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        # Next question index should be 2 (third question in randomized order)
        assert data["next_question_index"] == 2, (
            f"After answering 2 questions, next_question_index should be 2, " f"but got {data['next_question_index']}"
        )


def test_progress_tracking_without_randomization(temp_dir):
    """Test that progress tracking still works correctly without randomization."""
    quiz_data = {
        "title": "Non-Randomized Quiz",
        "randomize_questions": False,
        "show_right_answer": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Verify user starts at index 0
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["next_question_index"] == 0

        # Answer question 1 (ID=1)
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
        )
        assert response.status_code == 200

        # Verify progress moved to next question
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["next_question_index"] == 1


def test_final_results_with_randomization(temp_dir):
    """Test that final results show all answers correctly when randomization is enabled."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "show_right_answer": True,
        "questions": [
            {"question": "Q1", "options": ["A1", "B1"], "correct_answer": 0},
            {"question": "Q2", "options": ["A2", "B2"], "correct_answer": 1},
            {"question": "Q3", "options": ["A3", "B3"], "correct_answer": 0},
            {"question": "Q4", "options": ["A4", "B4"], "correct_answer": 1},
            {"question": "Q5", "options": ["A5", "B5"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Get user's randomized question order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        question_order = data["question_order"]
        assert len(question_order) == 5

        # Answer all questions in the randomized order
        for question_id in question_order:
            response = requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": 0},
            )
            assert response.status_code == 200

        # After all questions answered, verify user to get final results
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()

        # Verify test is marked as completed
        assert data["test_completed"] == True
        assert "final_results" in data

        # Verify final results contain all questions
        final_results = data["final_results"]
        assert final_results["total_count"] == 5
        assert len(final_results["test_results"]) == 5

        # Verify all test results have required fields
        for result in final_results["test_results"]:
            assert "question" in result
            assert "selected_answer" in result
            assert "correct_answer" in result
            assert "is_correct" in result
            assert "time_taken" in result

        # Verify the results are in the order the user answered them (randomized order)
        for i, result in enumerate(final_results["test_results"]):
            expected_question = f"Q{question_order[i]}"
            assert result["question"] == expected_question


def test_cannot_skip_questions_with_randomization(temp_dir):
    """Test that users cannot answer questions out of order when randomization is enabled."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Get user's randomized question order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        question_order = data["question_order"]

        # Get the expected first and third questions
        first_question_id = question_order[0]
        third_question_id = question_order[2]

        # Try to answer the third question without answering the first - should fail
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": third_question_id, "selected_answer": 0},
        )
        assert response.status_code == 403, "Should reject answering out-of-order question"
        data = response.json()
        assert "error" in data
        assert data["expected_question_id"] == first_question_id

        # Answer the first question correctly
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": first_question_id, "selected_answer": 0},
        )
        assert response.status_code == 200

        # Now try to skip the second question and answer the third - should still fail
        second_question_id = question_order[1]
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": third_question_id, "selected_answer": 0},
        )
        assert response.status_code == 403, "Should reject skipping second question"
        data = response.json()
        assert data["expected_question_id"] == second_question_id


def test_cannot_answer_already_answered_questions_with_randomization(temp_dir):
    """Test that users cannot re-answer questions with randomization enabled."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        # Get question order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        question_order = response.json()["question_order"]

        first_question_id = question_order[0]
        second_question_id = question_order[1]

        # Answer the first question
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": first_question_id, "selected_answer": 0},
        )
        assert response.status_code == 200

        # Try to answer the first question again - should fail
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": first_question_id, "selected_answer": 1},
        )
        assert response.status_code == 403, "Should reject re-answering previous question"
        data = response.json()
        assert data["expected_question_id"] == second_question_id


def test_cannot_answer_after_completing_quiz_with_randomization(temp_dir):
    """Test that users cannot submit answers after completing all questions."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        # Get question order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        question_order = response.json()["question_order"]

        # Answer all questions
        for question_id in question_order:
            response = requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": 0},
            )
            assert response.status_code == 200

        # Try to answer the first question again after completing - should fail
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": question_order[0], "selected_answer": 1},
        )
        assert response.status_code == 400, "Should reject answering after quiz completion"
        data = response.json()
        assert "вже відповіли на всі питання" in data["error"]


def test_sequential_answering_allowed_without_randomization(temp_dir):
    """Test that sequential answering still works when randomization is disabled."""
    quiz_data = {
        "title": "Non-Randomized Quiz",
        "randomize_questions": False,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        # Answer questions in order 1, 2, 3 - should all succeed
        for question_id in [1, 2, 3]:
            response = requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": 0},
            )
            assert response.status_code == 200, f"Question {question_id} should be accepted"


def test_validation_error_message_quality(temp_dir):
    """Test that validation error messages are clear and helpful."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        # Get question order
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        question_order = response.json()["question_order"]

        expected_first = question_order[0]
        wrong_question = question_order[2]

        # Try to answer wrong question
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": wrong_question, "selected_answer": 0},
        )

        # Verify error response structure
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "expected_question_id" in data
        assert data["expected_question_id"] == expected_first

        # Verify error message is in Ukrainian and clear
        assert "поточне питання" in data["error"].lower() or "питання" in data["error"].lower()
