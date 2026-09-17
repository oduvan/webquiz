"""
Integration tests for decimal (floating point) question points.

Points may be a number with at most two decimal places, e.g. 0.5, 1.25, 2.75.
"""

import pytest
import requests
import asyncio
import websockets
import json
import csv
import os
import glob
import time
from tests.conftest import custom_webquiz_server, get_admin_session


@pytest.fixture
def decimal_points_server():
    """Server with questions worth 0.5, 1.25 and 2.25 points (total 4)."""
    quiz_data = {
        "title": "Decimal Points Quiz",
        "show_right_answer": True,
        "questions": [
            {"question": "Half a point", "options": ["A", "B"], "correct_answer": 0, "points": 0.5},
            {"question": "One and a quarter", "options": ["A", "B"], "correct_answer": 1, "points": 1.25},
            {"question": "Two and a quarter", "options": ["A", "B"], "correct_answer": 0, "points": 2.25},
        ],
    }

    with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
        yield proc, port


@pytest.fixture
def inexact_points_server():
    """Server whose points are not exact in binary floating point (0.1 + 0.2 + 0.7)."""
    quiz_data = {
        "title": "Inexact Points Quiz",
        "show_right_answer": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 0.1},
            {"question": "Q2", "options": ["A", "B"], "correct_answer": 0, "points": 0.2},
            {"question": "Q3", "options": ["A", "B"], "correct_answer": 0, "points": 0.7},
        ],
    }

    with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
        yield proc, port


def _create_quiz(base_url, cookies, filename, quiz_data):
    return requests.post(
        f"{base_url}/api/admin/create-quiz",
        json={"filename": filename, "quiz_data": quiz_data},
        cookies=cookies,
    )


def _quiz_with_points(points):
    return {
        "title": "Points Quiz",
        "questions": [{"question": "Test question", "options": ["A", "B"], "correct_answer": 0, "points": points}],
    }


class TestDecimalPointsScoring:
    """Decimal points are served to the client and scored correctly."""

    def test_decimal_points_sent_to_client(self, decimal_points_server):
        """Decimal point values reach the client in the embedded questions JSON."""
        proc, port = decimal_points_server

        content = requests.get(f"http://localhost:{port}/").text

        assert '"points": 0.5' in content or '"points":0.5' in content
        assert '"points": 1.25' in content or '"points":1.25' in content
        assert '"points": 2.25' in content or '"points":2.25' in content

    def test_all_correct_earns_decimal_total(self, decimal_points_server):
        """Answering everything correctly earns the exact decimal total."""
        proc, port = decimal_points_server
        base_url = f"http://localhost:{port}"

        user_id = requests.post(f"{base_url}/api/register", json={"username": "decimal_all"}).json()["user_id"]

        for question_id, answer in [(1, 0), (2, 1), (3, 0)]:
            response = requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
            )
            assert response.status_code == 200
            assert response.json()["is_correct"] is True

        final_results = requests.get(f"{base_url}/api/verify-user/{user_id}").json()["final_results"]

        assert final_results["total_points"] == 4
        assert final_results["earned_points"] == 4
        assert final_results["points_percentage"] == 100

    def test_partial_score_has_no_float_noise(self, decimal_points_server):
        """A partial decimal score is exact, not 1.7500000000000002."""
        proc, port = decimal_points_server
        base_url = f"http://localhost:{port}"

        user_id = requests.post(f"{base_url}/api/register", json={"username": "decimal_part"}).json()["user_id"]

        # Correct: 0.5 + 1.25 = 1.75. Third question answered wrong.
        for question_id, answer in [(1, 0), (2, 1), (3, 1)]:
            requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
            )

        final_results = requests.get(f"{base_url}/api/verify-user/{user_id}").json()["final_results"]

        assert final_results["earned_points"] == 1.75
        assert final_results["total_points"] == 4
        # 1.75 / 4 = 43.75% -> rounded to 44
        assert final_results["points_percentage"] == 44

    def test_sum_of_inexact_points_is_rounded(self, inexact_points_server):
        """0.1 + 0.2 must score as 0.3, not 0.30000000000000004."""
        proc, port = inexact_points_server
        base_url = f"http://localhost:{port}"

        user_id = requests.post(f"{base_url}/api/register", json={"username": "inexact"}).json()["user_id"]

        # First two correct (0.1 + 0.2), last one wrong
        for question_id, answer in [(1, 0), (2, 0), (3, 1)]:
            requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
            )

        final_results = requests.get(f"{base_url}/api/verify-user/{user_id}").json()["final_results"]

        assert final_results["earned_points"] == 0.3
        assert repr(final_results["earned_points"]) == "0.3"
        assert final_results["total_points"] == 1
        assert final_results["points_percentage"] == 30

    def test_users_csv_contains_decimal_points(self, decimal_points_server):
        """Decimal earned/total points are written to the users CSV."""
        proc, port = decimal_points_server
        base_url = f"http://localhost:{port}"

        user_id = requests.post(f"{base_url}/api/register", json={"username": "decimal_csv"}).json()["user_id"]

        for question_id, answer in [(1, 0), (2, 1), (3, 1)]:
            requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
            )

        # Wait for the periodic CSV flush (5s interval)
        time.sleep(7)

        users_csv = glob.glob(os.path.join(f"data_{port}", "*.users.csv"))
        assert users_csv, "users CSV was not created"

        with open(users_csv[0], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        row = next(r for r in rows if r["username"] == "decimal_csv")
        assert float(row["earned_points"]) == 1.75
        assert float(row["total_points"]) == 4


@pytest.mark.asyncio
async def test_live_stats_broadcast_carries_decimal_points():
    """The live-stats WebSocket reports decimal question and total points."""
    quiz_data = {
        "title": "Decimal Points Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 0.5},
            {"question": "Q2", "options": ["A", "B"], "correct_answer": 1, "points": 1.25},
        ],
    }

    with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
        base_url = f"http://localhost:{port}"

        async with websockets.connect(f"ws://localhost:{port}/ws/live-stats") as websocket:
            await asyncio.wait_for(websocket.recv(), timeout=2.0)  # initial_state

            user_id = requests.post(f"{base_url}/api/register", json={"username": "wsuser"}).json()["user_id"]
            requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": 2, "selected_answer": 1},
            )

            state_update = None
            while state_update is None:
                message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=3.0))
                if message.get("type") == "state_update":
                    state_update = message

            assert state_update["question_points"] == 1.25
            assert state_update["earned_points"] == 1.25
            assert state_update["total_points"] == 1.75


class TestDecimalPointsValidation:
    """Quiz validation accepts up to two decimals and rejects anything finer."""

    @pytest.mark.parametrize("points", [0.5, 1.25, 2.75, 0.01, 3])
    def test_valid_points_accepted(self, points):
        """Points with at most two decimals are accepted."""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
            base_url = f"http://localhost:{port}"
            cookies = get_admin_session(port)

            response = _create_quiz(base_url, cookies, "valid_points.yaml", _quiz_with_points(points))
            assert response.status_code == 200, response.text

    @pytest.mark.parametrize("points", [1.234, 0.001, 2.5001])
    def test_more_than_two_decimals_rejected(self, points):
        """Points with more than two decimals are rejected."""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
            base_url = f"http://localhost:{port}"
            cookies = get_admin_session(port)

            response = _create_quiz(base_url, cookies, "bad_points.yaml", _quiz_with_points(points))
            assert response.status_code == 400, response.text

    @pytest.mark.parametrize("points", [0, -1, -0.5, "abc", True, None])
    def test_non_positive_or_non_numeric_points_rejected(self, points):
        """Points must be a positive number."""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
            base_url = f"http://localhost:{port}"
            cookies = get_admin_session(port)

            response = _create_quiz(base_url, cookies, "bad_points.yaml", _quiz_with_points(points))
            assert response.status_code == 400, response.text

    def test_points_validated_on_text_questions_too(self):
        """Decimal points work on text questions, and bad values are still rejected."""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
            base_url = f"http://localhost:{port}"
            cookies = get_admin_session(port)

            good = {
                "title": "Text Points Quiz",
                "questions": [{"question": "Enter:", "correct_value": "x", "checker": "", "points": 1.5}],
            }
            assert _create_quiz(base_url, cookies, "text_good.yaml", good).status_code == 200

            bad = {
                "title": "Text Points Quiz",
                "questions": [{"question": "Enter:", "correct_value": "x", "checker": "", "points": 1.555}],
            }
            assert _create_quiz(base_url, cookies, "text_bad.yaml", bad).status_code == 400


class TestDecimalPointsRoundTrip:
    """Decimal points survive being saved and loaded again."""

    def test_decimal_points_preserved_in_saved_quiz(self):
        """A quiz saved with decimal points reads back with the same values."""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        with custom_webquiz_server(quizzes={"default.yaml": quiz_data}) as (proc, port):
            base_url = f"http://localhost:{port}"
            cookies = get_admin_session(port)

            new_quiz = {
                "title": "Decimal Quiz",
                "questions": [
                    {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 0.5},
                    {"question": "Q2", "options": ["A", "B"], "correct_answer": 1, "points": 2.25},
                ],
            }
            assert _create_quiz(base_url, cookies, "decimal_quiz.yaml", new_quiz).status_code == 200

            response = requests.get(f"{base_url}/api/admin/quiz/decimal_quiz.yaml", cookies=cookies)
            assert response.status_code == 200
            content = response.json()["content"]

            assert "0.5" in content
            assert "2.25" in content
