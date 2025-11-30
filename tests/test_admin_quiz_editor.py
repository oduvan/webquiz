"""Tests for admin quiz editor functionality with randomize_questions field."""

import pytest
import requests
from conftest import custom_webquiz_server, get_admin_session


def test_create_quiz_with_randomize_questions_via_wizard(temp_dir):
    """Test creating a quiz with randomize_questions using wizard mode."""
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        quiz_data = {
            "title": "Test Quiz",
            "show_right_answer": True,
            "randomize_questions": True,
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            ],
        }

        # Create quiz via wizard mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_randomized", "mode": "wizard", "quiz_data": quiz_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify quiz was created with randomize_questions
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_randomized.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is True
        assert data["parsed"]["show_right_answer"] is True


def test_create_quiz_without_randomize_questions_defaults_false(temp_dir):
    """Test that omitting randomize_questions in wizard mode defaults to false."""
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        quiz_data = {
            "title": "Test Quiz",
            "show_right_answer": False,
            # randomize_questions not specified
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
        }

        # Create quiz via wizard mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_no_randomize", "mode": "wizard", "quiz_data": quiz_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200

        # Verify quiz was created with randomize_questions as false
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_no_randomize.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        # When not specified in wizard, it should default to false
        assert data["parsed"].get("randomize_questions", False) is False


def test_edit_quiz_to_add_randomize_questions(temp_dir):
    """Test editing an existing quiz to add randomize_questions."""
    quiz_data = {
        "title": "Original Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"editable.yaml": quiz_data}) as (proc, port):
        # First, verify the quiz doesn't have randomize_questions
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/editable.yaml", cookies = get_admin_session(port)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parsed"].get("randomize_questions", False) is False

        # Update quiz to enable randomize_questions
        updated_data = {
            "title": "Updated Quiz",
            "show_right_answer": True,
            "randomize_questions": True,
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            ],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/editable.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200

        # Verify randomize_questions was added
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/editable.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is True
        assert data["parsed"]["title"] == "Updated Quiz"


def test_randomize_questions_preserved_after_edit(temp_dir):
    """Test that randomize_questions setting is preserved when editing other quiz fields."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"randomized.yaml": quiz_data}) as (proc, port):
        # Get the quiz
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/randomized.yaml", cookies = get_admin_session(port)
        )
        assert response.status_code == 200
        original_data = response.json()["parsed"]

        # Edit quiz to change title but keep randomize_questions
        updated_data = {
            "title": "Updated Title",
            "randomize_questions": True,  # Explicitly keep it
            "questions": original_data["questions"],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/randomized.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200

        # Verify randomize_questions is still True
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/randomized.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is True
        assert data["parsed"]["title"] == "Updated Title"


def test_disable_randomize_questions_via_edit(temp_dir):
    """Test disabling randomize_questions on an existing randomized quiz."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"to_disable.yaml": quiz_data}) as (proc, port):
        # Verify it starts with randomize_questions enabled
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/to_disable.yaml", cookies = get_admin_session(port)
        )
        assert response.status_code == 200
        assert response.json()["parsed"]["randomize_questions"] is True

        # Disable randomize_questions
        updated_data = {
            "title": "No Longer Randomized",
            "randomize_questions": False,
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/to_disable.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200

        # Verify randomize_questions is now False
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/to_disable.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is False
        assert data["parsed"]["title"] == "No Longer Randomized"


def test_create_quiz_with_show_answers_on_completion(temp_dir):
    """Test creating a quiz with show_answers_on_completion using wizard mode."""
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        quiz_data = {
            "title": "Completion Answers Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            ],
        }

        # Create quiz via wizard mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_completion_answers", "mode": "wizard", "quiz_data": quiz_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify quiz was created with show_answers_on_completion
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_completion_answers.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["show_answers_on_completion"] is True
        assert data["parsed"]["show_right_answer"] is False


def test_edit_quiz_to_enable_show_answers_on_completion(temp_dir):
    """Test editing an existing quiz to enable show_answers_on_completion."""
    quiz_data = {
        "title": "Original Quiz",
        "show_right_answer": False,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"enable_completion.yaml": quiz_data}) as (proc, port):
        # First, verify the quiz doesn't have show_answers_on_completion
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/enable_completion.yaml", cookies = get_admin_session(port)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parsed"].get("show_answers_on_completion", False) is False

        # Update quiz to enable show_answers_on_completion
        updated_data = {
            "title": "Updated Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/enable_completion.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            cookies = get_admin_session(port),
        )

        assert response.status_code == 200

        # Verify show_answers_on_completion was added
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/enable_completion.yaml", cookies = get_admin_session(port)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["show_answers_on_completion"] is True
        assert data["parsed"]["title"] == "Updated Quiz"
