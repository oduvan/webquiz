"""Tests for live stats two-group functionality (in-progress and completed)."""

import pytest
import requests
import asyncio
import websockets
import json
from tests.conftest import custom_webquiz_server


@pytest.mark.asyncio
async def test_initial_state_includes_completed_users(temp_dir):
    """Test that WebSocket initial_state includes completed_users dictionary."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register a user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        # Connect to WebSocket
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state message
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)

            assert initial_data["type"] == "initial_state"
            assert "completed_users" in initial_data
            assert user_id in initial_data["completed_users"]
            assert initial_data["completed_users"][user_id] == False  # Not completed yet


@pytest.mark.asyncio
async def test_state_update_includes_completed_flag(temp_dir):
    """Test that state_update messages include completed flag."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Connect to WebSocket first
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Register user
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            assert response.status_code == 200
            user_id = response.json()["user_id"]

            # Wait for user_registered message
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Submit first answer
            response = requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
            )
            assert response.status_code == 200

            # Wait for state_update message
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            ws_data = json.loads(message)

            assert ws_data["type"] == "state_update"
            assert "completed" in ws_data
            assert ws_data["completed"] == False  # Only answered 1 of 2 questions


@pytest.mark.asyncio
async def test_user_completes_test_completed_flag_true(temp_dir):
    """Test that completed flag becomes true when user finishes all questions."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Connect to WebSocket
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Register user
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            assert response.status_code == 200
            user_id = response.json()["user_id"]

            # Wait for user_registered message
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Submit first answer
            requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
            )
            msg1 = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            data1 = json.loads(msg1)
            assert data1["completed"] == False

            # Submit second (last) answer
            requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": 2, "selected_answer": 1},
            )
            msg2 = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            data2 = json.loads(msg2)
            assert data2["completed"] == True  # Now completed!


@pytest.mark.asyncio
async def test_multiple_users_different_completion_status(temp_dir):
    """Test that different users can have different completion statuses."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register two users
        response1 = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        assert response1.status_code == 200
        user1_id = response1.json()["user_id"]

        response2 = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        assert response2.status_code == 200
        user2_id = response2.json()["user_id"]

        # User1 completes all questions
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 0},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 2, "selected_answer": 1},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 3, "selected_answer": 0},
        )

        # User2 only completes first question
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 1, "selected_answer": 0},
        )

        # Connect to WebSocket and check initial state
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)

            assert initial_data["type"] == "initial_state"
            completed_users = initial_data["completed_users"]

            # User1 should be completed, User2 should not be
            assert completed_users[user1_id] == True
            assert completed_users[user2_id] == False


@pytest.mark.asyncio
async def test_completed_users_tracked_across_reconnection(temp_dir):
    """Test that completion status is maintained when new WebSocket clients connect."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register user and complete quiz
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 2, "selected_answer": 1},
        )

        # Connect new WebSocket client
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)

            # User should still show as completed
            assert initial_data["completed_users"][user_id] == True


@pytest.mark.asyncio
async def test_no_users_empty_completed_dict(temp_dir):
    """Test that completed_users is empty when no users have registered."""
    with custom_webquiz_server() as (proc, port):
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)

            assert initial_data["type"] == "initial_state"
            assert "completed_users" in initial_data
            assert len(initial_data["completed_users"]) == 0


@pytest.mark.asyncio
async def test_quiz_switch_resets_completed_users(temp_dir):
    """Test that switching quizzes resets completion tracking."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
        ],
    }

    # Use default.yaml so it auto-loads, then we can switch to quiz2.yaml
    with custom_webquiz_server(quizzes={"default.yaml": quiz_data, "quiz2.yaml": quiz_data}) as (proc, port):
        # Register user on first quiz and complete it
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
        )

        # Connect to WebSocket
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            # Get initial state (user should be completed)
            initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            initial_data = json.loads(initial_msg)
            assert initial_data["completed_users"][user_id] == True

            # Switch quiz
            requests.post(
                f"http://localhost:{port}/api/admin/switch-quiz",
                json={"quiz_filename": "quiz2.yaml"},
                headers={"X-Master-Key": "test123"},
            )

            # Wait for quiz_switched message
            switch_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            switch_data = json.loads(switch_msg)

            assert switch_data["type"] == "quiz_switched"
            # After switch, no users should exist (quiz switch resets all state)


@pytest.mark.asyncio
async def test_completion_with_randomized_questions(temp_dir):
    """Test that completion works correctly with randomized questions."""
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
            # Receive initial_state
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Register user
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            user_id = response.json()["user_id"]
            question_order = response.json()["question_order"]

            # Wait for user_registered
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Answer all questions in the randomized order
            for question_id in question_order:
                requests.post(
                    f"http://localhost:{port}/api/submit-answer",
                    json={"user_id": user_id, "question_id": question_id, "selected_answer": 0},
                )
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(msg)

                # Check if this is the last question
                is_last = question_id == question_order[-1]
                assert data["completed"] == is_last


@pytest.mark.asyncio
async def test_approval_workflow_completion_tracking(temp_dir):
    """Test that completion tracking works with approval workflow."""
    quiz_data = {
        "title": "Test Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config, quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Connect to WebSocket first
        ws_url = f"ws://localhost:{port}/ws/live-stats"
        async with websockets.connect(ws_url) as websocket:
            # Receive initial_state
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # Register user (requires approval)
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
            user_id = response.json()["user_id"]

            # Approve user
            requests.put(
                f"http://localhost:{port}/api/admin/approve-user",
                json={"user_id": user_id},
                headers={"X-Master-Key": "test123"},
            )

            # Wait for user_registered message after approval
            await asyncio.wait_for(websocket.recv(), timeout=2.0)

            # User completes quiz
            requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
            )
            msg1 = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            assert json.loads(msg1)["completed"] == False

            requests.post(
                f"http://localhost:{port}/api/submit-answer",
                json={"user_id": user_id, "question_id": 2, "selected_answer": 1},
            )
            msg2 = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            assert json.loads(msg2)["completed"] == True
