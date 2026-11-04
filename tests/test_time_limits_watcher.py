"""Tests for the background check that times out students whose page went quiet."""

import time

import requests
from conftest import custom_webquiz_server, get_admin_session, register_student

FAST = {"WEBQUIZ_TIME_LIMIT_GRACE_SECONDS": "0.3", "WEBQUIZ_TIME_LIMIT_CHECK_INTERVAL": "0.2"}


def question(text="Q?", **extra):
    return {"question": text, "options": ["A", "B"], "correct_answer": 0, **extra}


def question_start(port, user_id, question_id):
    response = requests.post(
        f"http://localhost:{port}/api/question-start", json={"user_id": user_id, "question_id": question_id}
    )
    assert response.status_code == 200


def verify(port, user_id):
    return requests.get(f"http://localhost:{port}/api/verify-user/{user_id}").json()


def test_quiet_student_gets_timeout(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": {"per_question": 1}, "questions": [question(), question()]}}
    with custom_webquiz_server(quizzes=quizzes, env=FAST) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(2)  # the page sends nothing
        data = verify(port, user_id)
        assert data["next_question_index"] == 1
        assert data["test_completed"] is False


def test_next_question_clock_does_not_start_on_its_own(temp_dir):
    quizzes = {"q.yaml": {"title": "T", "time_limit": {"per_question": 1}, "questions": [question(), question()]}}
    with custom_webquiz_server(quizzes=quizzes, env=FAST) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(2)
        assert verify(port, user_id)["next_question_index"] == 1
        time.sleep(2)  # question 2 was never shown, so it must not time out
        assert verify(port, user_id)["next_question_index"] == 1


def test_whole_quiz_ends_for_quiet_student_in_student_order(temp_dir):
    quizzes = {
        "q.yaml": {
            "title": "T",
            "time_limit": {"whole_quiz": 1},
            "randomize_questions": True,
            "questions": [question("Q1?"), question("Q2?"), question("Q3?")],
        }
    }
    with custom_webquiz_server(quizzes=quizzes, env=FAST) as (proc, port):
        registration = requests.post(f"http://localhost:{port}/api/register", json={"username": "S"}).json()
        user_id = registration["user_id"]
        order = registration["question_order"]
        question_start(port, user_id, order[0])
        time.sleep(2)

        data = verify(port, user_id)
        assert data["test_completed"] is True
        rows = data["final_results"]["test_results"]
        assert [row["question"] for row in rows] == [f"Q{question_id}?" for question_id in order]
        assert all(row["timed_out"] is True and row["selected_answer"] == "" for row in rows)


def test_whole_quiz_timeouts_complete_the_class(temp_dir):
    quizzes = {
        "q.yaml": {
            "title": "T",
            "time_limit": {"whole_quiz": 1},
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [question(), question()],
        }
    }
    with custom_webquiz_server(quizzes=quizzes, env=FAST) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(2)
        data = verify(port, user_id)
        assert data["test_completed"] is True
        assert data["final_results"]["all_completed"] is True


def test_quiz_switch_while_clock_runs(temp_dir):
    quizzes = {
        "a.yaml": {"title": "A", "time_limit": {"per_question": 1}, "questions": [question()]},
        "b.yaml": {"title": "B", "time_limit": {"per_question": 1}, "questions": [question()]},
    }
    with custom_webquiz_server(quizzes=quizzes, env=FAST) as (proc, port):
        cookies = get_admin_session(port)

        def switch_to(filename):
            response = requests.post(
                f"http://localhost:{port}/api/admin/switch-quiz", cookies=cookies, json={"quiz_filename": filename}
            )
            assert response.status_code == 200

        switch_to("a.yaml")  # with two quiz files no quiz is active until the admin picks one
        user_id = register_student(port)
        question_start(port, user_id, 1)
        switch_to("b.yaml")
        time.sleep(1.5)

        assert proc.poll() is None
        assert verify(port, user_id)["valid"] is False  # the old student is gone
        new_user = register_student(port, "NewStudent")
        assert verify(port, new_user)["valid"] is True
