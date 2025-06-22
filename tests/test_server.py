import pytest
import json
import uuid
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from webquiz.server import TestingServer


class TestTestingServer:
    """Test cases for TestingServer internal functionality not covered by integration tests"""
    
    @pytest.mark.asyncio
    async def test_csv_flush_functionality(self, server, temp_csv_file):
        """Test CSV flushing functionality"""
        # Add some test responses
        server.user_responses = [
            {
                'user_id': 'user1',
                'username': 'testuser1',
                'question_text': 'Test question 1?',
                'selected_answer_text': 'Answer A',
                'correct_answer_text': 'Answer B',
                'is_correct': False,
                'time_taken_seconds': 5.5
            },
            {
                'user_id': 'user2',
                'username': 'testuser2',
                'question_text': 'Test question 2?',
                'selected_answer_text': 'Answer X',
                'correct_answer_text': 'Answer X',
                'is_correct': True,
                'time_taken_seconds': 3.2
            }
        ]
        
        # Mock the CSV file path
        with patch('aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file
            
            await server.flush_responses_to_csv()
            
            # Check that CSV content was written
            mock_file.write.assert_called_once()
            written_content = mock_file.write.call_args[0][0]
            
            # Verify CSV content structure
            lines = written_content.strip().split('\n')
            assert len(lines) == 2  # Two response rows
            
            # Check first row
            first_row = lines[0].split(',')
            assert first_row[0] == 'user1'
            assert first_row[1] == 'testuser1'
            
            # Check that responses were cleared
            assert len(server.user_responses) == 0
    
    @pytest.mark.asyncio
    async def test_default_questions_creation(self, server):
        """Test default questions YAML file creation"""
        with patch('aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file
            
            await server.create_default_questions_yaml()
            
            # Check that file was written
            mock_file.write.assert_called_once()
            written_content = mock_file.write.call_args[0][0]
            
            # Verify YAML content contains expected structure
            assert 'questions:' in written_content
            assert 'What is 2 + 2?' in written_content
            assert 'What is the capital of France?' in written_content
    
    def test_user_data_structure(self, server):
        """Test that user data is stored with correct structure"""
        user_id = 'test-123'
        username = 'testuser'
        
        server.users[user_id] = {
            'user_id': user_id,
            'username': username,
            'registered_at': datetime.now().isoformat()
        }
        
        # Verify structure
        user_data = server.users[user_id]
        assert user_data['user_id'] == user_id
        assert user_data['username'] == username
        assert 'registered_at' in user_data
        
        # Verify userid-based access works
        assert user_id in server.users
        assert server.users[user_id]['username'] == username