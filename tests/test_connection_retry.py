"""Tests for repeated student requests after a connection drop.

The quiz page retries a request when the connection drops. When the server already
handled the first attempt and only the response was lost, the retry must not record a
second answer or register a second user.
"""

import time

import requests

from conftest import custom_webquiz_server, get_admin_session


THREE_QUESTIONS = {
    "title": "Retry Quiz",
    "questions": [
        {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
        {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
    ],
}


def register(port, username="student", **extra):
    response = requests.post(f"http://localhost:{port}/api/register", json={"username": username, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def submit(port, user_id, question_id, answer):
    return requests.post(
        f"http://localhost:{port}/api/submit-answer",
        json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
    )


def verify(port, user_id):
    response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
    assert response.status_code == 200
    return response.json()


def test_repeated_answer_returns_stored_result(temp_dir):
    """The same answer sent twice is recorded once and the retry gets the first result."""
    with custom_webquiz_server(quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        user_id = register(port)["user_id"]

        first = submit(port, user_id, 1, 0)
        assert first.status_code == 200
        time.sleep(0.2)
        retry = submit(port, user_id, 1, 0)
        assert retry.status_code == 200
        assert retry.json() == first.json(), "Retry must return the stored result, including time_taken"

        # The repeated answer must not count as a second answer
        assert submit(port, user_id, 2, 1).status_code == 200
        data = verify(port, user_id)
        assert data["test_completed"] is False, "Quiz must not be completed early by a repeated answer"
        assert data["next_question_index"] == 2

        assert submit(port, user_id, 3, 0).status_code == 200
        data = verify(port, user_id)
        assert data["test_completed"] is True
        results = data["final_results"]
        assert results["total_count"] == 3
        assert results["correct_count"] == 3
        assert [r["question"] for r in results["test_results"]] == ["Q1", "Q2", "Q3"]


def test_different_answer_to_answered_question_rejected(temp_dir):
    """A new answer to an already answered question is not accepted and does not replace the first one."""
    with custom_webquiz_server(quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        user_id = register(port)["user_id"]

        assert submit(port, user_id, 1, 0).status_code == 200
        response = submit(port, user_id, 1, 1)
        assert response.status_code == 409
        assert "error" in response.json()

        assert verify(port, user_id)["next_question_index"] == 1

        submit(port, user_id, 2, 1)
        submit(port, user_id, 3, 0)
        results = verify(port, user_id)["final_results"]
        assert results["total_count"] == 3
        assert results["test_results"][0]["is_correct"] is True, "First answer must stay recorded"


def test_repeated_text_answer_returns_stored_result(temp_dir):
    """Text answers are compared as sent, so a retry of the same text gets the stored result."""
    quiz = {
        "title": "Text Retry",
        "questions": [
            {"question": "Type 42", "checker": "assert to_int(user_answer) == 42", "correct_value": "42"},
            {"question": "Q2", "options": ["A", "B"], "correct_answer": 0},
        ],
    }
    with custom_webquiz_server(quizzes={"quiz.yaml": quiz}) as (proc, port):
        user_id = register(port)["user_id"]

        first = submit(port, user_id, 1, "41")
        retry = submit(port, user_id, 1, "41")
        assert retry.status_code == 200
        assert retry.json() == first.json()
        assert retry.json()["is_correct"] is False

        assert submit(port, user_id, 1, "42").status_code == 409


def test_repeated_answer_with_randomization(temp_dir):
    """With randomized order a retry of the answered question no longer fails with 403."""
    quiz = {**THREE_QUESTIONS, "randomize_questions": True}
    with custom_webquiz_server(quizzes={"quiz.yaml": quiz}) as (proc, port):
        data = register(port)
        user_id = data["user_id"]
        order = data["question_order"]

        first = submit(port, user_id, order[0], 0)
        retry = submit(port, user_id, order[0], 0)
        assert retry.status_code == 200
        assert retry.json() == first.json()
        assert verify(port, user_id)["next_question_index"] == 1


def test_repeated_last_answer_after_completion(temp_dir):
    """A retry of the last answer after the quiz is completed gets the stored result."""
    quiz = {**THREE_QUESTIONS, "randomize_questions": True}
    with custom_webquiz_server(quizzes={"quiz.yaml": quiz}) as (proc, port):
        data = register(port)
        user_id = data["user_id"]
        order = data["question_order"]

        last = None
        for question_id in order:
            last = submit(port, user_id, question_id, 0)
            assert last.status_code == 200

        retry = submit(port, user_id, order[-1], 0)
        assert retry.status_code == 200
        assert retry.json() == last.json()
        assert verify(port, user_id)["final_results"]["total_count"] == 3


def test_repeated_answer_with_hidden_feedback(temp_dir):
    """With show_right_answer: false the stored result also hides correctness."""
    quiz = {**THREE_QUESTIONS, "show_right_answer": False}
    with custom_webquiz_server(quizzes={"quiz.yaml": quiz}) as (proc, port):
        user_id = register(port)["user_id"]

        submit(port, user_id, 1, 1)
        retry = submit(port, user_id, 1, 1)
        assert retry.status_code == 200
        assert "is_correct" not in retry.json()


def test_late_question_start_for_answered_question_is_ignored(temp_dir):
    """A question-start notice that arrives after the answer must not start timing for the next question."""
    with custom_webquiz_server(quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        user_id = register(port)["user_id"]
        url = f"http://localhost:{port}/api/question-start"

        assert submit(port, user_id, 1, 0).status_code == 200
        # Late retry of the notice for the question that is already answered
        response = requests.post(url, json={"user_id": user_id, "question_id": 1})
        assert response.status_code == 200

        time.sleep(1.5)
        requests.post(url, json={"user_id": user_id, "question_id": 2})
        response = submit(port, user_id, 2, 1)
        assert response.json()["time_taken"] < 1, "Timing for question 2 must start at its own notice"


def test_question_start_unknown_user_returns_404(temp_dir):
    """A question-start notice for a user the server does not know is a 404, not a server error."""
    with custom_webquiz_server(quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        response = requests.post(
            f"http://localhost:{port}/api/question-start", json={"user_id": "000000", "question_id": 1}
        )
        assert response.status_code == 404


def test_repeated_registration_returns_same_user(temp_dir):
    """A registration retried with the same token returns the user created by the first attempt."""
    with custom_webquiz_server(quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        first = register(port, "anna", registration_token="token-1")
        retry = register(port, "anna", registration_token="token-1")
        assert retry["user_id"] == first["user_id"]
        assert retry["username"] == "anna"
        assert retry["approved"] is True


def test_registration_token_does_not_bypass_unique_username(temp_dir):
    """Another token, or no token, still cannot take a username that is in use."""
    with custom_webquiz_server(quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        register(port, "anna", registration_token="token-1")

        url = f"http://localhost:{port}/api/register"
        response = requests.post(url, json={"username": "anna", "registration_token": "token-2"})
        assert response.status_code == 400
        response = requests.post(url, json={"username": "anna"})
        assert response.status_code == 400


def test_repeated_registration_keeps_question_order(temp_dir):
    """A retried registration returns the question order generated the first time."""
    quiz = {**THREE_QUESTIONS, "randomize_questions": True}
    with custom_webquiz_server(quizzes={"quiz.yaml": quiz}) as (proc, port):
        first = register(port, "anna", registration_token="token-1")
        retry = register(port, "anna", registration_token="token-1")
        assert retry["question_order"] == first["question_order"]


def test_repeated_registration_with_approval(temp_dir):
    """A retried registration reports the current approval state of the existing user."""
    config = {"registration": {"approve": True}}
    with custom_webquiz_server(config=config, quizzes={"quiz.yaml": THREE_QUESTIONS}) as (proc, port):
        first = register(port, "anna", registration_token="token-1")
        assert first["requires_approval"] is True
        assert first["approved"] is False

        retry = register(port, "anna", registration_token="token-1")
        assert retry["user_id"] == first["user_id"]
        assert retry["approved"] is False

        cookies = get_admin_session(port)
        requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": first["user_id"]}
        )
        retry = register(port, "anna", registration_token="token-1")
        assert retry["approved"] is True
