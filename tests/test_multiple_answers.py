"""
Test suite for multiple correct answers functionality
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from webquiz.server import TestingServer, WebQuizConfig


class TestMultipleAnswersValidation:
    """Test the multiple answers validation logic"""

    def setup_method(self):
        """Setup test server with multiple choice questions"""
        self.config = WebQuizConfig()
        self.server = TestingServer(self.config)

        # Test questions with various configurations
        self.server.questions = [
            {
                'id': 1,
                'question': 'Single answer question',
                'options': ['A', 'B', 'C', 'D'],
                'correct_answer': 1
            },
            {
                'id': 2,
                'question': 'Multiple answers - all required',
                'options': ['Python', 'HTML', 'JavaScript', 'CSS'],
                'correct_answer': [0, 2]
            },
            {
                'id': 3,
                'question': 'Multiple answers - minimum required',
                'options': ['Red', 'Green', 'Blue', 'Yellow'],
                'correct_answer': [0, 2, 3],
                'min_correct': 2
            }
        ]

    def test_single_answer_validation(self):
        """Test validation of single answer questions"""
        question = self.server.questions[0]

        # Correct answer
        assert self.server._validate_answer(1, question) == True

        # Incorrect answer
        assert self.server._validate_answer(0, question) == False
        assert self.server._validate_answer(2, question) == False

    def test_multiple_answers_all_required(self):
        """Test validation when all correct answers are required"""
        question = self.server.questions[1]

        # All correct answers
        assert self.server._validate_answer([0, 2], question) == True
        assert self.server._validate_answer([2, 0], question) == True  # Order shouldn't matter

        # Partial correct answers (should fail)
        assert self.server._validate_answer([0], question) == False
        assert self.server._validate_answer([2], question) == False

        # Incorrect answers included (should fail)
        assert self.server._validate_answer([0, 1, 2], question) == False
        assert self.server._validate_answer([0, 2, 3], question) == False

        # All wrong answers
        assert self.server._validate_answer([1, 3], question) == False

    def test_multiple_answers_minimum_required(self):
        """Test validation when minimum correct answers are required"""
        question = self.server.questions[2]

        # All correct answers
        assert self.server._validate_answer([0, 2, 3], question) == True

        # Minimum correct answers (2 out of 3)
        assert self.server._validate_answer([0, 2], question) == True
        assert self.server._validate_answer([0, 3], question) == True
        assert self.server._validate_answer([2, 3], question) == True

        # Less than minimum correct (should fail)
        assert self.server._validate_answer([0], question) == False
        assert self.server._validate_answer([2], question) == False

        # Any incorrect answer included (should fail)
        assert self.server._validate_answer([0, 1, 2], question) == False
        assert self.server._validate_answer([0, 2, 1], question) == False

    def test_invalid_answer_formats(self):
        """Test validation with invalid answer formats"""
        single_q = self.server.questions[0]
        multiple_q = self.server.questions[1]

        # Wrong type for single answer
        assert self.server._validate_answer([1], single_q) == False
        assert self.server._validate_answer("1", single_q) == False

        # Wrong type for multiple answer
        assert self.server._validate_answer(0, multiple_q) == False
        assert self.server._validate_answer("0,2", multiple_q) == False

        # Invalid option indices
        assert self.server._validate_answer([0, 5], multiple_q) == False
        assert self.server._validate_answer([-1], single_q) == False

    def test_csv_formatting(self):
        """Test CSV answer formatting with | separator"""
        question = self.server.questions[1]

        # Single answer formatting
        assert self.server._format_answer_text(1, ['A', 'B', 'C']) == 'B'

        # Multiple answers formatting (should be sorted)
        assert self.server._format_answer_text([2, 0], ['A', 'B', 'C', 'D']) == 'A|C'
        assert self.server._format_answer_text([1, 3, 0], ['A', 'B', 'C', 'D']) == 'A|B|D'

        # Empty or invalid inputs
        assert self.server._format_answer_text([], ['A', 'B']) == ''


class TestMultipleAnswersAPI:
    """Test API endpoints with multiple answers"""

    @pytest.mark.asyncio
    async def test_submit_multiple_answers(self):
        """Test submitting multiple answers via API"""
        config = WebQuizConfig()
        server = TestingServer(config)

        # Setup test questions
        server.questions = [
            {
                'id': 1,
                'question': 'Multiple choice test',
                'options': ['A', 'B', 'C', 'D'],
                'correct_answer': [0, 2]
            }
        ]

        # Mock user and timing
        user_id = 'test-user'
        server.users[user_id] = {'username': 'testuser'}
        server.question_start_times[user_id] = MagicMock()

        # Mock request
        mock_request = MagicMock()
        async def mock_json():
            return {
                'user_id': user_id,
                'question_id': 1,
                'selected_answer': [0, 2]  # Correct multiple answers
            }
        mock_request.json = mock_json

        with patch('webquiz.server.datetime') as mock_datetime:
            mock_datetime.now.return_value = MagicMock()
            response = await server.submit_answer(mock_request)

        # Should be successful
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """Test that existing single-answer quizzes still work"""
        config = WebQuizConfig()
        server = TestingServer(config)

        # Setup traditional single answer question
        server.questions = [
            {
                'id': 1,
                'question': 'Traditional single answer',
                'options': ['A', 'B', 'C', 'D'],
                'correct_answer': 2
            }
        ]

        # Mock user and timing
        user_id = 'test-user'
        server.users[user_id] = {'username': 'testuser'}
        server.question_start_times[user_id] = MagicMock()

        # Mock request with single answer
        mock_request = MagicMock()
        async def mock_json():
            return {
                'user_id': user_id,
                'question_id': 1,
                'selected_answer': 2  # Single answer format
            }
        mock_request.json = mock_json

        with patch('webquiz.server.datetime') as mock_datetime:
            mock_datetime.now.return_value = MagicMock()
            response = await server.submit_answer(mock_request)

        # Should be successful
        assert response.status == 200


class TestQuizValidation:
    """Test quiz data validation for multiple answers"""

    def setup_method(self):
        self.config = WebQuizConfig()
        self.server = TestingServer(self.config)

    def test_valid_multiple_answer_quiz(self):
        """Test validation of valid multiple answer quiz"""
        quiz_data = {
            'title': 'Test Quiz',
            'questions': [
                {
                    'question': 'Multiple choice question',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_answer': [0, 2]
                },
                {
                    'question': 'Single choice question',
                    'options': ['Yes', 'No'],
                    'correct_answer': 1
                }
            ]
        }

        errors = []
        assert self.server._validate_quiz_data(quiz_data, errors) == True
        assert len(errors) == 0

    def test_invalid_multiple_answer_quiz(self):
        """Test validation catches invalid multiple answer configurations"""
        # Empty correct_answer array
        quiz_data = {
            'questions': [
                {
                    'question': 'Invalid question',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': []
                }
            ]
        }

        errors = []
        assert self.server._validate_quiz_data(quiz_data, errors) == False
        assert any('correct_answer array cannot be empty' in error for error in errors)

    def test_min_correct_validation(self):
        """Test validation of min_correct field"""
        # Valid min_correct
        quiz_data = {
            'questions': [
                {
                    'question': 'Test question',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_answer': [0, 1, 2],
                    'min_correct': 2
                }
            ]
        }

        errors = []
        assert self.server._validate_quiz_data(quiz_data, errors) == True
        assert len(errors) == 0

        # Invalid min_correct (exceeds correct answers)
        quiz_data['questions'][0]['min_correct'] = 5
        errors = []
        assert self.server._validate_quiz_data(quiz_data, errors) == False
        assert any('min_correct cannot exceed number of correct answers' in error for error in errors)

    def test_min_correct_single_answer_error(self):
        """Test that min_correct is rejected for single answer questions"""
        quiz_data = {
            'questions': [
                {
                    'question': 'Single answer with min_correct',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': 1,
                    'min_correct': 1
                }
            ]
        }

        errors = []
        assert self.server._validate_quiz_data(quiz_data, errors) == False
        assert any('min_correct is only valid for multiple answer questions' in error for error in errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])