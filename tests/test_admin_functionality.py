import pytest
import pytest_asyncio
import tempfile
import os
import shutil
import yaml
from unittest.mock import AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from webquiz.server import TestingServer, create_app, WebQuizConfig


class TestAdminFunctionality:
    """Test admin interface and quiz management functionality"""
    
    @pytest_asyncio.fixture
    async def temp_quizzes_dir(self):
        """Create a temporary quizzes directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest_asyncio.fixture
    async def admin_app(self, temp_quizzes_dir):
        """Create a test app with admin functionality enabled"""
        # Create test quiz files
        quiz_data1 = {
            'questions': [
                {'id': 1, 'question': 'Math question?', 'options': ['1', '2'], 'correct_answer': 0}
            ]
        }
        quiz_data2 = {
            'questions': [
                {'id': 1, 'question': 'Geography question?', 'options': ['A', 'B'], 'correct_answer': 1}
            ]
        }
        
        # Create quiz files
        with open(os.path.join(temp_quizzes_dir, 'math_quiz.yaml'), 'w') as f:
            yaml.dump(quiz_data1, f)
        with open(os.path.join(temp_quizzes_dir, 'geography_quiz.yaml'), 'w') as f:
            yaml.dump(quiz_data2, f)
        
        # Create config
        config = WebQuizConfig()
        config.paths.quizzes_dir = temp_quizzes_dir
        config.paths.logs_dir = "test-logs"
        config.paths.csv_dir = "test-csv"
        config.paths.static_dir = "test-static"
        config.admin.master_key = "test-master-key"
        
        # Create a proper async mock for initialize_log_file that sets the log_file attribute
        async def mock_initialize_log_file(self):
            self.log_file = "test-server.log"
        
        # Mock file operations
        with patch('webquiz.server.TestingServer.initialize_log_file', mock_initialize_log_file), \
             patch('webquiz.server.TestingServer.initialize_csv', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.load_questions', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.create_default_index_html', new_callable=AsyncMock), \
             patch('webquiz.server.TestingServer.create_admin_selection_page', new_callable=AsyncMock), \
             patch('logging.basicConfig'), \
             patch('asyncio.create_task'), \
             patch('webquiz.server.TestingServer.periodic_flush', new_callable=AsyncMock):
            
            app = await create_app(config)
            
            # Set up test server instance with quiz files loaded
            test_server = None
            for route in app.router.routes():
                if hasattr(route, '_handler') and hasattr(route._handler, '__self__'):
                    if isinstance(route._handler.__self__, TestingServer):
                        test_server = route._handler.__self__
                        break
            
            if test_server:
                test_server.log_file = "test-server.log"
                # Set current quiz to None to simulate admin selection needed
                test_server.current_quiz_file = None
                test_server.questions = []
            
            yield app
    
    @pytest_asyncio.fixture
    async def admin_client(self, admin_app):
        """Create a test client for admin testing"""
        async with TestClient(TestServer(admin_app)) as client:
            yield client
    
    async def test_admin_auth_with_valid_master_key(self, admin_client):
        """Test admin authentication with valid master key"""
        response = await admin_client.post('/api/admin/auth', 
                                         headers={'X-Master-Key': 'test-master-key'},
                                         json={})
        
        assert response.status == 200
        data = await response.json()
        assert data['authenticated'] is True
        assert 'successful' in data['message']
    
    async def test_admin_auth_with_invalid_master_key(self, admin_client):
        """Test admin authentication with invalid master key"""
        response = await admin_client.post('/api/admin/auth', 
                                         headers={'X-Master-Key': 'wrong-key'},
                                         json={})
        
        assert response.status == 401
        data = await response.json()
        assert 'Invalid or missing master key' in data['error']
    
    async def test_admin_auth_with_missing_master_key(self, admin_client):
        """Test admin authentication with missing master key"""
        response = await admin_client.post('/api/admin/auth', json={})
        
        assert response.status == 401
        data = await response.json()
        assert 'Invalid or missing master key' in data['error']
    
    async def test_admin_auth_via_json_body(self, admin_client):
        """Test admin authentication via JSON body"""
        response = await admin_client.post('/api/admin/auth', 
                                         json={'master_key': 'test-master-key'})
        
        assert response.status == 200
        data = await response.json()
        assert data['authenticated'] is True
    
    async def test_list_quizzes_endpoint(self, admin_client):
        """Test listing available quizzes"""
        response = await admin_client.get('/api/admin/list-quizzes',
                                        headers={'X-Master-Key': 'test-master-key'})
        
        assert response.status == 200
        data = await response.json()
        assert 'quizzes' in data
        assert 'current_quiz' in data
        assert len(data['quizzes']) == 2
        assert 'math_quiz.yaml' in data['quizzes']
        assert 'geography_quiz.yaml' in data['quizzes']
    
    async def test_list_quizzes_without_auth(self, admin_client):
        """Test listing quizzes without authentication"""
        response = await admin_client.get('/api/admin/list-quizzes')
        
        assert response.status == 401
    
    async def test_switch_quiz_endpoint(self, admin_client):
        """Test switching to a different quiz"""
        # Mock the switch_quiz method to avoid file operations
        async def mock_switch_quiz(quiz_filename):
            # This is simulating the actual switch_quiz method call
            return None
        
        # Get the server instance and patch its method
        app = admin_client.server.app
        test_server = None
        for route in app.router.routes():
            if hasattr(route, '_handler') and hasattr(route._handler, '__self__'):
                if isinstance(route._handler.__self__, TestingServer):
                    test_server = route._handler.__self__
                    break
        
        if test_server:
            # Set up the server state for the test
            test_server.current_quiz_file = "test-quizzes/math_quiz.yaml"
            test_server.csv_file = "test-csv/math_quiz_user_responses.csv"
            
            with patch.object(test_server, 'switch_quiz', mock_switch_quiz):
                response = await admin_client.post('/api/admin/switch-quiz',
                                                 headers={'X-Master-Key': 'test-master-key'},
                                                 json={'quiz_filename': 'math_quiz.yaml'})
                
                assert response.status == 200
                data = await response.json()
                assert data['success'] is True
                assert data['current_quiz'] == 'math_quiz.yaml'
                assert 'csv_file' in data
    
    async def test_switch_quiz_nonexistent_file(self, admin_client):
        """Test switching to a nonexistent quiz file"""
        response = await admin_client.post('/api/admin/switch-quiz',
                                         headers={'X-Master-Key': 'test-master-key'},
                                         json={'quiz_filename': 'nonexistent.yaml'})
        
        assert response.status == 400
        data = await response.json()
        assert 'error' in data
    
    async def test_switch_quiz_without_auth(self, admin_client):
        """Test switching quiz without authentication"""
        response = await admin_client.post('/api/admin/switch-quiz',
                                         json={'quiz_filename': 'math_quiz.yaml'})
        
        assert response.status == 401
    
    async def test_admin_page_serves_correctly(self, admin_client):
        """Test that admin page is served correctly"""
        response = await admin_client.get('/admin')
        
        assert response.status == 200
        content = await response.text()
        assert 'WebQuiz Admin Panel' in content
        assert 'Master Key' in content
        assert 'Available Quiz Files' in content
    
    async def test_admin_endpoints_require_master_key_set(self):
        """Test that admin endpoints are disabled when no master key is set"""
        # Create config without master key
        config = WebQuizConfig()
        config.admin.master_key = None
        
        server = TestingServer(config)
        
        # Test auth endpoint
        from aiohttp import web
        from aiohttp.test_utils import make_mocked_request
        
        request = make_mocked_request('POST', '/api/admin/auth')
        response = await server.admin_auth_test(request)
        
        assert response.status == 403
        assert response.text == '{"error": "Admin functionality disabled - no master key set"}'
    
    async def test_admin_selection_page_shows_quiz_files(self, temp_quizzes_dir):
        """Test that admin selection page shows available quiz files"""
        config = WebQuizConfig()
        config.paths.quizzes_dir = temp_quizzes_dir
        config.paths.static_dir = "test-static"
        config.admin.master_key = "test123"
        
        # Create quiz files
        quiz_data = {'questions': [{'id': 1, 'question': 'Test?', 'options': ['A'], 'correct_answer': 0}]}
        with open(os.path.join(temp_quizzes_dir, 'quiz1.yaml'), 'w') as f:
            yaml.dump(quiz_data, f)
        with open(os.path.join(temp_quizzes_dir, 'quiz2.yaml'), 'w') as f:
            yaml.dump(quiz_data, f)
        
        server = TestingServer(config)
        
        # Create the admin selection page
        await server.create_admin_selection_page()
        
        # Check that the page was created
        index_path = os.path.join(config.paths.static_dir, 'index.html')
        assert os.path.exists(index_path)
        
        # Check content
        with open(index_path, 'r') as f:
            content = f.read()
            assert 'Quiz Selection Required' in content
            assert 'quiz1.yaml' in content
            assert 'quiz2.yaml' in content
            assert 'Access admin panel' in content  # Master key is set
    
    async def test_admin_selection_page_master_key_disabled(self, temp_quizzes_dir):
        """Test admin selection page when master key is not set"""
        config = WebQuizConfig()
        config.paths.quizzes_dir = temp_quizzes_dir
        config.paths.static_dir = "test-static"
        config.admin.master_key = None  # No master key
        
        # Create quiz files
        quiz_data = {'questions': [{'id': 1, 'question': 'Test?', 'options': ['A'], 'correct_answer': 0}]}
        with open(os.path.join(temp_quizzes_dir, 'quiz1.yaml'), 'w') as f:
            yaml.dump(quiz_data, f)
        
        server = TestingServer(config)
        
        # Create the admin selection page
        await server.create_admin_selection_page()
        
        # Check that the page was created
        index_path = os.path.join(config.paths.static_dir, 'index.html')
        assert os.path.exists(index_path)
        
        # Check content
        with open(index_path, 'r') as f:
            content = f.read()
            assert 'Quiz Selection Required' in content
            assert 'Admin panel disabled' in content  # No master key
            assert 'disabled' in content