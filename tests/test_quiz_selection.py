import pytest
import pytest_asyncio
import tempfile
import os
import shutil
import yaml
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp.test_utils import TestClient, TestServer
from webquiz.server import TestingServer, create_app, WebQuizConfig


class TestQuizSelection:
    """Test quiz selection and loading functionality"""
    
    @pytest_asyncio.fixture
    async def temp_quizzes_dir(self):
        """Create a temporary quizzes directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest_asyncio.fixture
    async def config_with_temp_dir(self, temp_quizzes_dir):
        """Create config with temporary quizzes directory"""
        config = WebQuizConfig()
        config.paths.quizzes_dir = temp_quizzes_dir
        config.paths.logs_dir = "test-logs"
        config.paths.csv_dir = "test-csv"
        config.paths.static_dir = "test-static"
        config.admin.master_key = "test-master-key"
        return config
    
    def create_quiz_file(self, quiz_dir, filename, questions_data):
        """Helper to create a quiz YAML file"""
        quiz_path = os.path.join(quiz_dir, filename)
        with open(quiz_path, 'w') as f:
            yaml.dump(questions_data, f)
        return quiz_path
    
    async def test_no_quiz_files_creates_default(self, config_with_temp_dir):
        """Test that when no quiz files exist, a default is created"""
        # Ensure the quizzes directory is empty
        assert len(os.listdir(config_with_temp_dir.paths.quizzes_dir)) == 0
        
        server = TestingServer(config_with_temp_dir)
        
        # Mock file operations except the ones we want to test
        with patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.create_default_index_html', new_callable=AsyncMock):
            
            await server.load_questions()
        
        # Check that default.yaml was created
        default_path = os.path.join(config_with_temp_dir.paths.quizzes_dir, 'default.yaml')
        assert os.path.exists(default_path)
        
        # Check that questions were loaded
        assert len(server.questions) > 0
        assert server.current_quiz_file == default_path
    
    async def test_single_quiz_file_loaded_as_default(self, config_with_temp_dir):
        """Test that a single quiz file is automatically loaded"""
        quiz_data = {
            'questions': [
                {
                    'id': 1,
                    'question': 'Single quiz question?',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': 0
                }
            ]
        }
        
        # Create a single quiz file
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'math_test.yaml', quiz_data)
        
        server = TestingServer(config_with_temp_dir)
        
        with patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.create_default_index_html', new_callable=AsyncMock):
            
            await server.load_questions()
        
        # Check that the single quiz was loaded
        assert len(server.questions) == 1
        assert server.questions[0]['question'] == 'Single quiz question?'
        assert 'math_test.yaml' in server.current_quiz_file
    
    async def test_multiple_files_with_default_loads_default(self, config_with_temp_dir):
        """Test that when multiple files exist with default.yaml, default.yaml is loaded"""
        quiz_data1 = {
            'questions': [
                {'id': 1, 'question': 'Default question?', 'options': ['A', 'B'], 'correct_answer': 0}
            ]
        }
        quiz_data2 = {
            'questions': [
                {'id': 1, 'question': 'Math question?', 'options': ['A', 'B'], 'correct_answer': 1}
            ]
        }
        
        # Create multiple quiz files including default.yaml
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'default.yaml', quiz_data1)
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'math_quiz.yaml', quiz_data2)
        
        server = TestingServer(config_with_temp_dir)
        
        with patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.create_default_index_html', new_callable=AsyncMock):
            
            await server.load_questions()
        
        # Check that default.yaml was loaded (not math_quiz.yaml)
        assert len(server.questions) == 1
        assert server.questions[0]['question'] == 'Default question?'
        assert 'default.yaml' in server.current_quiz_file
    
    async def test_multiple_files_without_default_creates_admin_page(self, config_with_temp_dir):
        """Test that when multiple files exist without default.yaml, admin selection page is created"""
        quiz_data1 = {
            'questions': [
                {'id': 1, 'question': 'Math question?', 'options': ['A', 'B'], 'correct_answer': 0}
            ]
        }
        quiz_data2 = {
            'questions': [
                {'id': 1, 'question': 'Geography question?', 'options': ['A', 'B'], 'correct_answer': 1}
            ]
        }
        
        # Create multiple quiz files WITHOUT default.yaml
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'math_quiz.yaml', quiz_data1)
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'geography_quiz.yaml', quiz_data2)
        
        server = TestingServer(config_with_temp_dir)
        
        with patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock):
            
            await server.load_questions()
        
        # Check that no quiz was loaded
        assert len(server.questions) == 0
        assert server.current_quiz_file is None
        
        # Check that admin selection page was created
        index_path = os.path.join(config_with_temp_dir.paths.static_dir, 'index.html')
        assert os.path.exists(index_path)
        
        # Check content of admin selection page
        with open(index_path, 'r') as f:
            content = f.read()
            assert 'Quiz Selection Required' in content
            assert 'math_quiz.yaml' in content
            assert 'geography_quiz.yaml' in content
    
    async def test_quiz_switching_resets_state(self, config_with_temp_dir):
        """Test that switching quizzes properly resets server state"""
        quiz_data1 = {
            'questions': [
                {'id': 1, 'question': 'Quiz 1 question?', 'options': ['A', 'B'], 'correct_answer': 0}
            ]
        }
        quiz_data2 = {
            'questions': [
                {'id': 1, 'question': 'Quiz 2 question?', 'options': ['A', 'B'], 'correct_answer': 1}
            ]
        }
        
        # Create quiz files
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'quiz1.yaml', quiz_data1)
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'quiz2.yaml', quiz_data2)
        
        server = TestingServer(config_with_temp_dir)
        
        # Add some mock user data
        server.users['user1'] = {'username': 'testuser'}
        server.user_progress['user1'] = 1
        server.user_responses = [{'some': 'data'}]
        
        with patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.create_default_index_html', new_callable=AsyncMock):
            
            await server.switch_quiz('quiz2.yaml')
        
        # Check that state was reset
        assert len(server.users) == 0
        assert len(server.user_progress) == 0
        assert len(server.user_responses) == 0
        
        # Check that new quiz was loaded
        assert len(server.questions) == 1
        assert server.questions[0]['question'] == 'Quiz 2 question?'
        assert 'quiz2.yaml' in server.current_quiz_file
    
    async def test_csv_filename_generation_with_quiz_prefix(self, config_with_temp_dir):
        """Test that CSV files are generated with quiz name prefix"""
        server = TestingServer(config_with_temp_dir)
        
        # Test CSV path generation
        csv_path = server.generate_csv_path('math_quiz')
        expected_path = os.path.join(config_with_temp_dir.paths.csv_dir, 'math_quiz_user_responses.csv')
        assert csv_path == expected_path
        
        # Check that directory was created
        assert os.path.exists(config_with_temp_dir.paths.csv_dir)
    
    async def test_list_available_quizzes(self, config_with_temp_dir):
        """Test listing available quiz files"""
        quiz_data = {'questions': [{'id': 1, 'question': 'Test?', 'options': ['A'], 'correct_answer': 0}]}
        
        # Create multiple quiz files
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'math_quiz.yaml', quiz_data)
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'geography_quiz.yml', quiz_data)
        self.create_quiz_file(config_with_temp_dir.paths.quizzes_dir, 'not_a_quiz.txt', {'invalid': 'file'})
        
        server = TestingServer(config_with_temp_dir)
        
        available_quizzes = await server.list_available_quizzes()
        
        # Should only return YAML files, sorted
        assert len(available_quizzes) == 2
        assert 'geography_quiz.yml' in available_quizzes
        assert 'math_quiz.yaml' in available_quizzes
        assert 'not_a_quiz.txt' not in available_quizzes
        assert available_quizzes == sorted(available_quizzes)