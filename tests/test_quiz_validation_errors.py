"""Tests for quiz validation error paths to improve coverage."""
import requests
import yaml
from conftest import custom_webquiz_server



# Test Quiz Validation

def test_validate_quiz_empty_content():
    with custom_webquiz_server() as (proc, port):
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": ""},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "empty" in str(data["errors"]).lower()
def test_validate_quiz_invalid_yaml_syntax():
    with custom_webquiz_server() as (proc, port):
        invalid_yaml = "title: Test\nquestions:\n  - question: What?\n   - invalid indentation"
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_yaml},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "YAML syntax error" in str(data["errors"])
def test_validate_quiz_not_a_dict():
    with custom_webquiz_server() as (proc, port):
        invalid_yaml = "just a string\n"
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_yaml},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
def test_validate_quiz_missing_questions_field():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"title": "Test Quiz"})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("questions" in err.lower() for err in data["errors"])
def test_validate_quiz_questions_not_a_list():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": "not a list"})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_empty_questions_list():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": []})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("принаймні одне" in err or "at least" in err.lower() for err in data["errors"])
def test_validate_quiz_question_not_a_dict():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": ["not a dict"]})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_missing_required_fields():
    with custom_webquiz_server() as (proc, port):
        # Missing options and correct_answer
        invalid_quiz = yaml.dump({"questions": [{"question": "What?"}]})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("options" in err.lower() for err in data["errors"])
        assert any("correct_answer" in err.lower() for err in data["errors"])
def test_validate_quiz_question_without_text_or_image():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"options": ["A", "B"], "correct_answer": 0}]}  # No question or image
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("question text or image" in err.lower() for err in data["errors"])
def test_validate_quiz_options_not_a_list():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": "not a list", "correct_answer": 0}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_too_few_options():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": [{"question": "What?", "options": ["A"], "correct_answer": 0}]})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("at least 2 options" in err.lower() for err in data["errors"])
def test_validate_quiz_options_not_all_strings():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": [{"question": "What?", "options": ["A", 123], "correct_answer": 0}]})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_correct_answer_out_of_range():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": 5}]}  # Index 5 > 1
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("out of range" in err.lower() for err in data["errors"])
def test_validate_quiz_correct_answer_negative():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": -1}]})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_multiple_answers_empty_array():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B", "C"], "correct_answer": []}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("cannot be empty" in err.lower() for err in data["errors"])
def test_validate_quiz_multiple_answers_not_all_integers():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B", "C"], "correct_answer": [0, "not_int"]}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_multiple_answers_index_out_of_range():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": [0, 5]}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_multiple_answers_duplicate_indices():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B", "C"], "correct_answer": [0, 1, 0]}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("duplicate" in err.lower() for err in data["errors"])
def test_validate_quiz_correct_answer_invalid_type():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": "not_valid"}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_min_correct_without_correct_answer():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump({"questions": [{"question": "What?", "options": ["A", "B"], "min_correct": 1}]})
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_min_correct_for_single_answer():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": 0, "min_correct": 1}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("only valid for multiple answer" in err.lower() for err in data["errors"])
def test_validate_quiz_min_correct_not_integer():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {
                "questions": [
                    {"question": "What?", "options": ["A", "B", "C"], "correct_answer": [0, 1], "min_correct": "2"}
                ]
            }
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
def test_validate_quiz_min_correct_less_than_one():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {
                "questions": [
                    {"question": "What?", "options": ["A", "B", "C"], "correct_answer": [0, 1], "min_correct": 0}
                ]
            }
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("at least 1" in err.lower() for err in data["errors"])
def test_validate_quiz_min_correct_exceeds_correct_answers():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {
                "questions": [
                    {"question": "What?", "options": ["A", "B", "C"], "correct_answer": [0, 1], "min_correct": 5}
                ]
            }
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("cannot exceed" in err.lower() for err in data["errors"])
def test_validate_quiz_show_right_answer_not_boolean():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {
                "show_right_answer": "yes",
                "questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": 0}],
            }
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("show_right_answer" in err.lower() and "boolean" in err.lower() for err in data["errors"])
def test_validate_quiz_randomize_questions_not_boolean():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {
                "randomize_questions": "yes",
                "questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": 0}],
            }
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("randomize_questions" in err.lower() and "boolean" in err.lower() for err in data["errors"])
def test_validate_quiz_title_not_string():
    with custom_webquiz_server() as (proc, port):
        invalid_quiz = yaml.dump(
            {"title": 123, "questions": [{"question": "What?", "options": ["A", "B"], "correct_answer": 0}]}
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": invalid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("title" in err.lower() and "string" in err.lower() for err in data["errors"])
def test_validate_quiz_valid_quiz_returns_success():
    with custom_webquiz_server() as (proc, port):
        valid_quiz = yaml.dump(
            {
                "title": "Test Quiz",
                "questions": [{"question": "What is 2+2?", "options": ["3", "4", "5"], "correct_answer": 1}],
            }
        )
        response = requests.post(
            f"http://localhost:{port}/api/admin/validate-quiz",
            json={"content": valid_quiz},
            headers={"X-Master-Key": "test123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["question_count"] == 1