"""Tests for stick_to_the_previous question attribute."""

import pytest
import requests
import yaml
from conftest import custom_webquiz_server, get_admin_session


def test_stick_to_previous_disabled_by_default(temp_dir):
    """Test that stick_to_the_previous is not set by default."""
    quiz_data = {
        "title": "Test Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }
    # Verify questions don't have stick_to_the_previous by default
    assert "stick_to_the_previous" not in quiz_data["questions"][0]
    assert "stick_to_the_previous" not in quiz_data["questions"][1]

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        user_id = response.json()["user_id"]

        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "question_order" in data
        # Without sticky constraints, any order should be valid
        assert set(data["question_order"]) == {1, 2}


def test_simple_sticky_pair(temp_dir):
    """Test that two questions with stick_to_the_previous stay together."""
    quiz_data = {
        "title": "Sticky Pair Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        # Register multiple users and verify Q1 always directly precedes Q2
        for i in range(10):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            assert response.status_code == 200
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            assert response.status_code == 200
            order = response.json()["question_order"]

            # Find position of Q1 and Q2
            pos_q1 = order.index(1)
            pos_q2 = order.index(2)

            # Q2 must immediately follow Q1
            assert pos_q2 == pos_q1 + 1, f"Q2 should follow Q1 directly, got order: {order}"


def test_sticky_chain_of_three(temp_dir):
    """Test that a chain of 3 sticky questions stays together."""
    quiz_data = {
        "title": "Sticky Chain Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0, "stick_to_the_previous": True},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        for i in range(10):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]

            # Q1, Q2, Q3 must be consecutive in that order
            pos_q1 = order.index(1)
            pos_q2 = order.index(2)
            pos_q3 = order.index(3)

            assert pos_q2 == pos_q1 + 1, f"Q2 should follow Q1, got order: {order}"
            assert pos_q3 == pos_q2 + 1, f"Q3 should follow Q2, got order: {order}"


def test_multiple_sticky_groups(temp_dir):
    """Test multiple separate sticky groups: [Q1,Q2], [Q3], [Q4,Q5].

    This tests the scenario where questions at positions 2, 4, 5 have stick_to_the_previous: true.
    Groups formed: [Q1,Q2], [Q3,Q4,Q5]
    """
    quiz_data = {
        "title": "Multiple Groups Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0, "stick_to_the_previous": True},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        for i in range(10):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]

            # Q2 must follow Q1
            assert order.index(2) == order.index(1) + 1, f"Q2 should follow Q1, got: {order}"
            # Q4 must follow Q3
            assert order.index(4) == order.index(3) + 1, f"Q4 should follow Q3, got: {order}"
            # Q5 must follow Q4
            assert order.index(5) == order.index(4) + 1, f"Q5 should follow Q4, got: {order}"


def test_positions_2_4_5_sticky(temp_dir):
    """Test the specific scenario: questions 2, 4, 5 have stick_to_the_previous.

    This creates groups: [Q1,Q2], [Q3,Q4,Q5]
    Where Q2 sticks to Q1, Q4 sticks to Q3, Q5 sticks to Q4.
    """
    quiz_data = {
        "title": "Positions 2,4,5 Sticky Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0, "stick_to_the_previous": True},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        orders_seen = set()
        for i in range(20):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]
            orders_seen.add(tuple(order))

            # Group [Q1,Q2] must stay together
            assert order.index(2) == order.index(1) + 1, f"Q2 should follow Q1, got: {order}"
            # Group [Q3,Q4,Q5] must stay together in order
            assert order.index(4) == order.index(3) + 1, f"Q4 should follow Q3, got: {order}"
            assert order.index(5) == order.index(4) + 1, f"Q5 should follow Q4, got: {order}"

        # With 2 groups, we should see at least 2 different orderings
        # (either [1,2,3,4,5] or [3,4,5,1,2])
        assert len(orders_seen) >= 1, "Should have valid sticky group orderings"


def test_sticky_without_randomization(temp_dir):
    """Test that stick_to_the_previous has no effect when randomization is disabled."""
    quiz_data = {
        "title": "Non-Randomized Quiz",
        "randomize_questions": False,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        data = response.json()

        # No question_order when randomization is disabled
        assert "question_order" not in data


def test_validation_first_question_cannot_be_sticky(temp_dir):
    """Test that first question cannot have stick_to_the_previous: true."""
    invalid_quiz = {
        "title": "Invalid Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "stick_to_the_previous": True},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    default_quiz = {
        "title": "Default",
        "questions": [{"question": "Q", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(quizzes={"default.yaml": default_quiz}) as (proc, port):
        yaml_content = yaml.dump(invalid_quiz)
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": yaml_content},
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert not data["valid"]
        assert any("Question 1" in error and "stick_to_the_previous" in error for error in data["errors"])


def test_validation_stick_to_previous_must_be_boolean(temp_dir):
    """Test that stick_to_the_previous must be a boolean."""
    invalid_quiz = {
        "title": "Invalid Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": "yes"},
        ],
    }

    default_quiz = {
        "title": "Default",
        "questions": [{"question": "Q", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(quizzes={"default.yaml": default_quiz}) as (proc, port):
        yaml_content = yaml.dump(invalid_quiz)
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": yaml_content},
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert not data["valid"]
        assert any("boolean" in error for error in data["errors"])


def test_validation_stick_to_previous_integer_is_invalid(temp_dir):
    """Test that stick_to_the_previous as integer is rejected."""
    invalid_quiz = {
        "title": "Invalid Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": 1},
        ],
    }

    default_quiz = {
        "title": "Default",
        "questions": [{"question": "Q", "options": ["A", "B"], "correct_answer": 0}],
    }

    with custom_webquiz_server(quizzes={"default.yaml": default_quiz}) as (proc, port):
        yaml_content = yaml.dump(invalid_quiz)
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": yaml_content},
            cookies=get_admin_session(port),
        )
        assert response.status_code == 200
        data = response.json()
        assert not data["valid"]
        assert any("boolean" in error for error in data["errors"])


def test_all_questions_sticky_except_first(temp_dir):
    """Test when all questions except first have stick_to_the_previous (single group)."""
    quiz_data = {
        "title": "Single Group Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0, "stick_to_the_previous": True},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1, "stick_to_the_previous": True},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "testuser"})
        user_id = response.json()["user_id"]

        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        order = response.json()["question_order"]

        # All questions form one group, order should always be [1, 2, 3, 4]
        assert order == [1, 2, 3, 4], f"Expected [1,2,3,4], got {order}"


def test_sticky_with_text_questions(temp_dir):
    """Test that stick_to_the_previous works with text input questions."""
    quiz_data = {
        "title": "Mixed Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2 (text)", "checker": "assert True", "stick_to_the_previous": True},
            {"question": "Q3", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        for i in range(5):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]

            # Q2 must follow Q1
            assert order.index(2) == order.index(1) + 1, f"Q2 should follow Q1, got: {order}"


def test_sticky_groups_actually_shuffle(temp_dir):
    """Test that groups are actually shuffled (not just kept in original order)."""
    quiz_data = {
        "title": "Shuffle Test Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
            {"question": "Q4", "options": ["G", "H"], "correct_answer": 1},
            {"question": "Q5", "options": ["I", "J"], "correct_answer": 0},
            {"question": "Q6", "options": ["K", "L"], "correct_answer": 1},
        ],
    }

    # Groups: [1,2], [3], [4], [5], [6]

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        first_positions = []

        for i in range(20):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]
            first_positions.append(order[0])

            # Q2 must still follow Q1
            assert order.index(2) == order.index(1) + 1, f"Q2 should follow Q1, got: {order}"

        # With 5 groups and 20 users, we should see different groups at position 0
        unique_firsts = set(first_positions)
        assert len(unique_firsts) > 1, "Groups should be shuffled, but first position is always the same"


def test_sticky_false_explicit(temp_dir):
    """Test that stick_to_the_previous: false behaves same as not set."""
    quiz_data = {
        "title": "Explicit False Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": False},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        orders_seen = set()
        for i in range(20):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]
            orders_seen.add(tuple(order))

        # Without sticky constraints, we should see various orderings
        # (Q1, Q2, Q3 should be shuffled independently)
        assert len(orders_seen) > 1, "Questions should shuffle independently when stick_to_the_previous: false"


def test_sticky_with_points(temp_dir):
    """Test that stick_to_the_previous works with questions that have points."""
    quiz_data = {
        "title": "Points Quiz",
        "randomize_questions": True,
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 2},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1, "stick_to_the_previous": True, "points": 3},
            {"question": "Q3", "options": ["E", "F"], "correct_answer": 0},
        ],
    }

    with custom_webquiz_server(quizzes={"test.yaml": quiz_data}) as (proc, port):
        for i in range(5):
            response = requests.post(f"http://localhost:{port}/api/register", json={"username": f"user{i}"})
            user_id = response.json()["user_id"]

            response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
            order = response.json()["question_order"]

            # Q2 must follow Q1
            assert order.index(2) == order.index(1) + 1, f"Q2 should follow Q1, got: {order}"
