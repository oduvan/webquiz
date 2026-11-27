"""Tests for text questions that the teacher checks by hand (manual_check: true).

The student's answer waits in a review queue. Teachers open the review page,
which is fed over WS /ws/review, and mark each answer right or wrong.
"""

import asyncio
import csv
import glob
import json
import os
import time

import pytest
import requests
import websockets
from websockets.exceptions import InvalidStatus

from conftest import custom_webquiz_server, get_admin_session, register_student

MANUAL_QUIZ = {
    "title": "Manual Check Quiz",
    "show_right_answer": True,
    "questions": [
        {
            "question": "Why is the sky blue?",
            "manual_check": True,
            "correct_value": "Rayleigh scattering",
            "points": 2,
        },
        {"question": "2 + 2?", "options": ["3", "4"], "correct_answer": 1},
        {"question": "Name a prime number", "manual_check": True},
    ],
}


def manual_server(quiz=None, config=None):
    return custom_webquiz_server(quizzes={"manual.yaml": quiz or MANUAL_QUIZ}, config=config)


def submit(port, user_id, question_id, answer):
    return requests.post(
        f"http://localhost:{port}/api/submit-answer",
        json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
    )


def final_results(port, user_id):
    data = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}").json()
    assert data["test_completed"], data
    return data["final_results"]


def cookie_header(port):
    cookies = get_admin_session(port)
    return {"Cookie": f"admin_session={cookies['admin_session']}"}


async def connect_review(port):
    return await websockets.connect(f"ws://localhost:{port}/ws/review", additional_headers=cookie_header(port))


async def recv(ws, timeout=3.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))


async def recv_state(ws, predicate=lambda state: True, timeout=3.0):
    """Read messages until a review_state that matches predicate arrives."""
    deadline = time.monotonic() + timeout
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise AssertionError("no matching review_state")
        message = await recv(ws, left)
        if message.get("type") == "review_state" and predicate(message):
            return message


async def take_shared(ws):
    await ws.send(json.dumps({"type": "take_shared"}))


async def send_verdict(ws, review_id, is_correct):
    await ws.send(json.dumps({"type": "verdict", "review_id": review_id, "is_correct": is_correct}))


# ---------------------------------------------------------------------------
# Quiz validation
# ---------------------------------------------------------------------------


def validate(port, quiz):
    import yaml

    cookies = get_admin_session(port)
    response = requests.post(
        f"http://localhost:{port}/api/admin/validate-quiz",
        json={"content": yaml.dump(quiz, allow_unicode=True)},
        cookies=cookies,
    )
    assert response.status_code == 200
    return response.json()


def one_question_quiz(question):
    return {"title": "T", "questions": [question]}


def test_manual_question_without_checker_is_valid():
    with manual_server() as (proc, port):
        result = validate(port, one_question_quiz({"question": "Q", "manual_check": True}))
        assert result["valid"], result


def test_manual_check_must_be_boolean():
    with manual_server() as (proc, port):
        result = validate(port, one_question_quiz({"question": "Q", "manual_check": "yes", "checker": ""}))
        assert not result["valid"]
        assert any("manual_check" in error for error in result["errors"])


def test_manual_check_with_checker_code_is_refused():
    with manual_server() as (proc, port):
        result = validate(
            port, one_question_quiz({"question": "Q", "manual_check": True, "checker": "assert user_answer"})
        )
        assert not result["valid"]
        assert any("manual_check" in error and "checker" in error for error in result["errors"])


def test_manual_check_with_options_is_refused():
    with manual_server() as (proc, port):
        result = validate(
            port,
            one_question_quiz({"question": "Q", "manual_check": True, "options": ["a", "b"], "correct_answer": 0}),
        )
        assert not result["valid"]
        assert any("manual_check" in error for error in result["errors"])


def test_manual_check_false_keeps_choice_question():
    with manual_server() as (proc, port):
        result = validate(
            port,
            one_question_quiz({"question": "Q", "manual_check": False, "options": ["a", "b"], "correct_answer": 0}),
        )
        assert result["valid"], result


def test_manual_question_is_a_text_question_on_the_page():
    with manual_server() as (proc, port):
        page = requests.get(f"http://localhost:{port}/").text
        assert '"type": "text"' in page
        # The sample answer for the teacher never reaches the student page
        assert "Rayleigh scattering" not in page


# ---------------------------------------------------------------------------
# Student answers
# ---------------------------------------------------------------------------


def test_submit_reply_says_the_answer_waits_for_the_teacher():
    with manual_server() as (proc, port):
        user_id = register_student(port)
        response = submit(port, user_id, 1, "Light scatters")
        assert response.status_code == 200
        data = response.json()
        assert data["pending_review"] is True
        assert data["is_text_question"] is True
        assert "is_correct" not in data
        assert "correct_value" not in data
        assert "checker_error" not in data


def test_submit_reply_without_show_right_answer():
    quiz = dict(MANUAL_QUIZ, show_right_answer=False)
    with manual_server(quiz) as (proc, port):
        user_id = register_student(port)
        data = submit(port, user_id, 1, "Light scatters").json()
        assert data["pending_review"] is True
        assert "is_correct" not in data


def test_repeated_submit_returns_the_same_reply():
    with manual_server() as (proc, port):
        user_id = register_student(port)
        first = submit(port, user_id, 1, "Light scatters").json()
        second = submit(port, user_id, 1, "Light scatters").json()
        assert first == second
        assert submit(port, user_id, 1, "Other").status_code == 409


def test_empty_answer_to_manual_question_is_refused():
    with manual_server() as (proc, port):
        user_id = register_student(port)
        assert submit(port, user_id, 1, "").status_code == 400


def test_final_results_show_waiting_answers():
    with manual_server() as (proc, port):
        user_id = register_student(port)
        submit(port, user_id, 1, "Light scatters")
        submit(port, user_id, 2, 1)
        submit(port, user_id, 3, "7")
        results = final_results(port, user_id)
        assert results["pending_count"] == 2
        assert results["correct_count"] == 1
        assert results["earned_points"] == 1
        assert results["total_points"] == 4
        rows = results["test_results"]
        assert rows[0]["pending_review"] is True
        assert rows[0]["is_correct"] is None
        assert rows[0]["earned_points"] == 0
        assert "pending_review" not in rows[1]
        assert rows[2]["pending_review"] is True


def test_final_results_keep_pending_mark_when_answers_are_hidden():
    quiz = dict(MANUAL_QUIZ, show_right_answer=False)
    with manual_server(quiz) as (proc, port):
        user_id = register_student(port)
        submit(port, user_id, 1, "Light scatters")
        submit(port, user_id, 2, 1)
        submit(port, user_id, 3, "7")
        results = final_results(port, user_id)
        assert results["pending_count"] == 2
        assert "is_correct" not in results["test_results"][0]
        assert results["test_results"][0]["pending_review"] is True


# ---------------------------------------------------------------------------
# Review page and WebSocket
# ---------------------------------------------------------------------------


def test_review_page_is_served():
    with manual_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/review/")
        assert response.status_code == 200
        assert "text/html" in response.headers["Content-Type"]
        assert "/ws/review" in response.text


@pytest.mark.asyncio
async def test_review_websocket_needs_admin_session():
    with manual_server() as (proc, port):
        with pytest.raises(InvalidStatus) as error:
            async with websockets.connect(f"ws://localhost:{port}/ws/review"):
                pass
        assert error.value.response.status_code == 401


@pytest.mark.asyncio
async def test_review_websocket_trusted_ip_needs_no_session():
    with manual_server(config={"admin": {"trusted_ips": ["127.0.0.1"]}}) as (proc, port):
        async with websockets.connect(f"ws://localhost:{port}/ws/review") as ws:
            state = await recv_state(ws)
            assert state["item"] is None


@pytest.mark.asyncio
async def test_reviewer_gets_answer_without_student_name():
    with manual_server() as (proc, port):
        async with await connect_review(port) as ws:
            state = await recv_state(ws)
            assert state == {
                "type": "review_state",
                "item": None,
                "pending_count": 0,
                "has_manual": True,
                "already_decided": False,
            }

            user_id = register_student(port, "Secret Name")
            submit(port, user_id, 1, "Light scatters")
            state = await recv_state(ws, lambda s: s["item"] is not None)
            item = state["item"]
            assert item["question"] == "Why is the sky blue?"
            assert item["answer"] == "Light scatters"
            assert item["correct_value"] == "Rayleigh scattering"
            assert item["points"] == 2
            assert state["pending_count"] == 1
            raw = json.dumps(state)
            assert "Secret Name" not in raw
            assert user_id not in raw


@pytest.mark.asyncio
async def test_verdict_updates_student_results():
    with manual_server() as (proc, port):
        async with await connect_review(port) as ws:
            await recv_state(ws)
            user_id = register_student(port)
            submit(port, user_id, 1, "Light scatters")
            submit(port, user_id, 2, 1)
            submit(port, user_id, 3, "7")

            state = await recv_state(ws, lambda s: s["item"] is not None)
            assert state["item"]["answer"] == "Light scatters"
            await send_verdict(ws, state["item"]["review_id"], True)

            state = await recv_state(ws, lambda s: s["item"] is not None and s["item"]["answer"] == "7")
            assert state["pending_count"] == 1
            results = final_results(port, user_id)
            assert results["pending_count"] == 1
            assert results["test_results"][0]["is_correct"] is True
            assert "pending_review" not in results["test_results"][0]
            assert results["earned_points"] == 3
            assert results["correct_count"] == 2

            await send_verdict(ws, state["item"]["review_id"], False)
            state = await recv_state(ws, lambda s: s["item"] is None)
            assert state["pending_count"] == 0
            results = final_results(port, user_id)
            assert results["pending_count"] == 0
            assert results["test_results"][2]["is_correct"] is False
            assert results["earned_points"] == 3


@pytest.mark.asyncio
async def test_verdict_that_is_not_boolean_is_ignored():
    with manual_server() as (proc, port):
        async with await connect_review(port) as ws:
            await recv_state(ws)
            user_id = register_student(port)
            submit(port, user_id, 1, "Light scatters")
            state = await recv_state(ws, lambda s: s["item"] is not None)
            await send_verdict(ws, state["item"]["review_id"], "yes")
            again = await recv_state(ws)
            assert again["item"] == state["item"]
            assert again["pending_count"] == 1


@pytest.mark.asyncio
async def test_two_reviewers_get_different_answers():
    with manual_server() as (proc, port):
        async with await connect_review(port) as first, await connect_review(port) as second:
            await recv_state(first)
            await recv_state(second)
            submit(port, register_student(port, "A"), 1, "answer A")
            submit(port, register_student(port, "B"), 1, "answer B")
            await asyncio.sleep(0.5)

            async def latest_item(ws):
                item = None
                while True:
                    try:
                        message = await recv(ws, 0.5)
                    except asyncio.TimeoutError:
                        return item
                    if message["type"] == "review_state":
                        item = message["item"]

            first_item = await latest_item(first)
            second_item = await latest_item(second)
            assert {first_item["answer"], second_item["answer"]} == {"answer A", "answer B"}


@pytest.mark.asyncio
async def test_first_verdict_wins_when_two_reviewers_see_the_same_answer():
    with manual_server() as (proc, port):
        async with await connect_review(port) as first:
            await recv_state(first)
            user_id = register_student(port)
            submit(port, user_id, 1, "Light scatters")
            first_state = await recv_state(first, lambda s: s["item"] is not None)

            async with await connect_review(port) as second:
                second_state = await recv_state(second)
                # The only waiting answer is open on the first page, so the second page waits
                assert second_state["item"] is None
                assert second_state["pending_count"] == 1
                # The teacher asks to help and gets the same answer
                await take_shared(second)
                second_state = await recv_state(second, lambda s: s["item"] is not None)
                assert second_state["item"]["review_id"] == first_state["item"]["review_id"]

                await send_verdict(first, first_state["item"]["review_id"], False)
                assert (await recv_state(first, lambda s: s["pending_count"] == 0))["item"] is None
                # The other page moves on by itself
                assert (await recv_state(second, lambda s: s["item"] is None))["pending_count"] == 0

                await send_verdict(second, second_state["item"]["review_id"], True)
                late = await recv_state(second)
                assert late["already_decided"] is True
                assert late["item"] is None

            submit(port, user_id, 2, 1)
            submit(port, user_id, 3, "7")
            assert final_results(port, user_id)["test_results"][0]["is_correct"] is False


@pytest.mark.asyncio
async def test_answer_of_closed_page_goes_to_waiting_page():
    with manual_server() as (proc, port):
        async with await connect_review(port) as first:
            await recv_state(first)
            submit(port, register_student(port, "A"), 1, "answer A")
            submit(port, register_student(port, "B"), 1, "answer B")
            state = await recv_state(first, lambda s: s["item"] is not None)
            assert state["item"]["answer"] == "answer A"

            async with await connect_review(port) as second:
                second_state = await recv_state(second)
                assert second_state["item"]["answer"] == "answer B"
                await send_verdict(second, second_state["item"]["review_id"], True)
                # Answer A is open on the first page, so the second page waits ...
                waiting = await recv_state(second, lambda s: s["pending_count"] == 1)
                assert waiting["item"] is None
                # ... until the teacher asks to help
                await take_shared(second)
                shared = await recv_state(second, lambda s: s["item"] is not None)
                assert shared["item"]["answer"] == "answer A"

        async with await connect_review(port) as third:
            state = await recv_state(third)
            assert state["item"]["answer"] == "answer A"


@pytest.mark.asyncio
async def test_quiz_restart_clears_the_queue():
    with manual_server() as (proc, port):
        async with await connect_review(port) as ws:
            await recv_state(ws)
            submit(port, register_student(port), 1, "Light scatters")
            await recv_state(ws, lambda s: s["item"] is not None)

            cookies = get_admin_session(port)
            response = requests.post(
                f"http://localhost:{port}/api/admin/switch-quiz",
                json={"quiz_filename": "manual.yaml"},
                cookies=cookies,
            )
            assert response.status_code == 200
            state = await recv_state(ws, lambda s: s["item"] is None)
            assert state["pending_count"] == 0
            assert state["has_manual"] is True


@pytest.mark.asyncio
async def test_has_manual_is_false_for_quiz_without_manual_questions():
    quiz = {"title": "Plain", "questions": [{"question": "Q", "options": ["a", "b"], "correct_answer": 0}]}
    with manual_server(quiz) as (proc, port):
        async with await connect_review(port) as ws:
            state = await recv_state(ws)
            assert state["has_manual"] is False


@pytest.mark.asyncio
async def test_admin_websocket_reports_review_status():
    with manual_server() as (proc, port):
        async with websockets.connect(f"ws://localhost:{port}/ws/admin") as admin_ws:
            initial = await recv(admin_ws)
            assert initial["review"] == {"has_manual": True, "pending_count": 0, "reviewers": 0}

            async with await connect_review(port) as review_ws:
                await recv_state(review_ws)
                submit(port, register_student(port), 1, "Light scatters")

                deadline = time.monotonic() + 3
                status = None
                while time.monotonic() < deadline:
                    message = await recv(admin_ws)
                    if message["type"] == "review_status" and message["pending_count"] == 1:
                        status = message
                        break
                assert status == {"type": "review_status", "has_manual": True, "pending_count": 1, "reviewers": 1}


@pytest.mark.asyncio
async def test_live_stats_show_pending_then_verdict():
    with manual_server() as (proc, port):
        async with websockets.connect(f"ws://localhost:{port}/ws/live-stats") as stats_ws:
            await recv(stats_ws)
            async with await connect_review(port) as review_ws:
                await recv_state(review_ws)
                user_id = register_student(port)
                submit(port, user_id, 1, "Light scatters")

                async def next_state_update():
                    while True:
                        message = await recv(stats_ws)
                        if message["type"] == "state_update" and message["state"] != "think":
                            return message

                pending = await next_state_update()
                assert pending["question_id"] == 1
                assert pending["state"] == "pending"
                assert pending["earned_points"] == 0

                state = await recv_state(review_ws, lambda s: s["item"] is not None)
                await send_verdict(review_ws, state["item"]["review_id"], True)
                decided = await next_state_update()
                assert decided["question_id"] == 1
                assert decided["user_id"] == user_id
                assert decided["state"] == "ok"
                assert decided["earned_points"] == 2


# ---------------------------------------------------------------------------
# CSV files
# ---------------------------------------------------------------------------


def read_csv(pattern):
    files = [f for f in glob.glob(pattern) if not f.endswith(".users.csv")]
    assert len(files) == 1, files
    with open(files[0], newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.asyncio
async def test_csv_row_is_rewritten_after_verdict():
    config = {"extra_answers_with_users_csv": True}
    with manual_server(config=config) as (proc, port):
        csv_dir = f"data_{port}"
        async with await connect_review(port) as ws:
            await recv_state(ws)
            user_id = register_student(port)
            submit(port, user_id, 1, "Light scatters")
            submit(port, user_id, 2, 1)
            time.sleep(6)

            rows = read_csv(f"{csv_dir}/manual_*[0-9].csv")
            assert [row["is_correct"] for row in rows] == ["", "True"]
            joined = read_csv(f"{csv_dir}/manual_*.answers_with_users.csv")
            assert [row["is_correct"] for row in joined] == ["", "True"]

            state = await recv_state(ws, lambda s: s["item"] is not None)
            await send_verdict(ws, state["item"]["review_id"], True)
            await recv_state(ws, lambda s: s["item"] is None)
            submit(port, user_id, 3, "7")
            time.sleep(6)

            rows = read_csv(f"{csv_dir}/manual_*[0-9].csv")
            assert [row["selected_answer"] for row in rows] == ["Light scatters", "4", "7"]
            assert [row["is_correct"] for row in rows] == ["True", "True", ""]
            joined = read_csv(f"{csv_dir}/manual_*.answers_with_users.csv")
            assert [row["is_correct"] for row in joined] == ["True", "True", ""]

            users = list(csv.DictReader(open(glob.glob(f"{csv_dir}/manual_*.users.csv")[0], encoding="utf-8")))
            assert users[0]["correct_answers"] == "2"
            assert users[0]["earned_points"] == "3"
            assert os.path.exists(csv_dir)


def test_texts_never_say_teacher():
    """Students and review pages see "manual verification", never a "teacher"."""
    from webquiz.translations import TRANSLATIONS

    for language, texts in TRANSLATIONS.items():
        for key, text in texts.items():
            if key.startswith(("pending_review", "review_")):
                lowered = text.lower()
                assert "teacher" not in lowered and "вчител" not in lowered and "учител" not in lowered, (
                    language,
                    key,
                )
