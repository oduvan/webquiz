import pytest
import json


class TestIntegration:
    """Integration tests using real HTTP requests"""
    
    @pytest.mark.asyncio
    async def test_user_registration_flow(self, client):
        """Test complete user registration flow with real HTTP requests"""
        # Register a new user
        response = await client.post('/api/register', json={'username': 'testuser'})
        
        assert response.status == 200
        data = await response.json()
        assert data['username'] == 'testuser'
        assert 'user_id' in data
        assert data['message'] == 'User registered successfully'
        
        user_id = data['user_id']
        
        # Verify the user can be found
        response = await client.get(f'/api/verify-user/{user_id}')
        assert response.status == 200
        data = await response.json()
        assert data['valid'] is True
        assert data['username'] == 'testuser'
    
    @pytest.mark.asyncio
    async def test_duplicate_username_registration(self, client):
        """Test that duplicate usernames are rejected"""
        # Register first user
        response = await client.post('/api/register', json={'username': 'duplicate_test'})
        assert response.status == 200
        
        # Try to register second user with same username
        response = await client.post('/api/register', json={'username': 'duplicate_test'})
        assert response.status == 400
        data = await response.json()
        assert 'Username already exists' in data['error']
    
    @pytest.mark.asyncio
    async def test_empty_username_registration(self, client):
        """Test that empty usernames are rejected"""
        response = await client.post('/api/register', json={'username': ''})
        assert response.status == 400
        data = await response.json()
        assert 'Username cannot be empty' in data['error']
    
    @pytest.mark.asyncio
    async def test_answer_submission_flow(self, client):
        """Test complete answer submission flow"""
        # Register a user first
        response = await client.post('/api/register', json={'username': 'answer_test_user'})
        assert response.status == 200
        user_data = await response.json()
        user_id = user_data['user_id']
        
        # Submit a correct answer
        response = await client.post('/api/submit-answer', json={
            'user_id': user_id,
            'question_id': 1,
            'selected_answer': 1  # Correct answer based on test question setup
        })
        
        assert response.status == 200
        data = await response.json()
        assert data['is_correct'] is True
        assert 'time_taken' in data
        assert data['message'] == 'Answer submitted successfully'
    
    @pytest.mark.asyncio
    async def test_incorrect_answer_submission(self, client):
        """Test incorrect answer submission"""
        # Register a user first
        response = await client.post('/api/register', json={'username': 'incorrect_test_user'})
        assert response.status == 200
        user_data = await response.json()
        user_id = user_data['user_id']
        
        # Submit an incorrect answer
        response = await client.post('/api/submit-answer', json={
            'user_id': user_id,
            'question_id': 1,
            'selected_answer': 0  # Incorrect answer
        })
        
        assert response.status == 200
        data = await response.json()
        assert data['is_correct'] is False
        assert 'time_taken' in data
    
    @pytest.mark.asyncio
    async def test_submit_answer_nonexistent_user(self, client):
        """Test answer submission with non-existent user"""
        response = await client.post('/api/submit-answer', json={
            'user_id': 'non-existent-user-id',
            'question_id': 1,
            'selected_answer': 1
        })
        
        assert response.status == 404
        data = await response.json()
        assert data['error'] == 'User not found'
    
    @pytest.mark.asyncio
    async def test_submit_answer_nonexistent_question(self, client):
        """Test answer submission with non-existent question"""
        # Register a user first
        response = await client.post('/api/register', json={'username': 'question_test_user'})
        assert response.status == 200
        user_data = await response.json()
        user_id = user_data['user_id']
        
        # Submit answer for non-existent question
        response = await client.post('/api/submit-answer', json={
            'user_id': user_id,
            'question_id': 999,  # Non-existent question
            'selected_answer': 1
        })
        
        assert response.status == 404
        data = await response.json()
        assert data['error'] == 'Question not found'
    
    @pytest.mark.asyncio
    async def test_verify_nonexistent_user(self, client):
        """Test verification of non-existent user"""
        response = await client.get('/api/verify-user/non-existent-user-id')
        
        assert response.status == 200
        data = await response.json()
        assert data['valid'] is False
        assert data['message'] == 'User ID not found'
    
    @pytest.mark.asyncio
    async def test_complete_test_flow(self, client):
        """Test a complete test-taking flow"""
        # 1. Register user
        response = await client.post('/api/register', json={'username': 'complete_flow_user'})
        assert response.status == 200
        user_data = await response.json()
        user_id = user_data['user_id']
        
        # 2. Verify user
        response = await client.get(f'/api/verify-user/{user_id}')
        assert response.status == 200
        verify_data = await response.json()
        assert verify_data['valid'] is True
        assert verify_data['next_question_index'] == 0
        assert verify_data['total_questions'] == 2
        
        # 3. Submit answer for question 1
        response = await client.post('/api/submit-answer', json={
            'user_id': user_id,
            'question_id': 1,
            'selected_answer': 1
        })
        assert response.status == 200
        answer1_data = await response.json()
        assert answer1_data['is_correct'] is True
        
        # 4. Submit answer for question 2
        response = await client.post('/api/submit-answer', json={
            'user_id': user_id,
            'question_id': 2,
            'selected_answer': 2
        })
        assert response.status == 200
        answer2_data = await response.json()
        assert answer2_data['is_correct'] is True
        
        # 5. Verify user progress after completing questions
        response = await client.get(f'/api/verify-user/{user_id}')
        assert response.status == 200
        final_verify_data = await response.json()
        assert final_verify_data['valid'] is True
        assert final_verify_data['next_question_index'] == 2  # Completed both questions
    
    @pytest.mark.asyncio
    async def test_server_side_timing(self, client):
        """Test that server-side timing is working"""
        # Register user
        response = await client.post('/api/register', json={'username': 'timing_test_user'})
        assert response.status == 200
        user_data = await response.json()
        user_id = user_data['user_id']
        
        # Submit answer (server should calculate time automatically)
        response = await client.post('/api/submit-answer', json={
            'user_id': user_id,
            'question_id': 1,
            'selected_answer': 1
        })
        
        assert response.status == 200
        data = await response.json()
        assert 'time_taken' in data
        assert isinstance(data['time_taken'], (int, float))
        assert data['time_taken'] >= 0  # Should be non-negative
    
    @pytest.mark.asyncio
    async def test_malformed_requests(self, client):
        """Test handling of malformed requests"""
        # Missing username in registration
        response = await client.post('/api/register', json={})
        assert response.status == 400
        
        # Missing fields in answer submission
        response = await client.post('/api/submit-answer', json={'user_id': 'test'})
        assert response.status == 400
        
        # Invalid JSON
        response = await client.post('/api/register', data='invalid json')
        assert response.status == 400