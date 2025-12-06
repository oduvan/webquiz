"""
Integration tests for text input questions functionality
"""

import pytest
import requests
from tests.conftest import custom_webquiz_server


@pytest.fixture
def text_input_server():
    """Create a test server with text input questions"""
    quiz_data = {
        "title": "Text Input Test Quiz",
        "show_right_answer": True,
        "questions": [
            # Simple text question with exact match checker (detected by checker/correct_value)
            {
                "question": "What is 2+2? (Enter the number)",
                "default_value": "",
                "correct_value": "4",
                "checker": "assert user_answer.strip() == '4', 'Expected 4'",
                "points": 1,
            },
            # Text question with math checker
            {
                "question": "Calculate the square root of 16",
                "default_value": "",
                "correct_value": "4",
                "checker": "result = float(user_answer.strip())\nassert abs(result - sqrt(16)) < 0.01, f'Expected 4, got {result}'",
                "points": 2,
            },
            # Text question without checker (exact match with correct_value)
            {
                "question": "What is the capital of France?",
                "correct_value": "Paris",
                "points": 1,
            },
            # Mixed with choice question
            {
                "question": "What color is the sky?",
                "options": ["Red", "Blue", "Green"],
                "correct_answer": 1,
            },
        ],
    }

    quizzes = {"default.yaml": quiz_data}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        yield proc, port


class TestTextInputQuestions:
    """Integration tests for text input question functionality"""

    def test_text_question_correct_answer(self, text_input_server):
        """Test submitting correct text answer"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "testuser"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Submit correct text answer
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": "4"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == True
        assert data.get("is_text_question") == True
        assert data.get("correct_value") == "4"

    def test_text_question_incorrect_answer(self, text_input_server):
        """Test submitting incorrect text answer with checker error"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "testuser2"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Submit incorrect text answer
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": "5"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == False
        assert data.get("is_text_question") == True
        assert data.get("correct_value") == "4"
        assert "checker_error" in data
        assert "Expected 4" in data["checker_error"]

    def test_text_question_with_math_checker(self, text_input_server):
        """Test text question with math functions in checker"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "mathuser"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Skip first question
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": "4"}
        )

        # Submit correct answer to math question
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": "4"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == True

    def test_text_question_without_checker(self, text_input_server):
        """Test text question without checker (exact match)"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "nocheck"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Skip first two questions
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": "4"}
        )
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": "4"}
        )

        # Submit correct answer (exact match to correct_value)
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 3, "selected_answer": "Paris"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == True

        # Test incorrect answer
        response2 = requests.post(f"{base_url}/api/register", json={"username": "nocheck2"})
        user_id2 = response2.json()["user_id"]

        # Skip first two questions
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id2, "question_id": 1, "selected_answer": "4"}
        )
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id2, "question_id": 2, "selected_answer": "4"}
        )

        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id2, "question_id": 3, "selected_answer": "London"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == False

    def test_mixed_question_types(self, text_input_server):
        """Test quiz with mixed text and choice questions"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "mixeduser"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Submit text answer
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": "4"}
        )
        assert response.status_code == 200
        assert response.json()["is_correct"] == True

        # Submit more text answers
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 2, "selected_answer": "4"}
        )
        requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 3, "selected_answer": "Paris"}
        )

        # Submit choice answer
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 4, "selected_answer": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == True
        assert "is_text_question" not in data or data.get("is_text_question") != True

    def test_text_question_whitespace_handling(self, text_input_server):
        """Test that whitespace is handled correctly in text answers"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Register user
        response = requests.post(f"{base_url}/api/register", json={"username": "whitespace"})
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        # Submit answer with extra whitespace (checker uses .strip())
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": "  4  "}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] == True

    def test_client_receives_text_question_data(self, text_input_server):
        """Test that client receives proper text question data"""
        proc, port = text_input_server
        base_url = f"http://localhost:{port}"

        # Get the main page
        response = requests.get(base_url)
        assert response.status_code == 200
        html_content = response.text

        # Check that text question is present with type
        assert '"type": "text"' in html_content or '"type":"text"' in html_content
        assert "What is 2+2? (Enter the number)" in html_content
        assert "default_value" in html_content


class TestTextInputQuizValidation:
    """Test quiz validation for text input questions"""

    def test_valid_text_question_quiz(self):
        """Test that valid text question quiz passes validation"""
        quiz_data = {
            "title": "Valid Text Quiz",
            "questions": [
                {
                    "question": "Enter your answer:",
                    "default_value": "",
                    "correct_value": "test",
                    "checker": "assert user_answer == 'test'",
                }
            ],
        }

        quizzes = {"default.yaml": quiz_data}

        with custom_webquiz_server(quizzes=quizzes) as (proc, port):
            base_url = f"http://localhost:{port}"
            response = requests.get(base_url)
            assert response.status_code == 200

    def test_text_question_with_image(self):
        """Test text question can have associated image"""
        quiz_data = {
            "title": "Image Text Quiz",
            "questions": [
                {
                    "question": "Look at the image and answer:",
                    "image": "/imgs/test.png",
                    "correct_value": "answer",
                }
            ],
        }

        quizzes = {"default.yaml": quiz_data}

        with custom_webquiz_server(quizzes=quizzes) as (proc, port):
            base_url = f"http://localhost:{port}"
            response = requests.get(base_url)
            assert response.status_code == 200

    def test_text_question_with_points(self):
        """Test text question can have custom points"""
        quiz_data = {
            "title": "Points Text Quiz",
            "questions": [
                {"question": "Enter answer:", "correct_value": "test", "points": 5}
            ],
        }

        quizzes = {"default.yaml": quiz_data}

        with custom_webquiz_server(quizzes=quizzes) as (proc, port):
            base_url = f"http://localhost:{port}"

            # Register and answer
            response = requests.post(f"{base_url}/api/register", json={"username": "pointsuser"})
            user_id = response.json()["user_id"]

            response = requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": 1, "selected_answer": "test"},
            )
            assert response.status_code == 200


class TestCheckerTemplates:
    """Test checker templates API"""

    def test_list_checker_templates_empty(self):
        """Test listing checker templates when none configured"""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        quizzes = {"default.yaml": quiz_data}

        with custom_webquiz_server(quizzes=quizzes) as (proc, port):
            base_url = f"http://localhost:{port}"

            # Authenticate as admin
            response = requests.post(
                f"{base_url}/api/admin/auth", json={"master_key": "test123"}, allow_redirects=False
            )
            assert response.status_code == 200
            cookies = response.cookies

            # List templates
            response = requests.get(f"{base_url}/api/admin/list-checker-templates", cookies=cookies)
            assert response.status_code == 200
            data = response.json()
            assert "templates" in data
            assert isinstance(data["templates"], list)

    def test_list_checker_templates_with_config(self):
        """Test listing checker templates when configured"""
        quiz_data = {
            "title": "Test Quiz",
            "questions": [{"question": "Test?", "options": ["A", "B"], "correct_answer": 0}],
        }

        config = {
            "checker_templates": [
                {"name": "Exact Match", "code": "assert user_answer.strip() == 'expected'"},
                {"name": "Numeric Check", "code": "assert float(user_answer) == 42"},
            ]
        }

        quizzes = {"default.yaml": quiz_data}

        with custom_webquiz_server(config=config, quizzes=quizzes) as (proc, port):
            base_url = f"http://localhost:{port}"

            # Authenticate as admin
            response = requests.post(
                f"{base_url}/api/admin/auth", json={"master_key": "test123"}, allow_redirects=False
            )
            assert response.status_code == 200
            cookies = response.cookies

            # List templates
            response = requests.get(f"{base_url}/api/admin/list-checker-templates", cookies=cookies)
            assert response.status_code == 200
            data = response.json()
            assert "templates" in data
            assert len(data["templates"]) == 2
            assert data["templates"][0]["name"] == "Exact Match"
            assert data["templates"][1]["name"] == "Numeric Check"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
