"""Integration tests: time_limit checks on save and copying it when quizzes are united."""

import os

import requests
import yaml
from conftest import custom_webquiz_server, get_admin_session


def validate(port, cookies, quiz_yaml):
    response = requests.post(
        f"http://localhost:{port}/api/admin/validate-quiz", cookies=cookies, json={"content": quiz_yaml}
    )
    assert response.status_code == 200
    return response.json()


def test_validate_quiz_rejects_both_time_limit_modes(temp_dir):
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        data = validate(
            port,
            cookies,
            """title: Both modes
time_limit:
  per_question: 30
  whole_quiz: 600
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 0""",
        )
        assert data["valid"] is False
        assert any("time_limit" in error for error in data["errors"])


def test_validate_quiz_rejects_negative_question_time_limit(temp_dir):
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        data = validate(
            port,
            cookies,
            """title: Negative
time_limit:
  per_question: 30
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 0
    time_limit: -5""",
        )
        assert data["valid"] is False
        assert any("Question 1" in error and "time_limit" in error for error in data["errors"])


def test_validate_quiz_accepts_question_time_limit_without_quiz_time_limit(temp_dir):
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        data = validate(
            port,
            cookies,
            """title: Question only
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 0
    time_limit: 10""",
        )
        assert data["valid"] is True


def test_unite_copies_time_limit_from_first_quiz(temp_dir):
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "time_limit": {"per_question": 30},
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0, "time_limit": 10}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "united_timed"},
        )
        assert response.status_code == 200

        with open(os.path.join(temp_dir, f"quizzes_{port}", "united_timed.yaml"), encoding="utf-8") as f:
            united = yaml.safe_load(f)

        assert united["time_limit"] == {"per_question": 30}
        assert united["questions"][0]["time_limit"] == 10
