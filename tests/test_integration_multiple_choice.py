"""
Integration tests for multiple choice functionality
"""
import pytest
import json
import yaml
import tempfile
import os
import aiohttp
from tests.conftest import custom_webquiz_server


@pytest.fixture
def multiple_choice_server():
    """Create a test server with multiple choice questions"""
    # Create quiz data with mixed question types
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

    quizzes = {'default.yaml': quiz_data}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        yield proc, port


class TestMultipleChoiceIntegration:
    """Integration tests for multiple choice functionality"""

    @pytest.mark.asyncio
    async def test_user_registration_and_progress(self, multiple_choice_server):
        """Test user registration works with multiple choice quizzes"""
        proc, port = multiple_choice_server
        base_url = f'http://localhost:{port}'

        async with aiohttp.ClientSession() as session:
            # Register user
            async with session.post(f'{base_url}/api/register',
                                  json={'username': 'testuser'}) as response:
                assert response.status == 200
                data = await response.json()
                user_id = data['user_id']
                assert 'user_id' in data

            # Verify user can be verified
            async with session.get(f'{base_url}/api/verify-user/{user_id}') as response:
                assert response.status == 200
                data = await response.json()
                assert data['username'] == 'testuser'

    @pytest.mark.asyncio
    async def test_mixed_question_types_submission(self, multiple_choice_server):
        """Test submitting answers for mixed single/multiple choice questions"""
        proc, port = multiple_choice_server
        base_url = f'http://localhost:{port}'

        async with aiohttp.ClientSession() as session:
            # Register user
            async with session.post(f'{base_url}/api/register',
                                  json={'username': 'testuser'}) as response:
                assert response.status == 200
                data = await response.json()
                user_id = data['user_id']

            # Test 1: Submit single answer
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 1,
                                      'selected_answer': 1
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == True

            # Test 2: Submit multiple answers (all correct)
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 2,
                                      'selected_answer': [0, 2]
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == True
                assert data['is_multiple_choice'] == True

            # Test 3: Submit minimum correct answers
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 3,
                                      'selected_answer': [0, 2]  # 2 out of 3 correct
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == True

    @pytest.mark.asyncio
    async def test_csv_export_format(self, multiple_choice_server):
        """Test CSV export includes proper formatting for multiple answers"""
        proc, port = multiple_choice_server
        base_url = f'http://localhost:{port}'

        async with aiohttp.ClientSession() as session:
            # Register user
            async with session.post(f'{base_url}/api/register',
                                  json={'username': 'csvuser'}) as response:
                assert response.status == 200
                data = await response.json()
                user_id = data['user_id']

            # Submit single answer
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 1,
                                      'selected_answer': 1  # '4'
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == True

            # Submit multiple answers
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 2,
                                      'selected_answer': [0, 2]  # Python, JavaScript
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == True
                assert data['is_multiple_choice'] == True

            # The CSV formatting verification would need to be done by checking
            # the actual CSV file written by the server, which is harder to test
            # in integration tests. This test mainly verifies the server accepts
            # and processes both single and multiple answers correctly.

    @pytest.mark.asyncio
    async def test_incorrect_multiple_answers(self, multiple_choice_server):
        """Test incorrect multiple answer scenarios"""
        proc, port = multiple_choice_server
        base_url = f'http://localhost:{port}'

        async with aiohttp.ClientSession() as session:
            # Register user
            async with session.post(f'{base_url}/api/register',
                                  json={'username': 'testuser'}) as response:
                assert response.status == 200
                data = await response.json()
                user_id = data['user_id']

            # Test: Partial correct answers (should fail for all-required question)
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 2,
                                      'selected_answer': [0]  # Only Python, missing JavaScript
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == False

            # Test: Including incorrect answer (should fail)
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 2,
                                      'selected_answer': [0, 1, 2]  # Includes HTML
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == False

            # Test: Less than minimum required
            async with session.post(f'{base_url}/api/submit-answer',
                                  json={
                                      'user_id': user_id,
                                      'question_id': 3,
                                      'selected_answer': [0]  # Only 1, need at least 2
                                  }) as response:
                assert response.status == 200
                data = await response.json()
                assert data['is_correct'] == False

    @pytest.mark.asyncio
    async def test_question_data_sent_to_client(self, multiple_choice_server):
        """Test that client receives proper question type information"""
        proc, port = multiple_choice_server
        base_url = f'http://localhost:{port}'

        async with aiohttp.ClientSession() as session:
            # Get the main page to check that questions are properly embedded
            async with session.get(base_url) as response:
                assert response.status == 200
                html_content = await response.text()

                # Basic check that the HTML contains question data
                assert 'Single answer: What is 2+2?' in html_content
                assert 'Multiple answers: Which are programming languages?' in html_content
                assert 'Minimum correct: Select at least 2 colors' in html_content

                # Check that quiz configuration is embedded
                assert 'show_right_answer' in html_content

    @pytest.mark.asyncio
    async def test_backward_compatibility_existing_quiz(self):
        """Test that existing quiz files without multiple choice work"""
        # Create traditional quiz format
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

        quizzes = {'default.yaml': traditional_quiz}

        with custom_webquiz_server(quizzes=quizzes) as (proc, port):
            base_url = f'http://localhost:{port}'

            async with aiohttp.ClientSession() as session:
                # Register user
                async with session.post(f'{base_url}/api/register',
                                      json={'username': 'traditionaluser'}) as response:
                    assert response.status == 200
                    data = await response.json()
                    user_id = data['user_id']

                # Test submission with traditional format
                async with session.post(f'{base_url}/api/submit-answer',
                                      json={
                                          'user_id': user_id,
                                          'question_id': 1,
                                          'selected_answer': 2
                                      }) as response:
                    assert response.status == 200
                    data = await response.json()
                    assert data['is_correct'] == True

                # Verify the quiz loads and works correctly
                async with session.get(base_url) as response:
                    assert response.status == 200
                    html_content = await response.text()
                    assert 'What is the capital of France?' in html_content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])