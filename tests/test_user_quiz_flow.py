"""
Test complete user quiz flow including registration, answering questions, and checking results.

This test module verifies the full user journey through the WebQuiz system:
1. User registration (reservation)
2. Answering all questions in sequence
3. Checking final results
4. Session persistence and verification

This covers the API flow for a user actually passing through the quiz.
"""
import pytest
import requests
import json
import time
import uuid
from conftest import get_worker_port


class TestUserQuizFlow:
    """Test complete user quiz flow from registration to results."""
    
    def test_complete_user_quiz_flow(self, webquiz_server):
        """Test complete user flow: registration -> answering questions -> checking results."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Step 1: User Registration (Reservation)
        username = f'test_user_{uuid.uuid4().hex[:8]}'
        register_data = {'username': username}
        
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 200
        
        register_result = response.json()
        assert 'user_id' in register_result
        assert 'username' in register_result
        assert register_result['username'] == username
        assert 'message' in register_result
        assert register_result['message'] == 'User registered successfully'
        
        user_id = register_result['user_id']
        
        # Verify user_id is a valid UUID
        uuid.UUID(user_id)  # This will raise ValueError if not valid UUID
        
        # Step 2: Verify user session immediately after registration
        response = requests.get(f'{base_url}/api/verify-user/{user_id}')
        assert response.status_code == 200
        
        verify_result = response.json()
        assert verify_result['valid'] is True
        assert verify_result['user_id'] == user_id
        assert verify_result['username'] == username
        assert verify_result['next_question_index'] == 0
        assert verify_result['total_questions'] > 0
        assert verify_result['last_answered_question_id'] == 0
        assert verify_result['test_completed'] is False
        
        total_questions = verify_result['total_questions']
        
        # Step 3: Answer all questions in sequence
        question_results = []
        for question_index in range(total_questions):
            question_id = question_index + 1  # Questions are 1-indexed
            
            # Submit answer (we'll use answer index 0 for simplicity)
            answer_data = {
                'user_id': user_id,
                'question_id': question_id,
                'selected_answer': 0  # Always select first option
            }
            
            response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
            assert response.status_code == 200
            
            answer_result = response.json()
            assert 'is_correct' in answer_result
            assert 'time_taken' in answer_result
            assert 'message' in answer_result
            assert answer_result['message'] == 'Answer submitted successfully'
            assert isinstance(answer_result['time_taken'], (int, float))
            assert answer_result['time_taken'] >= 0
            
            question_results.append({
                'question_id': question_id,
                'is_correct': answer_result['is_correct'],
                'time_taken': answer_result['time_taken']
            })
            
            # Verify user progress after each answer
            response = requests.get(f'{base_url}/api/verify-user/{user_id}')
            assert response.status_code == 200
            
            progress_result = response.json()
            assert progress_result['valid'] is True
            assert progress_result['last_answered_question_id'] == question_id
            
            if question_index < total_questions - 1:
                # Not the last question
                assert progress_result['next_question_index'] == question_index + 1
                assert progress_result['test_completed'] is False
                assert 'final_results' not in progress_result
            else:
                # Last question - test should be completed
                assert progress_result['next_question_index'] == total_questions
                assert progress_result['test_completed'] is True
                assert 'final_results' in progress_result
        
        # Step 4: Check final results after test completion
        response = requests.get(f'{base_url}/api/verify-user/{user_id}')
        assert response.status_code == 200
        
        final_verify = response.json()
        assert final_verify['valid'] is True
        assert final_verify['test_completed'] is True
        assert 'final_results' in final_verify
        
        final_results = final_verify['final_results']
        assert 'test_results' in final_results
        assert 'correct_count' in final_results
        assert 'total_count' in final_results
        assert 'percentage' in final_results
        assert 'total_time' in final_results
        
        # Verify final results integrity
        assert final_results['total_count'] == total_questions
        assert len(final_results['test_results']) == total_questions
        assert 0 <= final_results['correct_count'] <= total_questions
        assert 0 <= final_results['percentage'] <= 100
        assert final_results['total_time'] >= 0
        
        # Verify individual question results in final results
        test_results = final_results['test_results']
        for i, result in enumerate(test_results):
            assert 'question' in result
            assert 'selected_answer' in result
            assert 'correct_answer' in result
            assert 'is_correct' in result
            assert 'time_taken' in result
            
            # Match with our recorded results
            recorded_result = question_results[i]
            assert result['is_correct'] == recorded_result['is_correct']
            assert abs(result['time_taken'] - recorded_result['time_taken']) < 1.0  # Allow 1s tolerance
        
        # Calculate expected percentage and verify
        correct_answers = sum(1 for r in question_results if r['is_correct'])
        expected_percentage = round((correct_answers / total_questions) * 100)
        assert final_results['percentage'] == expected_percentage
        assert final_results['correct_count'] == correct_answers


    def test_user_registration_with_duplicate_username(self, webquiz_server):
        """Test that duplicate usernames are rejected."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Register first user
        username = f'duplicate_test_{uuid.uuid4().hex[:8]}'
        register_data = {'username': username}
        
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 200
        
        # Try to register second user with same username
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 400
        
        error_result = response.json()
        assert 'error' in error_result
        assert 'already exists' in error_result['error'].lower()


    def test_user_registration_with_empty_username(self, webquiz_server):
        """Test that empty usernames are rejected."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Test with empty username
        register_data = {'username': ''}
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 400
        
        error_result = response.json()
        assert 'error' in error_result
        assert 'empty' in error_result['error'].lower()
        
        # Test with whitespace-only username
        register_data = {'username': '   '}
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 400


    def test_submit_answer_with_invalid_user(self, webquiz_server):
        """Test submitting answer with non-existent user ID."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Use a fake user ID
        fake_user_id = str(uuid.uuid4())
        answer_data = {
            'user_id': fake_user_id,
            'question_id': 1,
            'selected_answer': 0
        }
        
        response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
        assert response.status_code == 404
        
        error_result = response.json()
        assert 'error' in error_result
        assert 'not found' in error_result['error'].lower()


    def test_submit_answer_with_invalid_question(self, webquiz_server):
        """Test submitting answer for non-existent question."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Register a user first
        username = f'test_invalid_q_{uuid.uuid4().hex[:8]}'
        register_data = {'username': username}
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 200
        user_id = response.json()['user_id']
        
        # Try to answer a question that doesn't exist
        answer_data = {
            'user_id': user_id,
            'question_id': 9999,  # Non-existent question
            'selected_answer': 0
        }
        
        response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
        assert response.status_code == 404
        
        error_result = response.json()
        assert 'error' in error_result
        assert 'question not found' in error_result['error'].lower()


    def test_verify_invalid_user_id(self, webquiz_server):
        """Test verifying non-existent user ID."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Use a fake user ID
        fake_user_id = str(uuid.uuid4())
        response = requests.get(f'{base_url}/api/verify-user/{fake_user_id}')
        assert response.status_code == 200
        
        verify_result = response.json()
        assert verify_result['valid'] is False
        assert 'message' in verify_result
        assert 'not found' in verify_result['message'].lower()


    def test_answer_timing_accuracy(self, webquiz_server):
        """Test that answer timing is measured accurately."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Register user
        username = f'timing_test_{uuid.uuid4().hex[:8]}'
        register_data = {'username': username}
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 200
        user_id = response.json()['user_id']
        
        # Wait a specific amount of time before answering
        wait_time = 2.0  # Wait 2 seconds
        time.sleep(wait_time)
        
        # Submit answer
        answer_data = {
            'user_id': user_id,
            'question_id': 1,
            'selected_answer': 0
        }
        
        response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
        assert response.status_code == 200
        
        answer_result = response.json()
        measured_time = answer_result['time_taken']
        
        # Allow 0.5s tolerance for network and processing delays
        assert measured_time >= wait_time - 0.5
        assert measured_time <= wait_time + 1.0  # Upper bound more generous


    def test_session_persistence_across_verify_calls(self, webquiz_server):
        """Test that user session persists across multiple verify calls."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Register user
        username = f'persistence_test_{uuid.uuid4().hex[:8]}'
        register_data = {'username': username}
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 200
        user_id = response.json()['user_id']
        
        # Get total questions
        response = requests.get(f'{base_url}/api/verify-user/{user_id}')
        total_questions = response.json()['total_questions']
        
        # Verify user multiple times and answer questions up to total available
        max_questions = min(3, total_questions)
        for i in range(max_questions):
            response = requests.get(f'{base_url}/api/verify-user/{user_id}')
            assert response.status_code == 200
            
            verify_result = response.json()
            assert verify_result['valid'] is True
            assert verify_result['user_id'] == user_id
            assert verify_result['username'] == username
            
            # Answer a question if not the last iteration and if there are more questions
            if i < max_questions - 1 and i + 1 <= total_questions:
                answer_data = {
                    'user_id': user_id,
                    'question_id': i + 1,
                    'selected_answer': 0
                }
                response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
                assert response.status_code == 200


    def test_partial_quiz_completion_and_resume(self, webquiz_server):
        """Test that user can resume quiz after partial completion."""
        _, port = webquiz_server
        base_url = f'http://localhost:{port}'
        
        # Register user
        username = f'resume_test_{uuid.uuid4().hex[:8]}'
        register_data = {'username': username}
        response = requests.post(f'{base_url}/api/register', json=register_data)
        assert response.status_code == 200
        user_id = response.json()['user_id']
        
        # Get total questions
        response = requests.get(f'{base_url}/api/verify-user/{user_id}')
        total_questions = response.json()['total_questions']
        
        # Answer only first question (partial completion)
        answer_data = {
            'user_id': user_id,
            'question_id': 1,
            'selected_answer': 0
        }
        response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
        assert response.status_code == 200
        
        # Verify state after partial completion
        response = requests.get(f'{base_url}/api/verify-user/{user_id}')
        assert response.status_code == 200
        
        verify_result = response.json()
        assert verify_result['valid'] is True
        assert verify_result['last_answered_question_id'] == 1
        assert verify_result['next_question_index'] == 1  # Index to next question (0-based)
        assert verify_result['test_completed'] is (total_questions == 1)  # Handle single-question quiz
        
        if total_questions == 1:
            # Single question quiz - test is completed
            assert 'final_results' in verify_result
            return  # Skip resume part for single-question quiz
        
        assert verify_result['test_completed'] is False
        assert 'final_results' not in verify_result
        
        # Resume and complete the quiz
        for question_id in range(2, total_questions + 1):
            answer_data = {
                'user_id': user_id,
                'question_id': question_id,
                'selected_answer': 0
            }
            response = requests.post(f'{base_url}/api/submit-answer', json=answer_data)
            assert response.status_code == 200
        
        # Verify completion
        response = requests.get(f'{base_url}/api/verify-user/{user_id}')
        assert response.status_code == 200
        
        final_verify = response.json()
        assert final_verify['test_completed'] is True
        assert 'final_results' in final_verify