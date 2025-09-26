"""
Integration tests for multiple choice functionality
"""
import pytest
import json
import yaml
import tempfile
import os
from aiohttp.test_utils import make_mocked_request
from webquiz.server import TestingServer, WebQuizConfig


@pytest.fixture
async def multiple_choice_server():
    """Create a test server with multiple choice questions"""
    config = WebQuizConfig()
    server = TestingServer(config)

    # Create temporary quiz file with mixed question types
    quiz_data = {
        'title': 'Integration Test Quiz',
        'show_right_answer': True,
        'questions': [
            {
                'question': 'Single answer: What is 2+2?',
                'options': ['3', '4', '5', '6'],
                'correct_answer': 1
            },
            {
                'question': 'Multiple answers: Which are programming languages?',
                'options': ['Python', 'HTML', 'JavaScript', 'CSS'],
                'correct_answer': [0, 2]
            },
            {
                'question': 'Minimum correct: Select at least 2 colors',
                'options': ['Red', 'Green', 'Blue', 'Yellow'],
                'correct_answer': [0, 2, 3],
                'min_correct': 2
            }
        ]
    }

    # Load quiz data into server
    await server.load_quiz_data(quiz_data)
    return server


class TestMultipleChoiceIntegration:
    """Integration tests for multiple choice functionality"""

    @pytest.mark.asyncio
    async def test_user_registration_and_progress(self, multiple_choice_server):
        """Test user registration works with multiple choice quizzes"""
        server = multiple_choice_server

        # Register user
        request = make_mocked_request('POST', '/api/register',
                                      json={'username': 'testuser'})
        response = await server.register_user(request)

        assert response.status == 200
        data = json.loads(response.text)
        user_id = data['user_id']

        # Verify user is in system
        assert user_id in server.users
        assert server.users[user_id]['username'] == 'testuser'

    @pytest.mark.asyncio
    async def test_mixed_question_types_submission(self, multiple_choice_server):
        """Test submitting answers for mixed single/multiple choice questions"""
        server = multiple_choice_server

        # Register user
        user_id = 'test-user-123'
        server.users[user_id] = {'username': 'testuser'}

        # Test 1: Submit single answer
        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 1,
                                          'selected_answer': 1
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == True

        # Test 2: Submit multiple answers (all correct)
        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 2,
                                          'selected_answer': [0, 2]
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == True
        assert data['is_multiple_choice'] == True

        # Test 3: Submit minimum correct answers
        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 3,
                                          'selected_answer': [0, 2]  # 2 out of 3 correct
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == True

    @pytest.mark.asyncio
    async def test_csv_export_format(self, multiple_choice_server):
        """Test CSV export includes proper formatting for multiple answers"""
        server = multiple_choice_server

        # Setup user and submit answers
        user_id = 'test-user-csv'
        server.users[user_id] = {'username': 'csvuser'}

        # Submit single answer
        server.user_responses.append({
            'user_id': user_id,
            'username': 'csvuser',
            'question_id': 1,
            'question_text': 'Single answer: What is 2+2?',
            'selected_answer_text': '4',
            'correct_answer_text': '4',
            'is_correct': True,
            'time_taken_seconds': 10.5,
            'timestamp': '2024-01-01T12:00:00'
        })

        # Submit multiple answers
        server.user_responses.append({
            'user_id': user_id,
            'username': 'csvuser',
            'question_id': 2,
            'question_text': 'Multiple answers: Which are programming languages?',
            'selected_answer_text': 'JavaScript|Python',  # Should be sorted
            'correct_answer_text': 'JavaScript|Python',
            'is_correct': True,
            'time_taken_seconds': 15.2,
            'timestamp': '2024-01-01T12:01:00'
        })

        # Verify CSV formatting
        responses = server.user_responses
        assert len(responses) == 2

        # Single answer response
        single_response = responses[0]
        assert single_response['selected_answer_text'] == '4'
        assert '|' not in single_response['selected_answer_text']

        # Multiple answer response
        multiple_response = responses[1]
        assert '|' in multiple_response['selected_answer_text']
        assert multiple_response['selected_answer_text'] == 'JavaScript|Python'

    @pytest.mark.asyncio
    async def test_incorrect_multiple_answers(self, multiple_choice_server):
        """Test incorrect multiple answer scenarios"""
        server = multiple_choice_server
        user_id = 'test-user-incorrect'
        server.users[user_id] = {'username': 'testuser'}

        # Test: Partial correct answers (should fail for all-required question)
        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 2,
                                          'selected_answer': [0]  # Only Python, missing JavaScript
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == False

        # Test: Including incorrect answer (should fail)
        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 2,
                                          'selected_answer': [0, 1, 2]  # Includes HTML
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == False

        # Test: Less than minimum required
        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 3,
                                          'selected_answer': [0]  # Only 1, need at least 2
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == False

    @pytest.mark.asyncio
    async def test_question_data_sent_to_client(self, multiple_choice_server):
        """Test that client receives proper question type information"""
        server = multiple_choice_server

        # Get questions for client
        client_questions = []
        for q in server.questions:
            client_question = {
                'id': q['id'],
                'options': q['options'],
                'is_multiple_choice': isinstance(q['correct_answer'], list)
            }
            if 'question' in q:
                client_question['question'] = q['question']
            if isinstance(q['correct_answer'], list):
                client_question['min_correct'] = q.get('min_correct', len(q['correct_answer']))
            client_questions.append(client_question)

        # Verify question 1 (single choice)
        q1 = client_questions[0]
        assert q1['is_multiple_choice'] == False
        assert 'min_correct' not in q1

        # Verify question 2 (multiple choice, all required)
        q2 = client_questions[1]
        assert q2['is_multiple_choice'] == True
        assert q2['min_correct'] == 2  # All correct answers required

        # Verify question 3 (multiple choice, minimum required)
        q3 = client_questions[2]
        assert q3['is_multiple_choice'] == True
        assert q3['min_correct'] == 2  # Explicitly set minimum

    @pytest.mark.asyncio
    async def test_backward_compatibility_existing_quiz(self):
        """Test that existing quiz files without multiple choice work"""
        config = WebQuizConfig()
        server = TestingServer(config)

        # Load traditional quiz format
        traditional_quiz = {
            'title': 'Traditional Quiz',
            'questions': [
                {
                    'question': 'What is the capital of France?',
                    'options': ['London', 'Berlin', 'Paris', 'Madrid'],
                    'correct_answer': 2
                },
                {
                    'question': 'Which language is Python?',
                    'options': ['Programming', 'Spoken', 'Dead'],
                    'correct_answer': 0
                }
            ]
        }

        await server.load_quiz_data(traditional_quiz)

        # Test submission with traditional format
        user_id = 'traditional-user'
        server.users[user_id] = {'username': 'traditionaluser'}

        request = make_mocked_request('POST', '/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 1,
                                          'selected_answer': 2
                                      })
        response = await server.submit_answer(request)

        assert response.status == 200
        data = json.loads(response.text)
        assert data['is_correct'] == True

        # Verify client data doesn't have multiple choice flags
        client_questions = []
        for q in server.questions:
            client_question = {
                'id': q['id'],
                'options': q['options'],
                'is_multiple_choice': isinstance(q['correct_answer'], list)
            }
            client_questions.append(client_question)

        assert all(not q['is_multiple_choice'] for q in client_questions)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])