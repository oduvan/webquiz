"""
Tests for the extra answers_with_users CSV (per-answer rows enriched with user info).

This optional third CSV is generated when ``extra_answers_with_users_csv: true``
is set in the top-level WebQuiz config. It writes one row per submitted answer,
with ``user_id``, ``username`` and any configured registration fields prepended
to the standard answers columns.
"""

import csv
import os
import time

import pytest
import requests

from tests.conftest import custom_webquiz_server


QUIZ_DATA = {
    "title": "Answers-with-users CSV Quiz",
    "show_right_answer": True,
    "questions": [
        {"question": "Q1?", "options": ["a", "b", "c", "d"], "correct_answer": 1},
        {"question": "Q2?", "options": ["w", "x", "y", "z"], "correct_answer": 0},
    ],
}


def _wait_for_file(path, timeout=10.0):
    """Block until ``path`` exists or ``timeout`` elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(0.25)
    return False


def _find_csv(csv_dir, suffix):
    """Return absolute path of first CSV file matching ``suffix``, or None."""
    if not os.path.isdir(csv_dir):
        return None
    for filename in os.listdir(csv_dir):
        if filename.endswith(suffix):
            return os.path.join(csv_dir, filename)
    return None


def _submit_all(base_url, user_id, answers):
    for q_id, selected in answers:
        response = requests.post(
            f"{base_url}/api/submit-answer",
            json={"user_id": user_id, "question_id": q_id, "selected_answer": selected},
        )
        assert response.status_code == 200, response.text


def test_answers_with_users_csv_not_created_when_disabled():
    """By default, no .answers_with_users.csv file is generated."""
    with custom_webquiz_server(quizzes={"default.yaml": QUIZ_DATA}) as (_, port):
        base_url = f"http://localhost:{port}"
        csv_dir = f"data_{port}"

        response = requests.post(f"{base_url}/api/register", json={"username": "alice"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        _submit_all(base_url, user_id, [(1, 1), (2, 0)])

        # Wait long enough for the 5s periodic flush
        time.sleep(6)

        # Regular answers CSV should exist
        assert _find_csv(csv_dir, ".csv") is not None, "answers CSV should exist"
        # But the third file should NOT
        assert _find_csv(csv_dir, ".answers_with_users.csv") is None, (
            "extra answers_with_users CSV must not be created when disabled"
        )


def test_answers_with_users_csv_created_when_enabled():
    """With ``extra_answers_with_users_csv: true``, a .answers_with_users.csv file is generated."""
    config = {"extra_answers_with_users_csv": True}
    with custom_webquiz_server(config=config, quizzes={"default.yaml": QUIZ_DATA}) as (_, port):
        base_url = f"http://localhost:{port}"
        csv_dir = f"data_{port}"

        response = requests.post(f"{base_url}/api/register", json={"username": "bob"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        _submit_all(base_url, user_id, [(1, 1), (2, 0)])

        extra_path = os.path.join(csv_dir, "default_0001.answers_with_users.csv")
        assert _wait_for_file(extra_path, timeout=10.0), "answers_with_users CSV was never created"

        with open(extra_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert reader.fieldnames == [
            "user_id",
            "username",
            "question",
            "selected_answer",
            "correct_answer",
            "is_correct",
            "time_taken_seconds",
        ]
        assert len(rows) == 2

        for row in rows:
            assert row["user_id"] == user_id
            assert row["username"] == "bob"

        questions = sorted(r["question"] for r in rows)
        assert questions == ["Q1?", "Q2?"]


def test_answers_with_users_csv_includes_registration_fields():
    """Custom registration fields are included as columns alongside username."""
    config = {
        "extra_answers_with_users_csv": True,
        "registration": {"fields": ["School", "Grade Level"]},
    }
    with custom_webquiz_server(config=config, quizzes={"default.yaml": QUIZ_DATA}) as (_, port):
        base_url = f"http://localhost:{port}"
        csv_dir = f"data_{port}"

        response = requests.post(
            f"{base_url}/api/register",
            json={"username": "carol", "school": "Lyceum 1", "grade_level": "10-B"},
        )
        assert response.status_code == 200, response.text
        user_id = response.json()["user_id"]

        _submit_all(base_url, user_id, [(1, 1), (2, 0)])

        extra_path = os.path.join(csv_dir, "default_0001.answers_with_users.csv")
        assert _wait_for_file(extra_path, timeout=10.0), "answers_with_users CSV was never created"

        with open(extra_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert reader.fieldnames == [
            "user_id",
            "username",
            "school",
            "grade_level",
            "question",
            "selected_answer",
            "correct_answer",
            "is_correct",
            "time_taken_seconds",
        ]
        assert len(rows) == 2

        for row in rows:
            assert row["username"] == "carol"
            assert row["school"] == "Lyceum 1"
            assert row["grade_level"] == "10-B"


def test_answers_with_users_csv_appends_across_flushes():
    """A second batch of answers is appended (not overwritten) to the extra CSV."""
    config = {"extra_answers_with_users_csv": True}
    with custom_webquiz_server(config=config, quizzes={"default.yaml": QUIZ_DATA}) as (_, port):
        base_url = f"http://localhost:{port}"
        csv_dir = f"data_{port}"

        # User 1 submits first answer, wait for flush
        r = requests.post(f"{base_url}/api/register", json={"username": "user1"})
        user_id_1 = r.json()["user_id"]
        _submit_all(base_url, user_id_1, [(1, 1)])

        extra_path = os.path.join(csv_dir, "default_0001.answers_with_users.csv")
        assert _wait_for_file(extra_path, timeout=10.0)

        # User 2 submits answers after first flush has happened
        r = requests.post(f"{base_url}/api/register", json={"username": "user2"})
        user_id_2 = r.json()["user_id"]
        _submit_all(base_url, user_id_2, [(1, 0), (2, 0)])

        # Wait long enough for the next periodic flush to append
        time.sleep(7)

        with open(extra_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # 1 row from user1 + 2 rows from user2
        assert len(rows) == 3
        usernames = sorted({row["username"] for row in rows})
        assert usernames == ["user1", "user2"]


def test_answers_with_users_csv_config_validation_rejects_non_bool():
    """Saving a config with a non-boolean extra_answers_with_users_csv via admin API returns 400."""
    from tests.conftest import get_admin_session

    with custom_webquiz_server(quizzes={"default.yaml": QUIZ_DATA}) as (_, port):
        base_url = f"http://localhost:{port}"
        cookies = get_admin_session(port)

        response = requests.put(
            f"{base_url}/api/admin/config",
            json={"content": "extra_answers_with_users_csv: \"yes\"\n"},
            cookies=cookies,
        )
        assert response.status_code == 400, response.text
        body = response.json()
        assert any("extra_answers_with_users_csv" in err for err in body.get("errors", []))
