"""Tests for time limit rules when an answer is submitted."""

import asyncio
import csv
import json
import os
import time

import pytest
import requests
import websockets
from conftest import custom_webquiz_server, register_student

SHORT_GRACE = {"WEBQUIZ_TIME_LIMIT_GRACE_SECONDS": "0.5"}


def question(text="Q?", **extra):
    return {"question": text, "options": ["A", "B"], "correct_answer": 0, **extra}


def quiz(time_limit=None, questions=None, **settings):
    data = {"title": "Timed", "questions": questions or [question()], **settings}
    if time_limit is not None:
        data["time_limit"] = time_limit
    return {"timed.yaml": data}


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


def final_rows(port, user_id):
    data = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}").json()
    assert data["test_completed"] is True, data
    return data["final_results"]["test_results"]


def test_answer_within_grace_counts(temp_dir):
    with custom_webquiz_server(quizzes=quiz({"per_question": 1}), env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(1.2)  # after the limit, but inside the grace
        response = submit(port, user_id, 1, 0)
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is True
        assert "timed_out" not in data


def test_late_answer_is_stored_as_timeout(temp_dir):
    with custom_webquiz_server(quizzes=quiz({"per_question": 1}), env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(1.8)  # after the limit and the grace
        response = submit(port, user_id, 1, 0)
        assert response.status_code == 200
        data = response.json()
        assert data["timed_out"] is True
        assert data["is_correct"] is False

        rows = final_rows(port, user_id)
        assert rows[0]["selected_answer"] == ""
        assert rows[0]["timed_out"] is True


def test_empty_answer_on_limited_question_is_timeout(temp_dir):
    with custom_webquiz_server(quizzes=quiz({"per_question": 30})) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        response = submit(port, user_id, 1, None)
        assert response.status_code == 200
        assert response.json()["timed_out"] is True


def test_empty_answer_without_time_limit_is_rejected(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        assert submit(port, user_id, 1, None).status_code == 400


def test_empty_answer_on_unlimited_question_is_rejected(temp_dir):
    quizzes = quiz({"per_question": 30}, questions=[question(time_limit=0)])
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        assert submit(port, user_id, 1, "").status_code == 400


def test_empty_answer_skips_checker(temp_dir):
    text_question = {"question": "Type anything", "checker": "x = 1", "correct_value": ""}
    quizzes = quiz({"per_question": 30}, questions=[text_question], show_right_answer=True)
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        response = submit(port, user_id, 1, "")
        assert response.status_code == 200
        assert response.json()["is_correct"] is False


def test_answer_after_timeout_returns_stored_timeout(temp_dir):
    quizzes = quiz({"per_question": 30}, questions=[question("Q1?"), question("Q2?")], randomize_questions=True)
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        registration = requests.post(f"http://localhost:{port}/api/register", json={"username": "S"}).json()
        user_id = registration["user_id"]
        first_id = registration["question_order"][0]
        question_start(port, user_id, first_id)
        assert submit(port, user_id, first_id, None).json()["timed_out"] is True

        late = submit(port, user_id, first_id, 0)  # a real answer arrives after the timeout
        assert late.status_code == 200
        assert late.json()["timed_out"] is True


def test_whole_quiz_empty_answer_ends_quiz(temp_dir):
    quizzes = quiz({"whole_quiz": 600}, questions=[question("Q1?"), question("Q2?"), question("Q3?")])
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        response = submit(port, user_id, 1, None)
        assert response.status_code == 200
        assert response.json()["test_completed"] is True

        rows = final_rows(port, user_id)
        assert len(rows) == 3
        assert all(row["selected_answer"] == "" and row["timed_out"] is True for row in rows)
        assert rows[1]["time_taken"] == 0
        assert rows[2]["time_taken"] == 0


def test_whole_quiz_empty_answer_from_continue_screen(temp_dir):
    quizzes = quiz({"whole_quiz": 600}, questions=[question("Q1?"), question("Q2?"), question("Q3?")])
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        assert submit(port, user_id, 1, 0).status_code == 200
        # The student is on the "Continue" screen: Q2 was never opened
        response = submit(port, user_id, 2, None)
        assert response.status_code == 200
        assert response.json()["test_completed"] is True

        rows = final_rows(port, user_id)
        assert rows[0]["selected_answer"] == "A"
        assert not rows[0].get("timed_out")
        assert rows[1]["timed_out"] is True and rows[2]["timed_out"] is True


def test_whole_quiz_late_answer_ends_quiz(temp_dir):
    quizzes = quiz({"whole_quiz": 1}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(quizzes=quizzes, env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(1.8)
        data = submit(port, user_id, 1, 0).json()
        assert data["timed_out"] is True
        assert data["test_completed"] is True


def test_timeout_row_in_answers_csv(temp_dir):
    with custom_webquiz_server(quizzes=quiz({"per_question": 30})) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        assert submit(port, user_id, 1, None).json()["timed_out"] is True
        time.sleep(6)  # CSV files are written every 5 seconds

        csv_dir = os.path.join(temp_dir, f"data_{port}")
        answer_files = [
            name for name in os.listdir(csv_dir) if name.endswith(".csv") and not name.endswith(".users.csv")
        ]
        assert len(answer_files) == 1
        with open(os.path.join(csv_dir, answer_files[0]), encoding="utf-8") as f:
            rows = list(csv.reader(f))

        assert rows[0] == [
            "user_id",
            "question",
            "selected_answer",
            "correct_answer",
            "is_correct",
            "time_taken_seconds",
        ]
        assert rows[1][2] == ""
        assert rows[1][4] == "False"


@pytest.mark.asyncio
async def test_live_stats_gets_timeout_state(temp_dir):
    with custom_webquiz_server(quizzes=quiz({"per_question": 30})) as (proc, port):
        async with websockets.connect(f"ws://localhost:{port}/ws/live-stats") as websocket:
            await asyncio.wait_for(websocket.recv(), timeout=2.0)  # initial_state
            user_id = register_student(port)
            question_start(port, user_id, 1)
            submit(port, user_id, 1, None)

            states = []
            for _ in range(5):
                message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2.0))
                if message.get("type") == "state_update":
                    states.append(message["state"])
                if "timeout" in states:
                    break
            assert "timeout" in states


# ---- Requests sent by hand (not by the quiz page) must not avoid the limit ----


def test_answer_without_question_start_counts_from_registration(temp_dir):
    """Skipping question-start for the first question does not stop the clock."""
    with custom_webquiz_server(quizzes=quiz({"per_question": 1}), env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        time.sleep(1.8)  # no question-start is ever sent
        data = submit(port, user_id, 1, 0).json()
        assert data["timed_out"] is True


def test_answer_without_question_start_counts_from_previous_answer(temp_dir):
    """Skipping question-start for a later question does not stop the clock."""
    quizzes = quiz({"per_question": 1}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(quizzes=quizzes, env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        assert submit(port, user_id, 1, 0).status_code == 200
        time.sleep(1.8)  # no question-start for Q2
        data = submit(port, user_id, 2, 0).json()
        assert data["timed_out"] is True


def test_continue_screen_time_still_not_counted(temp_dir):
    """The quiz page sends question-start, so time on the Continue screen does not count."""
    quizzes = quiz({"per_question": 1}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(quizzes=quizzes, env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        assert submit(port, user_id, 1, 0).status_code == 200
        time.sleep(1.8)  # the student stays on the Continue screen
        question_start(port, user_id, 2)
        data = submit(port, user_id, 2, 0).json()
        assert "timed_out" not in data


def test_whole_quiz_without_question_start_counts_from_registration(temp_dir):
    quizzes = quiz({"whole_quiz": 1}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(quizzes=quizzes, env=SHORT_GRACE) as (proc, port):
        user_id = register_student(port)
        time.sleep(1.8)  # no question-start is ever sent
        data = submit(port, user_id, 1, 0).json()
        assert data["timed_out"] is True
        assert data["test_completed"] is True


def test_question_start_with_unknown_question_is_rejected(temp_dir):
    with custom_webquiz_server(quizzes=quiz({"per_question": 30})) as (proc, port):
        user_id = register_student(port)
        response = requests.post(
            f"http://localhost:{port}/api/question-start", json={"user_id": user_id, "question_id": 999}
        )
        assert response.status_code == 404


def test_question_start_for_a_later_question_does_not_block_the_open_clock(temp_dir):
    quizzes = quiz({"per_question": 30}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 2)  # not the student's question yet
        question_start(port, user_id, 1)
        time.sleep(1.1)
        assert question_start(port, user_id, 1)["remaining_seconds"] <= 29  # Q1's clock is running


def test_answer_to_another_question_does_not_stop_the_open_clock(temp_dir):
    quizzes = quiz({"per_question": 30}, questions=[question("Q1?"), question("Q2?"), question("Q3?")])
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        time.sleep(1.1)
        assert submit(port, user_id, 2, 0).status_code == 200  # no order check without randomization
        assert question_start(port, user_id, 1)["remaining_seconds"] <= 29  # Q1's clock still runs
