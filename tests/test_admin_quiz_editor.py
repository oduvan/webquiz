"""Tests for admin quiz editor functionality with randomize_questions field."""

import pytest
import requests
import yaml
from tests.conftest import custom_webquiz_server


def test_create_quiz_with_randomize_questions_via_wizard(temp_dir):
    """Test creating a quiz with randomize_questions using wizard mode."""
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        quiz_data = {
            "title": "Test Quiz",
            "show_right_answer": True,
            "randomize_questions": True,
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            ],
        }

        # Create quiz via wizard mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_randomized", "mode": "wizard", "quiz_data": quiz_data},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify quiz was created with randomize_questions
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_randomized.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is True
        assert data["parsed"]["show_right_answer"] is True


def test_create_quiz_without_randomize_questions_defaults_false(temp_dir):
    """Test that omitting randomize_questions in wizard mode defaults to false."""
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        quiz_data = {
            "title": "Test Quiz",
            "show_right_answer": False,
            # randomize_questions not specified
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
        }

        # Create quiz via wizard mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_no_randomize", "mode": "wizard", "quiz_data": quiz_data},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200

        # Verify quiz was created with randomize_questions as false
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_no_randomize.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        # When not specified in wizard, it should default to false
        assert data["parsed"].get("randomize_questions", False) is False


def test_edit_quiz_to_add_randomize_questions(temp_dir):
    """Test editing an existing quiz to add randomize_questions."""
    quiz_data = {
        "title": "Original Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
        ],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"editable.yaml": quiz_data}) as (proc, port):
        # First, verify the quiz doesn't have randomize_questions
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/editable.yaml", headers={"X-Master-Key": "test123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parsed"].get("randomize_questions", False) is False

        # Update quiz to enable randomize_questions
        updated_data = {
            "title": "Updated Quiz",
            "show_right_answer": True,
            "randomize_questions": True,
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2", "options": ["C", "D"], "correct_answer": 1},
            ],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/editable.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200

        # Verify randomize_questions was added
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/editable.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is True
        assert data["parsed"]["title"] == "Updated Quiz"


def test_randomize_questions_preserved_after_edit(temp_dir):
    """Test that randomize_questions setting is preserved when editing other quiz fields."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"randomized.yaml": quiz_data}) as (proc, port):
        # Get the quiz
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/randomized.yaml", headers={"X-Master-Key": "test123"}
        )
        assert response.status_code == 200
        original_data = response.json()["parsed"]

        # Edit quiz to change title but keep randomize_questions
        updated_data = {
            "title": "Updated Title",
            "randomize_questions": True,  # Explicitly keep it
            "questions": original_data["questions"],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/randomized.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200

        # Verify randomize_questions is still True
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/randomized.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is True
        assert data["parsed"]["title"] == "Updated Title"


def test_disable_randomize_questions_via_edit(temp_dir):
    """Test disabling randomize_questions on an existing randomized quiz."""
    quiz_data = {
        "title": "Randomized Quiz",
        "randomize_questions": True,
        "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
    }

    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config, quizzes={"to_disable.yaml": quiz_data}) as (proc, port):
        # Verify it starts with randomize_questions enabled
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/to_disable.yaml", headers={"X-Master-Key": "test123"}
        )
        assert response.status_code == 200
        assert response.json()["parsed"]["randomize_questions"] is True

        # Disable randomize_questions
        updated_data = {
            "title": "No Longer Randomized",
            "randomize_questions": False,
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0}],
        }

        response = requests.put(
            f"http://localhost:{port}/api/admin/quiz/to_disable.yaml",
            json={"mode": "wizard", "quiz_data": updated_data},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200

        # Verify randomize_questions is now False
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/to_disable.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["randomize_questions"] is False
        assert data["parsed"]["title"] == "No Longer Randomized"


def test_create_quiz_with_multiple_correct_answers_array_format(temp_dir):
    """Test creating a quiz with multiple correct answers (array format) via wizard mode.
    
    This test verifies that when creating a quiz with questions that have multiple
    correct answers (represented as an array like [0, 2]), the YAML content is 
    properly formatted and parseable, not malformed with just comma-separated values.
    """
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        quiz_data = {
            "title": "Multiple Choice Quiz",
            "questions": [
                {
                    "question": "Which are programming languages?",
                    "options": ["Python", "HTML", "JavaScript", "CSS"],
                    "correct_answer": [0, 2],  # Multiple correct answers as array
                },
                {
                    "question": "Select all even numbers",
                    "options": ["1", "2", "3", "4", "5", "6"],
                    "correct_answer": [1, 3, 5],  # Multiple correct answers as array
                    "min_correct": 2,  # Partial credit
                },
            ],
        }

        # Create quiz via wizard mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_multiple_answers", "mode": "wizard", "quiz_data": quiz_data},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify quiz was created with correct array format
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_multiple_answers.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        
        # Check parsed YAML structure - this is the most important check
        # The YAML should parse correctly with arrays as arrays
        assert data["parsed"]["questions"][0]["correct_answer"] == [0, 2]
        assert data["parsed"]["questions"][1]["correct_answer"] == [1, 3, 5]
        assert data["parsed"]["questions"][1]["min_correct"] == 2
        
        # Check raw YAML content formatting
        content = data["content"]
        
        # Verify YAML is valid - re-parse it to ensure it's not malformed
        parsed_content = yaml.safe_load(content)
        assert parsed_content["questions"][0]["correct_answer"] == [0, 2]
        assert parsed_content["questions"][1]["correct_answer"] == [1, 3, 5]
        
        # Ensure it's not malformed with the broken format like "correct_answer: 0,2"
        # The broken format would parse as a string "0,2" not an array [0, 2]
        # Python's yaml.dump produces multi-line array format by default, which is fine
        # But we want to ensure it's NOT the broken comma-only format
        lines = content.split('\n')
        for line in lines:
            if 'correct_answer:' in line and line.strip().startswith('correct_answer:'):
                # If correct_answer is on same line, it should be flow style [x, y] or just whitespace
                # It should NOT be like "correct_answer: 0,2" (without brackets)
                after_colon = line.split('correct_answer:')[1].strip()
                if after_colon and not after_colon.startswith('['):
                    # If there's content and it doesn't start with [, it's likely multi-line (OK)
                    # But let's check it's not the broken format
                    assert ',' not in after_colon or '[' in after_colon, \
                        f"Found malformed correct_answer format: {line}"
        
        # Verify min_correct is present in the YAML
        assert "min_correct: 2" in content or "min_correct:\n  2" in content, \
            "Second question should have min_correct field"


def test_create_quiz_with_array_answers_via_text_mode(temp_dir):
    """Test creating a quiz in text mode with array-formatted correct answers.
    
    This simulates what would happen if a user manually typed YAML with flow-style
    arrays [0, 2] in the text editor, which is the format that should be produced
    by the JavaScript syncWizardToText() function after the fix.
    """
    config = {"admin": {"master_key": "test123"}}

    with custom_webquiz_server(config=config) as (proc, port):
        # YAML content with flow-style arrays as would be produced by fixed JS
        yaml_content = """questions:
- question: "Which are programming languages?"
  options:
  - "Python"
  - "HTML"
  - "JavaScript"
  - "CSS"
  correct_answer: [0, 2]
- question: "Select all even numbers"
  options:
  - "1"
  - "2"
  - "3"
  - "4"
  - "5"
  - "6"
  correct_answer: [1, 3, 5]
  min_correct: 2
"""

        # Create quiz via text mode
        response = requests.post(
            f"http://localhost:{port}/api/admin/create-quiz",
            json={"filename": "test_text_arrays", "mode": "text", "content": yaml_content},
            headers={"X-Master-Key": "test123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify quiz was created and parses correctly
        response = requests.get(
            f"http://localhost:{port}/api/admin/quiz/test_text_arrays.yaml", headers={"X-Master-Key": "test123"}
        )

        assert response.status_code == 200
        data = response.json()
        
        # The key test: arrays should be parsed correctly
        assert data["parsed"]["questions"][0]["correct_answer"] == [0, 2]
        assert data["parsed"]["questions"][1]["correct_answer"] == [1, 3, 5]
        assert data["parsed"]["questions"][1]["min_correct"] == 2
