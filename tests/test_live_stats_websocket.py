"""Tests for live stats WebSocket with question randomization."""

import pytest
import requests
import asyncio
import websockets
import json
from tests.conftest import custom_webquiz_server


@pytest.mark.asyncio
async def test_live_stats_websocket_shows_correct_first_question(temp_dir):
    """Test that WebSocket live stats shows correct first question from randomized order."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Connect to WebSocket first
        ws_url = f"ws://localhost:{port}/ws/live-stats"

        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state message (empty on first connection)
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)
            assert initial_data["type"] == "initial_state"

            # Register a user (this should trigger WebSocket broadcast)
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            assert response.status_code == 200
            data = response.json()
            user_id = data["user_id"]
            question_order = data["question_order"]
            expected_first_question = question_order[0]

            # Wait for WebSocket message about user registration
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            ws_data = json.loads(message)

            # Verify the WebSocket message contains correct first question
            assert ws_data["type"] == "user_registered"
            assert ws_data["user_id"] == user_id
            assert ws_data["username"] == "testuser"
            assert ws_data["question_id"] == expected_first_question, (
                f"Expected first question {expected_first_question} in WebSocket, " f"but got {ws_data['question_id']}"
            )
            assert ws_data["state"] == "think"


@pytest.mark.asyncio
async def test_live_stats_websocket_no_duplicate_questions(temp_dir):
    """Test that WebSocket doesn't send duplicate question notifications."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        ws_url = f"ws://localhost:{port}/ws/live-stats"

        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state message
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)
            assert initial_data["type"] == "initial_state"

            # Register a user
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            assert response.status_code == 200
            data = response.json()
            user_id = data["user_id"]
            question_order = data["question_order"]

            # Wait for registration message
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            ws_data = json.loads(message)

            assert ws_data["type"] == "user_registered"
            first_question_id = ws_data["question_id"]

            # The question_id in WebSocket should match the first question in order
            assert first_question_id == question_order[0], (
                f"WebSocket shows question {first_question_id}, " f"but first in order is {question_order[0]}"
            )


@pytest.mark.asyncio
async def test_live_stats_websocket_with_approval_workflow(temp_dir):
    """Test that WebSocket uses correct first question in approval workflow."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
        ],
    }

    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config, quizzes={"test.yaml": quiz_data}) as (proc, port):
        ws_url = f"ws://localhost:{port}/ws/live-stats"

        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state message
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)
            assert initial_data["type"] == "initial_state"

            # Register a user (not yet approved)
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            assert response.status_code == 200
            data = response.json()
            user_id = data["user_id"]
            question_order = data["question_order"]
            expected_first_question = question_order[0]

            # Approve user (this should trigger WebSocket message)
            response = requests.put(
                f"http://localhost:{port}/api/admin/approve-user",
                json={"user_id": user_id},
                headers={"X-Master-Key": "test123"},
            )
            assert response.status_code == 200

            # Wait for WebSocket message about user approval
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            ws_data = json.loads(message)

            # Verify the WebSocket message contains correct first question
            assert ws_data["type"] == "user_registered"  # Approval sends same type as registration
            assert ws_data["user_id"] == user_id
            assert ws_data["question_id"] == expected_first_question, (
                f"Expected first question {expected_first_question} after approval, "
                f"but WebSocket shows {ws_data['question_id']}"
            )


@pytest.mark.asyncio
async def test_live_stats_websocket_without_randomization(temp_dir):
    """Test that WebSocket shows question 1 when randomization is disabled."""
    quiz_data = {
        "title": "Non-Randomized Quiz",
        "randomize_questions": False,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user first
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Now connect to WebSocket and check initial state
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            # Wait for initial_state message
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            ws_data = json.loads(message)

            assert ws_data["type"] == "initial_state"
            # Check live_stats contains the user with question 1 in "think" state
            assert user_id in ws_data["live_stats"]
            user_stats = ws_data["live_stats"][user_id]

            # Question 1 should be in "think" state (since randomization is disabled)
            # Note: question IDs are strings in JSON
            assert "1" in user_stats, f"Question 1 not found in user stats: {user_stats.keys()}"
            assert (
                user_stats["1"]["state"] == "think"
            ), f"Expected question 1 in 'think' state, but got {user_stats['1']['state']}"


@pytest.mark.asyncio
async def test_live_stats_websocket_multiple_users_different_orders(temp_dir):
    """Test that different users get different first questions in WebSocket."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
            {"question": "Q6", "options": ["K", "L"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        ws_url = f"ws://localhost:{port}/ws/live-stats"

        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state message (empty)
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)
            assert initial_data["type"] == "initial_state"

            first_questions = []

            # Register 5 users and collect their first question IDs from WebSocket
            for i in range(5):
                response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
                assert response.status_code == 200

                # Wait for WebSocket message
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                ws_data = json.loads(message)

                assert ws_data["type"] == "user_registered"
                first_questions.append(ws_data["question_id"])

            # With 6 questions and 5 users, very likely to have different first questions
            unique_first_questions = set(first_questions)
            assert len(unique_first_questions) > 1, (
                "Expected at least some users to have different first questions, " f"but all got: {first_questions}"
            )
