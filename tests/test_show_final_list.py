import re
import json
import requests
from pathlib import Path
from conftest import custom_webquiz_server, get_admin_session


def test_show_final_list_default_true(temp_dir):
    """Test that show_final_list defaults to true and question list is shown in results."""
    quiz_data = {
        "default.yaml": {
            "title": "Default Final List Quiz",
            "questions": [
                {"question": "What is 2 + 2?", "options": ["3", "4", "5"], "correct_answer": 1},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f"static_{port}"
        index_path = static_path / "index.html"

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Default should be true
        assert "let showFinalList = true;" in html_content


def test_show_final_list_true_explicit(temp_dir):
    """Test that show_final_list=true embeds true in template."""
    quiz_data = {
        "default.yaml": {
            "title": "Show Final List Quiz",
            "show_final_list": True,
            "questions": [
                {"question": "What is 3 + 3?", "options": ["5", "6", "7"], "correct_answer": 1},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f"static_{port}"
        index_path = static_path / "index.html"

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        assert "let showFinalList = true;" in html_content


def test_show_final_list_false(temp_dir):
    """Test that show_final_list=false embeds false in template."""
    quiz_data = {
        "default.yaml": {
            "title": "Hide Final List Quiz",
            "show_final_list": False,
            "questions": [
                {"question": "What is 4 + 4?", "options": ["7", "8", "9"], "correct_answer": 1},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f"static_{port}"
        index_path = static_path / "index.html"

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        assert "let showFinalList = false;" in html_content


def test_show_final_list_false_still_shows_score():
    """Test that with show_final_list=false, final results still include score summary."""
    quiz_data = {
        "default.yaml": {
            "title": "Score Only Quiz",
            "show_final_list": False,
            "questions": [
                {"question": "Q1?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Register and complete quiz
        register_response = requests.post(
            f"http://localhost:{port}/api/register", json={"username": "testuser"}
        )
        assert register_response.status_code == 200
        user_id = register_response.json()["user_id"]

        submit_response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
        )
        assert submit_response.status_code == 200

        # Verify final results still contain test_results data (server side is unaffected)
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()

        assert verify_data["test_completed"] is True
        assert "final_results" in verify_data
        final_results = verify_data["final_results"]
        assert final_results["correct_count"] == 1
        assert final_results["total_count"] == 1
        assert final_results["percentage"] == 100


def test_show_final_list_validation():
    """Test that show_final_list validation rejects non-boolean values."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Validate a quiz with invalid show_final_list via validate endpoint
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            cookies=cookies,
            json={
                "content": "title: Test\nshow_final_list: notabool\nquestions:\n  - question: Q?\n    options: [A, B]\n    correct_answer: 0\n",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("show_final_list" in e for e in data.get("errors", []))


def test_show_final_list_in_quiz_switch(temp_dir):
    """Test that show_final_list is updated when switching quizzes."""
    quiz_data = {
        "default.yaml": {
            "title": "Quiz With List",
            "show_final_list": True,
            "questions": [
                {"question": "Q1?", "options": ["A", "B"], "correct_answer": 0},
            ],
        },
        "quiz2.yaml": {
            "title": "Quiz Without List",
            "show_final_list": False,
            "questions": [
                {"question": "Q2?", "options": ["X", "Y"], "correct_answer": 1},
            ],
        },
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f"static_{port}"
        index_path = static_path / "index.html"

        # First quiz should have showFinalList = true
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        assert "let showFinalList = true;" in html_content

        # Switch to second quiz
        cookies = get_admin_session(port)
        switch_response = requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            cookies=cookies,
            json={"quiz_filename": "quiz2.yaml"},
        )
        assert switch_response.status_code == 200

        # Second quiz should have showFinalList = false
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        assert "let showFinalList = false;" in html_content
