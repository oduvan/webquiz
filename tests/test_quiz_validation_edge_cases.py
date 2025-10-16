"""
Comprehensive edge case tests for quiz validation logic
Tests _validate_quiz_data method through the validation endpoint
"""

import requests
from conftest import custom_webquiz_server


def test_validate_quiz_invalid_data_type_not_dict(temp_dir):
    """Test validation rejects non-dictionary data"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        # Test with list instead of dict
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            headers=headers,
            json={"content": "- invalid\n- structure"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("словником" in error or "dictionary" in error.lower() for error in data["errors"])


def test_validate_quiz_missing_questions_field(temp_dir):
    """Test validation rejects quiz without 'questions' field"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: No Questions Quiz
description: This quiz has no questions field"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("questions" in error for error in data["errors"])


def test_validate_quiz_questions_not_list(temp_dir):
    """Test validation rejects when 'questions' is not a list"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Invalid Questions Type
questions: "not a list"  # Should be array"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("списком" in error or "list" in error.lower() for error in data["errors"])


def test_validate_quiz_empty_questions_array(temp_dir):
    """Test validation rejects empty questions array"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Empty Questions
questions: []"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("принаймні одне питання" in error or "at least" in error.lower() for error in data["errors"])


def test_validate_quiz_question_not_dict(temp_dir):
    """Test validation rejects non-dictionary questions"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Invalid Question Type
questions:
  - "string instead of object"
  - question: Valid question
    options: ['A', 'B']
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("dictionary" in error.lower() for error in data["errors"])


def test_validate_quiz_missing_required_fields(temp_dir):
    """Test validation rejects questions missing required fields"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        # Missing 'options'
        quiz_yaml1 = """title: Missing Options
questions:
  - question: Where are options?
    correct_answer: 0"""

        response1 = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml1}
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["valid"] is False
        assert any("options" in error for error in data1["errors"])

        # Missing 'correct_answer'
        quiz_yaml2 = """title: Missing Correct Answer
questions:
  - question: What's the answer?
    options: ['A', 'B', 'C']"""

        response2 = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml2}
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["valid"] is False
        assert any("correct_answer" in error for error in data2["errors"])


def test_validate_quiz_no_question_text_or_image(temp_dir):
    """Test validation rejects questions with neither text nor image"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: No Question Content
questions:
  - options: ['A', 'B']
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("question text or image" in error.lower() for error in data["errors"])


def test_validate_quiz_options_not_list(temp_dir):
    """Test validation rejects when options is not a list"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Options Not List
questions:
  - question: Test?
    options: "not a list"
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("options must be a list" in error.lower() for error in data["errors"])


def test_validate_quiz_options_too_few(temp_dir):
    """Test validation rejects questions with less than 2 options"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Too Few Options
questions:
  - question: Only one option?
    options: ['A']
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("at least 2 options" in error.lower() for error in data["errors"])


def test_validate_quiz_options_not_all_strings(temp_dir):
    """Test validation rejects when options contain non-string values"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Non-String Options
questions:
  - question: Test?
    options: ['A', 123, 'C']  # 123 is not a string
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("all options must be strings" in error.lower() for error in data["errors"])


def test_validate_quiz_correct_answer_out_of_range(temp_dir):
    """Test validation rejects correct_answer index out of range"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Answer Out of Range
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 5  # Index 5 doesn't exist"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("out of range" in error.lower() for error in data["errors"])


def test_validate_quiz_correct_answer_array_empty(temp_dir):
    """Test validation rejects empty correct_answer array"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Empty Answer Array
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    correct_answer: []  # Empty array"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("cannot be empty" in error.lower() for error in data["errors"])


def test_validate_quiz_correct_answer_array_non_integers(temp_dir):
    """Test validation rejects correct_answer array with non-integers"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Non-Integer Answers
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    correct_answer: [0, "1", 2]  # "1" is string"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("only integers" in error.lower() for error in data["errors"])


def test_validate_quiz_correct_answer_array_out_of_range(temp_dir):
    """Test validation rejects correct_answer array with out-of-range indices"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Answer Index Out of Range
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: [0, 5]  # 5 is out of range"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("out of range" in error.lower() for error in data["errors"])


def test_validate_quiz_correct_answer_array_duplicates(temp_dir):
    """Test validation rejects correct_answer array with duplicate indices"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Duplicate Answer Indices
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    correct_answer: [0, 1, 0]  # 0 appears twice"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("duplicate" in error.lower() for error in data["errors"])


def test_validate_quiz_correct_answer_wrong_type(temp_dir):
    """Test validation rejects correct_answer that's neither int nor array"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Wrong Answer Type
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: "zero"  # String instead of int"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("integer or array" in error.lower() for error in data["errors"])


def test_validate_quiz_min_correct_without_correct_answer(temp_dir):
    """Test validation rejects min_correct without correct_answer"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Min Correct Without Answer
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    min_correct: 2"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("min_correct but no correct_answer" in error.lower() for error in data["errors"])


def test_validate_quiz_min_correct_with_single_answer(temp_dir):
    """Test validation rejects min_correct with single answer question"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Min Correct With Single Answer
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    correct_answer: 1  # Single answer
    min_correct: 1  # min_correct only for multiple answers"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("only valid for multiple answer" in error.lower() for error in data["errors"])


def test_validate_quiz_min_correct_not_integer(temp_dir):
    """Test validation rejects non-integer min_correct"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Min Correct Not Integer
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    correct_answer: [0, 1, 2]
    min_correct: "two"  # String instead of int"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("min_correct must be an integer" in error.lower() for error in data["errors"])


def test_validate_quiz_min_correct_too_low(temp_dir):
    """Test validation rejects min_correct < 1"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Min Correct Too Low
questions:
  - question: Test?
    options: ['A', 'B', 'C']
    correct_answer: [0, 1]
    min_correct: 0  # Must be at least 1"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("at least 1" in error.lower() for error in data["errors"])


def test_validate_quiz_min_correct_exceeds_answers(temp_dir):
    """Test validation rejects min_correct > number of correct answers"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Min Correct Exceeds Answers
questions:
  - question: Test?
    options: ['A', 'B', 'C', 'D']
    correct_answer: [0, 1]  # 2 correct answers
    min_correct: 5  # Requires 5 but only 2 exist"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("cannot exceed" in error.lower() for error in data["errors"])


def test_validate_quiz_show_right_answer_not_boolean(temp_dir):
    """Test validation rejects non-boolean show_right_answer"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Invalid Show Right Answer Type
show_right_answer: "yes"  # Should be boolean
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("show_right_answer" in error and "boolean" in error.lower() for error in data["errors"])


def test_validate_quiz_randomize_questions_not_boolean(temp_dir):
    """Test validation rejects non-boolean randomize_questions"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: Invalid Randomize Type
randomize_questions: 1  # Should be boolean
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("randomize_questions" in error and "boolean" in error.lower() for error in data["errors"])


def test_validate_quiz_title_not_string(temp_dir):
    """Test validation rejects non-string title"""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Master-Key": "test123"}

        quiz_yaml = """title: 123  # Number instead of string
questions:
  - question: Test?
    options: ['A', 'B']
    correct_answer: 0"""

        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz", headers=headers, json={"content": quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("title" in error and "string" in error.lower() for error in data["errors"])
