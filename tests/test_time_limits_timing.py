"""Tests for when question clocks start and the remaining time sent by question-start."""

import os
import re
import time

import requests
from conftest import custom_webquiz_server, get_admin_session, register_student


def question(text="Q?", **extra):
    return {"question": text, "options": ["A", "B"], "correct_answer": 0, **extra}


def question_start(port, user_id, question_id):
    response = requests.post(
        f"http://localhost:{port}/api/question-start", json={"user_id": user_id, "question_id": question_id}
    )
    assert response.status_code == 200
    return response.json()


def submit(port, user_id, question_id, answer):
    return requests.post(
        f"http://localhost:{port}/api/submit-answer",
        json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
    )


def test_first_question_clock_starts_at_question_start(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "questions": [question()]}}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        time.sleep(1.2)  # the page has not shown the question yet
        question_start(port, user_id, 1)
        response = submit(port, user_id, 1, 0)
        assert response.status_code == 200
        assert response.json()["time_taken"] < 1.0


def test_first_question_clock_starts_after_approval_at_question_start(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "questions": [question()]}}
    with custom_webquiz_server(config={"registration": {"approve": True}}, quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        cookies = get_admin_session(port)
        approve = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )
        assert approve.status_code == 200
        time.sleep(1.2)  # the student has not pressed "Check status" yet
        question_start(port, user_id, 1)
        response = submit(port, user_id, 1, 0)
        assert response.status_code == 200
        assert response.json()["time_taken"] < 1.0


def test_question_start_returns_remaining_and_reload_does_not_reset(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": {"per_question": 30}, "questions": [question()]}}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        first = question_start(port, user_id, 1)
        assert 29 < first["remaining_seconds"] <= 30
        assert "quiz_remaining_seconds" not in first

        time.sleep(1.1)
        again = question_start(port, user_id, 1)  # page reload sends question-start again
        assert again["remaining_seconds"] <= 29


def test_question_start_returns_quiz_remaining(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": {"whole_quiz": 600}, "questions": [question()]}}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        data = question_start(port, user_id, 1)
        assert 599 < data["quiz_remaining_seconds"] <= 600
        assert "remaining_seconds" not in data


def test_unlimited_question_has_no_remaining(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": {"per_question": 30}, "questions": [question(time_limit=0)]}}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        assert question_start(port, user_id, 1) == {"status": "success"}


def test_page_contains_time_limits(temp_dir):
    quizzes = {
        "q.yaml": {
            "title": "T",
            "time_limit": {"per_question": 60},
            "questions": [question("Q1?"), question("Q2?", time_limit=20)],
        }
    }
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        html = requests.get(f"http://localhost:{port}/").text
        assert re.search(r'"time_limit":\s*20', html)
        assert re.search(r'"time_limit":\s*60', html)
        assert "const quizTimeLimit = 0" in html


def test_page_contains_whole_quiz_time_limit(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": {"whole_quiz": 900}, "questions": [question()]}}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        html = requests.get(f"http://localhost:{port}/").text
        assert "const quizTimeLimit = 900" in html


def test_malformed_time_limit_loads_without_limits(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": "soon", "questions": [question()]}}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        assert question_start(port, user_id, 1) == {"status": "success"}
        html = requests.get(f"http://localhost:{port}/").text
        assert "const quizTimeLimit = 0" in html
