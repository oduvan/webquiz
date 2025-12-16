"""Tests for quiz renaming functionality via admin API."""

import pytest
import requests
from conftest import custom_webquiz_server, get_admin_session


def test_rename_quiz_basic(temp_dir):
    """Test basic quiz renaming - rename an inactive quiz."""
    quiz_data = {
        "title": "Original Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }
    # Provide a second quiz so neither is auto-selected as active
    dummy_quiz = {
        "title": "Dummy Quiz",
        "questions": [{"question": "Dummy", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"original_name.yaml": quiz_data, "dummy.yaml": dummy_quiz}) as (
        proc,
        port,
    ):
        # Update quiz with new filename
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/original_name.yaml",
            json={
                "filename": "renamed_quiz",  # Without .yaml extension
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["renamed"] is True
        assert data["filename"] == "renamed_quiz.yaml"

        # Verify old quiz is no longer accessible
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/original_name.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 404, "Old quiz should not be found"

        # Verify can access quiz with new name
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/renamed_quiz.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        assert response.json()["parsed"]["title"] == "Original Quiz"


def test_rename_quiz_with_extension(temp_dir):
    """Test renaming quiz with .yaml extension provided."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }
    dummy_quiz = {
        "title": "Dummy",
        "questions": [{"question": "Q", "options": ["A"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"test.yaml": quiz_data, "dummy.yaml": dummy_quiz}) as (
        proc,
        port,
    ):
        # Rename with .yaml extension included
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/test.yaml",
            json={
                "filename": "renamed.yaml",  # With .yaml extension
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["renamed"] is True
        assert data["filename"] == "renamed.yaml"

        # Verify quiz accessible with new name
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/renamed.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200


def test_rename_quiz_no_change(temp_dir):
    """Test updating quiz without changing filename."""
    quiz_data = {
        "title": "Original Title",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"unchanged.yaml": quiz_data}) as (proc, port):
        # Update quiz content but keep same filename
        updated_data = {
            "title": "Updated Title",
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/unchanged.yaml",
            json={
                "filename": "unchanged",  # Same name
                "mode": "wizard",
                "quiz_data": updated_data,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["renamed"] is False  # No rename occurred
        assert data["filename"] == "unchanged.yaml"

        # Verify file still exists with updated content
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/unchanged.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        assert response.json()["parsed"]["title"] == "Updated Title"


def test_rename_active_quiz_blocked(temp_dir):
    """Test that renaming the currently active quiz is blocked with 409 error."""
    quiz_data = {
        "title": "Active Quiz",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"active.yaml": quiz_data}) as (proc, port):
        # Switch to this quiz to make it active
        response = requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            json={"quiz_filename": "active.yaml"},
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200

        # Try to rename the active quiz
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/active.yaml",
            json={
                "filename": "renamed_active",
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        # Should get 409 Conflict error
        assert response.status_code == 409
        data = response.json()
        assert "error" in data
        assert "Cannot rename active quiz" in data["error"]
        assert "switch to a different quiz" in data["error"]

        # Verify quiz still accessible with old name
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/active.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200, "Original quiz should still exist"

        # Verify renamed quiz doesn't exist
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/renamed_active.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 404, "Renamed quiz should not exist"


def test_rename_quiz_filename_conflict(temp_dir):
    """Test that renaming to an existing filename is blocked with 409 error."""
    quiz_a = {
        "title": "Quiz A",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }
    quiz_b = {
        "title": "Quiz B",
        "questions": [{"question": "Q2", "options": ["C", "D"], "correct_answer": 1}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"quiz_a.yaml": quiz_a, "quiz_b.yaml": quiz_b}) as (proc, port):
        # Try to rename quiz_a to quiz_b (conflict)
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/quiz_a.yaml",
            json={
                "filename": "quiz_b",  # Conflicts with existing file
                "mode": "wizard",
                "quiz_data": quiz_a,
            },
            cookies=get_admin_session(port),
        )

        # Should get 409 Conflict error
        assert response.status_code == 409
        data = response.json()
        assert "error" in data
        assert "already exists" in data["error"]
        assert "quiz_b.yaml" in data["error"]

        # Verify quiz_a still has original title
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/quiz_a.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        assert response.json()["parsed"]["title"] == "Quiz A"


def test_rename_nonexistent_quiz(temp_dir):
    """Test that renaming a nonexistent quiz returns 404."""
    quiz_data = {
        "title": "Test",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Try to rename a quiz that doesn't exist
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/nonexistent.yaml",
            json={
                "filename": "renamed",
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        # Should get 404 Not Found
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()


def test_rename_quiz_text_mode(temp_dir):
    """Test renaming quiz using text mode instead of wizard mode."""
    quiz_data = {
        "title": "Text Mode Quiz",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }
    dummy_quiz = {
        "title": "Dummy",
        "questions": [{"question": "Q", "options": ["A"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"text_quiz.yaml": quiz_data, "dummy.yaml": dummy_quiz}) as (
        proc,
        port,
    ):
        # Get quiz content in YAML format
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/text_quiz.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        yaml_content = response.json()["content"]

        # Update using text mode with new filename
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/text_quiz.yaml",
            json={
                "filename": "renamed_text_quiz",
                "mode": "text",
                "content": yaml_content,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["renamed"] is True
        assert data["filename"] == "renamed_text_quiz.yaml"

        # Verify old quiz no longer accessible
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/text_quiz.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 404

        # Verify renamed quiz accessible
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/renamed_text_quiz.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200


def test_rename_quiz_preserves_content(temp_dir):
    """Test that renaming preserves all quiz content correctly."""
    quiz_data = {
        "title": "Complex Quiz",
        "show_right_answer": True,
        "randomize_questions": True,
        "show_answers_on_completion": False,
        "questions": [
            {
                "question": "Q1 with image",
                "image": "image1.jpg",
                "options": ["A", "B", "C"],
                "correct_answer": 1,
                "points": 2,
            },
            {
                "question": "Q2 text input",
                "default_value": "",
                "correct_value": "42",
                "checker": "answer == '42'",
            },
        ],
    }
    dummy_quiz = {
        "title": "Dummy",
        "questions": [{"question": "Q", "options": ["A"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"complex.yaml": quiz_data, "dummy.yaml": dummy_quiz}) as (
        proc,
        port,
    ):
        # Rename the quiz
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/complex.yaml",
            json={
                "filename": "complex_renamed",
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        assert response.json()["renamed"] is True

        # Verify all content is preserved
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/complex_renamed.yaml",
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        parsed = response.json()["parsed"]
        assert parsed["title"] == "Complex Quiz"
        assert parsed["show_right_answer"] is True
        assert parsed["randomize_questions"] is True
        assert parsed["show_answers_on_completion"] is False
        assert len(parsed["questions"]) == 2
        assert parsed["questions"][0]["image"] == "image1.jpg"
        assert parsed["questions"][0]["points"] == 2
        assert parsed["questions"][1]["checker"] == "answer == '42'"


def test_rename_after_switch_away(temp_dir):
    """Test that quiz can be renamed after switching away from it."""
    quiz_a = {
        "title": "Quiz A",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }
    quiz_b = {
        "title": "Quiz B",
        "questions": [{"question": "Q2", "options": ["C", "D"], "correct_answer": 1}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"quiz_a.yaml": quiz_a, "quiz_b.yaml": quiz_b}) as (proc, port):
        # Switch to quiz_a (make it active)
        response = requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            json={"quiz_filename": "quiz_a.yaml"},
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200

        # Try to rename quiz_a - should fail (it's active)
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/quiz_a.yaml",
            json={
                "filename": "quiz_a_renamed",
                "mode": "wizard",
                "quiz_data": quiz_a,
            },
            cookies=get_admin_session(port),
        )
        assert response.status_code == 409

        # Switch to quiz_b (quiz_a is no longer active)
        response = requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            json={"quiz_filename": "quiz_b.yaml"},
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200

        # Now rename quiz_a - should succeed
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/quiz_a.yaml",
            json={
                "filename": "quiz_a_renamed",
                "mode": "wizard",
                "quiz_data": quiz_a,
            },
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["renamed"] is True
        assert data["filename"] == "quiz_a_renamed.yaml"

        # Verify renamed quiz accessible
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/quiz_a_renamed.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200


def test_rename_quiz_empty_filename(temp_dir):
    """Test that providing empty filename uses original name (no rename)."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }
    dummy_quiz = {
        "title": "Dummy",
        "questions": [{"question": "Q", "options": ["A"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"test.yaml": quiz_data, "dummy.yaml": dummy_quiz}) as (
        proc,
        port,
    ):
        # Update with empty filename
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/test.yaml",
            json={
                "filename": "",  # Empty filename
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["renamed"] is False
        assert data["filename"] == "test.yaml"

        # Verify quiz still accessible with original name
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test.yaml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200


def test_rename_quiz_yml_extension(temp_dir):
    """Test renaming with .yml extension instead of .yaml."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }
    dummy_quiz = {
        "title": "Dummy",
        "questions": [{"question": "Q", "options": ["A"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"test.yaml": quiz_data, "dummy.yaml": dummy_quiz}) as (
        proc,
        port,
    ):
        # Rename with .yml extension
        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/test.yaml",
            json={
                "filename": "renamed.yml",  # .yml extension
                "mode": "wizard",
                "quiz_data": quiz_data,
            },
            cookies=get_admin_session(port),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["renamed"] is True
        assert data["filename"] == "renamed.yml"

        # Verify quiz accessible with .yml extension
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/renamed.yml",
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
