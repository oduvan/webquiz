"""Tests for quiz settings chosen when the admin starts a quiz.

The values in the quiz file are only the defaults. Settings sent with
switch-quiz apply to the running quiz and are never written to the file.
"""

import os

import requests
import yaml
from conftest import custom_webquiz_server, get_admin_session, register_student


def question(text="Q?", **extra):
    return {"question": text, "options": ["A", "B"], "correct_answer": 0, **extra}


def quiz_file(**settings):
    return {"title": "Start Settings", "questions": [question("Q1?"), question("Q2?")], **settings}


def start(port, cookies, filename, settings=None):
    body = {"quiz_filename": filename}
    if settings is not None:
        body["settings"] = settings
    return requests.post(f"http://localhost:{port}/api/admin/switch-quiz", cookies=cookies, json=body)


def page(port):
    return requests.get(f"http://localhost:{port}/").text


def question_start(port, user_id, question_id):
    response = requests.post(
        f"http://localhost:{port}/api/question-start", json={"user_id": user_id, "question_id": question_id}
    )
    assert response.status_code == 200
    return response.json()


def read_quiz_file(temp_dir, port, filename):
    with open(os.path.join(temp_dir, f"quizzes_{port}", filename), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_start_settings_apply_to_running_quiz(temp_dir):
    quizzes = {"q.yaml": quiz_file(show_right_answer=True, show_final_list=True)}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        response = start(
            port,
            cookies,
            "q.yaml",
            {
                "show_right_answer": False,
                "show_answers_on_completion": True,
                "randomize_questions": True,
                "show_final_list": False,
                "time_limit": {"per_question": 30},
            },
        )
        assert response.status_code == 200
        assert response.json()["settings"]["time_limit"] == {"per_question": 30}

        html = page(port)
        assert "let showRightAnswer = false" in html
        assert "let showFinalList = false" in html

        registration = requests.post(f"http://localhost:{port}/api/register", json={"username": "S"}).json()
        assert "question_order" in registration  # randomized
        first_id = registration["question_order"][0]
        assert 29 < question_start(port, registration["user_id"], first_id)["remaining_seconds"] <= 30

        listing = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies).json()
        assert listing["show_answers_on_completion"] is True


def test_start_settings_are_not_written_to_the_quiz_file(temp_dir):
    quizzes = {"q.yaml": quiz_file(show_right_answer=True)}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        before = read_quiz_file(temp_dir, port, "q.yaml")
        assert start(port, cookies, "q.yaml", {"show_right_answer": False, "time_limit": {"whole_quiz": 60}}).ok
        assert read_quiz_file(temp_dir, port, "q.yaml") == before


def test_missing_settings_keep_the_quiz_file_values(temp_dir):
    quizzes = {"q.yaml": quiz_file(show_final_list=False, time_limit={"per_question": 45})}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        assert start(port, cookies, "q.yaml", {"show_right_answer": False}).ok
        assert "let showFinalList = false" in page(port)
        user_id = register_student(port)
        assert 44 < question_start(port, user_id, 1)["remaining_seconds"] <= 45


def test_time_limit_null_turns_the_limit_off(temp_dir):
    quizzes = {"q.yaml": quiz_file(time_limit={"per_question": 30})}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        assert start(port, cookies, "q.yaml", {"time_limit": None}).ok
        user_id = register_student(port)
        assert question_start(port, user_id, 1) == {"status": "success"}


def test_restart_of_the_same_quiz_keeps_the_start_settings(temp_dir):
    """Saving the config restarts the running quiz; the start settings stay."""
    quizzes = {"q.yaml": quiz_file(show_right_answer=True)}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        assert start(port, cookies, "q.yaml", {"show_right_answer": False}).ok
        saved = requests.put(
            f"http://localhost:{port}/api/admin/config",
            cookies=cookies,
            json={"content": 'registration:\n  fields:\n    - "Grade"\n'},
        )
        assert saved.status_code == 200
        assert "let showRightAnswer = false" in page(port)


def test_another_quiz_without_settings_uses_its_file_values(temp_dir):
    quizzes = {"a.yaml": quiz_file(show_right_answer=True), "b.yaml": quiz_file(show_right_answer=True)}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        assert start(port, cookies, "a.yaml", {"show_right_answer": False}).ok
        assert start(port, cookies, "b.yaml").ok
        assert "let showRightAnswer = true" in page(port)


def test_invalid_start_settings_are_rejected_and_quiz_is_not_switched(temp_dir):
    quizzes = {"a.yaml": quiz_file(), "b.yaml": quiz_file()}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        assert start(port, cookies, "a.yaml").ok
        for bad in (
            {"show_right_answer": "no"},
            {"randomize_questions": 1},
            {"time_limit": {"per_question": -1}},
            {"time_limit": {"per_question": 5, "whole_quiz": 5}},
            {"title": "Not a start setting"},
        ):
            response = start(port, cookies, "b.yaml", bad)
            assert response.status_code == 400, bad
            assert response.json()["errors"], bad

        listing = requests.get(f"http://localhost:{port}/api/admin/list-quizzes", cookies=cookies).json()
        assert listing["current_quiz"] == "a.yaml"
