import requests
from conftest import custom_webquiz_server, get_admin_session


def make_admin_request(method, url, cookies, **kwargs):
    """Helper to make admin requests with cookies."""
    return requests.request(method, url, cookies=cookies, **kwargs)


def test_basic_manual_reveal_flow():
    """Test basic manual reveal flow - admin forces answers to show."""
    quiz_data = {
        "default.yaml": {
            "title": "Manual Reveal Test Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
                {"question": "What is 3 + 3?", "options": ["5", "6", "7", "8"], "correct_answer": 1},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        # Get admin session
        admin_session = get_admin_session(port, "test123")

        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        assert user1_response.status_code == 200
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        assert user2_response.status_code == 200
        user2_id = user2_response.json()["user_id"]

        # User 1 completes the quiz
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 1},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 2, "selected_answer": 1},
        )

        # Verify user 1 - should NOT have correct answers yet (user2 hasn't completed)
        verify1_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        assert verify1_response.status_code == 200
        verify1_data = verify1_response.json()
        assert verify1_data["test_completed"] is True
        final_results1 = verify1_data["final_results"]
        assert final_results1["all_completed"] is False

        # Verify correct answers are NOT shown
        for result in final_results1["test_results"]:
            assert "correct_answer" not in result
            assert "is_correct" not in result

        # Admin forces answers to show
        force_response = make_admin_request(
            "POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session
        )
        assert force_response.status_code == 200
        force_data = force_response.json()
        assert force_data["success"] is True
        assert force_data["forced"] is True
        assert force_data["completed_count"] == 1  # Only user1 completed
        assert force_data["total_count"] == 2  # 2 users registered

        # Verify user 1 again - NOW should have correct answers
        verify1_after_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        assert verify1_after_response.status_code == 200
        verify1_after_data = verify1_after_response.json()
        final_results1_after = verify1_after_data["final_results"]

        # all_completed should now be True (forced)
        assert final_results1_after["all_completed"] is True

        # Verify correct answers ARE now shown
        for result in final_results1_after["test_results"]:
            assert "correct_answer" in result
            assert "is_correct" in result

        # User 2 completes now (after manual reveal)
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 1, "selected_answer": 1},
        )
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 2, "selected_answer": 1},
        )

        # Verify user 2 also sees correct answers (because of manual reveal)
        verify2_response = requests.get(f"http://localhost:{port}/api/verify-user/{user2_id}")
        assert verify2_response.status_code == 200
        verify2_data = verify2_response.json()
        final_results2 = verify2_data["final_results"]

        assert final_results2["all_completed"] is True
        for result in final_results2["test_results"]:
            assert "correct_answer" in result
            assert "is_correct" in result


def test_show_right_answer_precedence():
    """Test that show_right_answer: true always shows answers regardless of manual reveal."""
    quiz_data = {
        "default.yaml": {
            "title": "Precedence Test Quiz",
            "show_right_answer": True,  # This should always show answers
            "show_answers_on_completion": True,
            "questions": [
                {"question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        # Register and complete quiz
        user_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        assert user_response.status_code == 200
        user_id = user_response.json()["user_id"]

        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 1},
        )

        # Verify answers are shown even without manual reveal
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        final_results = verify_data["final_results"]

        for result in final_results["test_results"]:
            assert "correct_answer" in result
            assert "is_correct" in result


def test_reset_on_quiz_switch():
    """Test that force_all_completed flag resets when switching quizzes."""
    quiz_data = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "Q1?", "options": ["A", "B"], "correct_answer": 0},
            ],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "Q2?", "options": ["C", "D"], "correct_answer": 1},
            ],
        },
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        admin_session = get_admin_session(port, "test123")

        # Select quiz1 first
        make_admin_request(
            "POST",
            f"http://localhost:{port}/api/admin/switch-quiz",
            admin_session,
            json={"quiz_filename": "quiz1.yaml"},
        )

        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]

        # Only user1 completes
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 0},
        )

        # Verify answers not shown initially (user2 hasn't completed)
        verify_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results = verify_response.json()["final_results"]
        assert final_results["all_completed"] is False
        assert "correct_answer" not in final_results["test_results"][0]

        # Force show answers
        force_response = make_admin_request(
            "POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session
        )
        assert force_response.status_code == 200

        # Verify answers are now shown
        verify_response2 = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results2 = verify_response2.json()["final_results"]
        assert final_results2["all_completed"] is True

        # Switch to quiz2
        switch_response = make_admin_request(
            "POST",
            f"http://localhost:{port}/api/admin/switch-quiz",
            admin_session,
            json={"quiz_filename": "quiz2.yaml"},
        )
        assert switch_response.status_code == 200

        # Verify force_all_completed is reset
        list_response = make_admin_request("GET", f"http://localhost:{port}/api/admin/list-quizzes", admin_session)
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["force_all_completed"] is False


def test_new_student_after_manual_reveal():
    """Test that new students also see answers after manual reveal."""
    quiz_data = {
        "default.yaml": {
            "title": "New Student Test Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "correct_answer": 1},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        admin_session = get_admin_session(port, "test123")

        # Register user1 and complete quiz
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 1},
        )

        # Force show answers
        make_admin_request("POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session)

        # Register new user2
        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        assert user2_response.status_code == 200
        user2_id = user2_response.json()["user_id"]

        # User2 completes quiz
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user2_id, "question_id": 1, "selected_answer": 0},  # Wrong answer
        )

        # Verify user2 sees correct answers (even though they registered after manual reveal)
        verify2_response = requests.get(f"http://localhost:{port}/api/verify-user/{user2_id}")
        verify2_data = verify2_response.json()
        final_results2 = verify2_data["final_results"]

        assert final_results2["all_completed"] is True
        assert "correct_answer" in final_results2["test_results"][0]
        assert "is_correct" in final_results2["test_results"][0]


def test_authentication_required():
    """Test that force-show-answers endpoint requires admin authentication."""
    quiz_data = {
        "default.yaml": {
            "title": "Auth Test Quiz",
            "show_right_answer": False,
            "questions": [
                {"question": "Q?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        # Try to force show answers without authentication
        response = requests.post(f"http://localhost:{port}/api/admin/force-show-answers")
        assert response.status_code in [401, 403]  # Should be unauthorized/forbidden


def test_force_show_answers_idempotent():
    """Test that calling force-show-answers multiple times is idempotent."""
    quiz_data = {
        "default.yaml": {
            "title": "Idempotent Test Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "Q?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        admin_session = get_admin_session(port, "test123")

        # Force show answers first time
        response1 = make_admin_request("POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["forced"] is True

        # Force show answers second time - should still succeed
        response2 = make_admin_request("POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["forced"] is True


def test_force_show_with_no_students():
    """Test that forcing answers works even when no students are registered."""
    quiz_data = {
        "default.yaml": {
            "title": "No Students Test Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "Q?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        admin_session = get_admin_session(port, "test123")

        # Force show answers with no students
        response = make_admin_request("POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session)
        assert response.status_code == 200
        data = response.json()
        assert data["forced"] is True
        assert data["completed_count"] == 0
        assert data["total_count"] == 0


def test_admin_list_quizzes_includes_flag():
    """Test that admin_list_quizzes response includes force_all_completed flag."""
    quiz_data = {
        "default.yaml": {
            "title": "Flag Test Quiz",
            "show_right_answer": False,
            "questions": [
                {"question": "Q?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        admin_session = get_admin_session(port, "test123")

        # Check initial state - flag should be False
        list_response1 = make_admin_request("GET", f"http://localhost:{port}/api/admin/list-quizzes", admin_session)
        assert list_response1.status_code == 200
        list_data1 = list_response1.json()
        assert "force_all_completed" in list_data1
        assert list_data1["force_all_completed"] is False
        assert "show_answers_on_completion" in list_data1
        assert list_data1["show_answers_on_completion"] is False  # Default quiz has this disabled

        # Force show answers
        make_admin_request("POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session)

        # Check state after forcing - flag should be True
        list_response2 = make_admin_request("GET", f"http://localhost:{port}/api/admin/list-quizzes", admin_session)
        assert list_response2.status_code == 200
        list_data2 = list_response2.json()
        assert list_data2["force_all_completed"] is True
        assert list_data2["show_answers_on_completion"] is False  # Quiz config hasn't changed


def test_manual_reveal_with_approval_mode():
    """Test manual reveal works correctly with approval mode enabled."""
    quiz_data = {
        "default.yaml": {
            "title": "Approval Mode Test Quiz",
            "show_right_answer": False,
            "show_answers_on_completion": True,
            "questions": [
                {"question": "Q?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    config_data = {
        "admin": {"master_key": "test123"},
        "registration": {
            "approve": True,
        },
    }

    with custom_webquiz_server(config=config_data, quizzes=quiz_data) as (proc, port):
        admin_session = get_admin_session(port, "test123")

        # Register two users
        user1_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user1"})
        user1_id = user1_response.json()["user_id"]

        user2_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "user2"})
        user2_id = user2_response.json()["user_id"]

        # Approve only user1
        make_admin_request(
            "PUT", f"http://localhost:{port}/api/admin/approve-user", admin_session, json={"user_id": user1_id}
        )

        # User1 completes quiz
        requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user1_id, "question_id": 1, "selected_answer": 0},
        )

        # Verify answers not shown yet (user1 is only approved student, so all approved completed)
        verify1_response = requests.get(f"http://localhost:{port}/api/verify-user/{user1_id}")
        final_results1 = verify1_response.json()["final_results"]
        # With approval mode, user1 is the only approved student and they completed, so answers should show
        assert final_results1["all_completed"] is True

        # Force show answers (should work even though all approved students completed)
        force_response = make_admin_request(
            "POST", f"http://localhost:{port}/api/admin/force-show-answers", admin_session
        )
        assert force_response.status_code == 200
        assert force_response.json()["forced"] is True
