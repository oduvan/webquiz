import pytest
import pytest_asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from webquiz.server import TestingServer, create_app, WebQuizConfig


@pytest_asyncio.fixture
async def server():
    """Create a test server instance"""
    # Create test config
    config = WebQuizConfig()
    config.paths.quizzes_dir = "test-quizzes"
    config.paths.logs_dir = "test-logs"
    config.paths.csv_dir = "test-csv"
    config.paths.static_dir = "test-static"
    config.admin.master_key = "test-master-key"
    
    test_server = TestingServer(config)
    # Don't initialize log file or CSV file for tests
    return test_server


@pytest_asyncio.fixture
async def app():
    """Create a test app instance"""
    # Create test static directory
    import os
    os.makedirs('test-static', exist_ok=True)
    
    # Create test config
    config = WebQuizConfig()
    config.paths.quizzes_dir = "test-quizzes"
    config.paths.logs_dir = "test-logs"
    config.paths.csv_dir = "test-csv"
    config.paths.static_dir = "test-static"
    config.admin.master_key = "test-master-key"
    
    # Create a proper async mock for initialize_log_file that sets the log_file attribute
    async def mock_initialize_log_file(self):
        self.log_file = "test-server.log"
    
    # Mock file operations to avoid creating actual files during tests
    with patch('webquiz.server.TestingServer.initialize_log_file', mock_initialize_log_file), \
         patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock), \
         patch('webquiz.server.TestingServer.load_questions', new_callable=AsyncMock), \
         patch('webquiz.server.TestingServer.create_default_index_html', new_callable=AsyncMock), \
         patch('logging.basicConfig'), \
         patch('asyncio.create_task'), \
         patch('webquiz.server.TestingServer.periodic_flush', new_callable=AsyncMock):  # Prevent background tasks during tests
        
        app = await create_app(config)
        
        # Access the server instance and set up test questions
        # The server instance is created inside create_app()
        # We need to patch it after creation
        test_server = None
        for route in app.router.routes():
            if hasattr(route, '_handler') and hasattr(route._handler, '__self__'):
                if isinstance(route._handler.__self__, TestingServer):
                    test_server = route._handler.__self__
                    break
        
        if test_server:
            # Set dummy log file for tests
            test_server.log_file = "test-server.log"
            test_server.questions = [
                {
                    'id': 1,
                    'question': 'Test question 1?',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_answer': 1
                },
                {
                    'id': 2,
                    'question': 'Test question 2?',
                    'options': ['W', 'X', 'Y', 'Z'],
                    'correct_answer': 2
                }
            ]
        
        yield app
        
        # Cleanup test static directory
        import shutil
        if os.path.exists('test-static'):
            shutil.rmtree('test-static')


@pytest_asyncio.fixture
async def client(app):
    """Create a test client for making HTTP requests"""
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.fixture
def test_user_data():
    """Sample user data for tests"""
    return {
        'username': 'testuser',
        'user_id': 'test-user-id-123'
    }


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('user_id,username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds\n')
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_yaml_file():
    """Create a temporary YAML file for testing"""
    import yaml
    
    test_questions = {
        'questions': [
            {
                'id': 1,
                'question': 'Test YAML question?',
                'options': ['Option A', 'Option B', 'Option C'],
                'correct_answer': 0
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(test_questions, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)