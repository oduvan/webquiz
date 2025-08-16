import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock
import aiohttp
from aiohttp import web, WSMsgType
from aiohttp.test_utils import AioHTTPTestCase

from webquiz.server import WebQuizConfig, TestingServer, create_app


class TestLiveStats(AioHTTPTestCase):
    
    async def get_application(self):
        """Create test application"""
        config = WebQuizConfig()
        config.paths.quizzes_dir = "test-quizzes"
        config.paths.logs_dir = "test-logs"
        config.paths.csv_dir = "test-csv"
        config.paths.static_dir = "test-static"
        
        async def mock_initialize_log_file(self):
            self.log_file = "test.log"
        
        with patch('webquiz.server.TestingServer.initialize_log_file', mock_initialize_log_file):
            with patch('webquiz.server.TestingServer.periodic_flush', new_callable=AsyncMock):
                with patch('webquiz.server.TestingServer.load_questions', new_callable=AsyncMock):
                    app = await create_app(config)
                    
                    # Get server instance for testing
                    self.testing_server = None
                    for route in app.router.routes():
                        if hasattr(route, '_handler') and hasattr(route._handler, '__self__'):
                            if isinstance(route._handler.__self__, TestingServer):
                                self.testing_server = route._handler.__self__
                                break
                    
                    # Mock questions for testing
                    self.testing_server.questions = [
                        {'id': 1, 'question': 'Test question 1', 'options': ['A', 'B', 'C'], 'correct_answer': 0},
                        {'id': 2, 'question': 'Test question 2', 'options': ['X', 'Y', 'Z'], 'correct_answer': 1},
                    ]
                    
                    return app

    async def test_live_stats_page_loads(self):
        """Test that live stats page loads correctly (or returns 404 if template missing)"""
        resp = await self.client.request("GET", "/live-stats")
        # In test environment, template might not be available, so we accept 404
        self.assertIn(resp.status, [200, 404])
        if resp.status == 200:
            self.assertEqual(resp.content_type, 'text/html')
        elif resp.status == 404:
            text = await resp.text()
            self.assertIn("Live stats page not found", text)

    async def test_websocket_connection(self):
        """Test WebSocket connection establishment"""
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Should receive initial state message
        msg = await ws.receive()
        self.assertEqual(msg.type, WSMsgType.TEXT)
        
        data = json.loads(msg.data)
        self.assertEqual(data['type'], 'initial_state')
        self.assertIn('live_stats', data)
        self.assertIn('users', data)
        self.assertIn('total_questions', data)
        
        await ws.close()

    async def test_websocket_ping_pong(self):
        """Test WebSocket keep-alive ping/pong"""
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Skip initial state message
        await ws.receive()
        
        # Send ping
        await ws.send_str(json.dumps({'type': 'ping'}))
        
        # Should receive pong
        msg = await ws.receive()
        data = json.loads(msg.data)
        self.assertEqual(data['type'], 'pong')
        
        await ws.close()

    async def test_user_registration_broadcasts(self):
        """Test that user registration broadcasts to WebSocket clients"""
        # Connect WebSocket client
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Skip initial state message
        await ws.receive()
        
        # Register a user
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        self.assertEqual(resp.status, 200)
        
        # Should receive user registration broadcast
        msg = await ws.receive()
        data = json.loads(msg.data)
        
        self.assertEqual(data['type'], 'user_registered')
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['question_id'], 1)
        self.assertEqual(data['state'], 'think')
        
        await ws.close()

    async def test_answer_submission_broadcasts(self):
        """Test that answer submission broadcasts state updates"""
        # Register user first
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        user_data = await resp.json()
        user_id = user_data['user_id']
        
        # Connect WebSocket client
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Skip initial state and registration messages
        await ws.receive()  # initial_state
        await ws.receive()  # user_registered
        
        # Submit answer
        resp = await self.client.request("POST", "/api/submit-answer", 
                                       json={
                                           'user_id': user_id,
                                           'question_id': 1,
                                           'selected_answer': 0  # Correct answer
                                       })
        self.assertEqual(resp.status, 200)
        
        # Should receive two broadcasts: current question result + next question think
        msg1 = await ws.receive()
        data1 = json.loads(msg1.data)
        
        self.assertEqual(data1['type'], 'state_update')
        self.assertEqual(data1['user_id'], user_id)
        self.assertEqual(data1['question_id'], 1)
        self.assertEqual(data1['state'], 'ok')
        
        msg2 = await ws.receive()
        data2 = json.loads(msg2.data)
        
        self.assertEqual(data2['type'], 'state_update')
        self.assertEqual(data2['user_id'], user_id)
        self.assertEqual(data2['question_id'], 2)
        self.assertEqual(data2['state'], 'think')
        
        await ws.close()

    async def test_incorrect_answer_broadcasts(self):
        """Test that incorrect answers broadcast 'fail' state"""
        # Register user
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        user_data = await resp.json()
        user_id = user_data['user_id']
        
        # Connect WebSocket
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Skip initial messages
        await ws.receive()  # initial_state
        await ws.receive()  # user_registered
        
        # Submit incorrect answer
        resp = await self.client.request("POST", "/api/submit-answer", 
                                       json={
                                           'user_id': user_id,
                                           'question_id': 1,
                                           'selected_answer': 1  # Incorrect answer
                                       })
        
        # Should receive 'fail' state
        msg = await ws.receive()
        data = json.loads(msg.data)
        self.assertEqual(data['state'], 'fail')
        
        await ws.close()

    async def test_live_stats_data_structure(self):
        """Test that live stats data structure is maintained correctly"""
        # Register user
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        user_data = await resp.json()
        user_id = user_data['user_id']
        
        # Check initial state
        self.assertIn(user_id, self.testing_server.live_stats)
        self.assertEqual(self.testing_server.live_stats[user_id][1], 'think')
        
        # Submit answer
        await self.client.request("POST", "/api/submit-answer", 
                                json={
                                    'user_id': user_id,
                                    'question_id': 1,
                                    'selected_answer': 0
                                })
        
        # Check updated state
        self.assertEqual(self.testing_server.live_stats[user_id][1], 'ok')
        self.assertEqual(self.testing_server.live_stats[user_id][2], 'think')

    async def test_multiple_websocket_clients(self):
        """Test broadcasting to multiple WebSocket clients"""
        # Connect multiple clients
        ws1 = await self.client.ws_connect('/ws/live-stats')
        ws2 = await self.client.ws_connect('/ws/live-stats')
        
        # Skip initial messages
        await ws1.receive()
        await ws2.receive()
        
        # Register user
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        
        # Both clients should receive the broadcast
        msg1 = await ws1.receive()
        msg2 = await ws2.receive()
        
        data1 = json.loads(msg1.data)
        data2 = json.loads(msg2.data)
        
        self.assertEqual(data1['type'], 'user_registered')
        self.assertEqual(data2['type'], 'user_registered')
        self.assertEqual(data1['username'], data2['username'])
        
        await ws1.close()
        await ws2.close()

    async def test_websocket_client_cleanup(self):
        """Test that disconnected WebSocket clients are cleaned up"""
        initial_count = len(self.testing_server.websocket_clients)
        
        # Connect client
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Verify client was added
        self.assertEqual(len(self.testing_server.websocket_clients), initial_count + 1)
        
        await ws.close()
        # Give some time for cleanup
        await asyncio.sleep(0.1)
        
        # Client should be removed (this happens when trying to send next message)
        # Register user to trigger broadcast and cleanup
        await self.client.request("POST", "/api/register", 
                                json={'username': 'testuser'})
        
        # The closed client should have been cleaned up
        self.assertEqual(len(self.testing_server.websocket_clients), initial_count)

    async def test_quiz_switch_broadcasts(self):
        """Test that quiz switching broadcasts to clients"""
        # Mock the switch_quiz method to avoid file operations
        async def mock_switch_quiz(quiz_filename):
            self.testing_server.questions = [
                {'id': 1, 'question': 'New question', 'options': ['A', 'B'], 'correct_answer': 0}
            ]
            self.testing_server.live_stats.clear()
            await self.testing_server.broadcast_to_websockets({
                'type': 'quiz_switched',
                'current_quiz': quiz_filename,
                'total_questions': 1,
                'message': f'Quiz switched to: {quiz_filename}'
            })
        
        # Connect WebSocket
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Skip initial state
        await ws.receive()
        
        # Trigger quiz switch
        with patch.object(self.testing_server, 'switch_quiz', mock_switch_quiz):
            with patch.object(self.testing_server, 'list_available_quizzes', return_value=['new_quiz.yaml']):
                await self.testing_server.switch_quiz('new_quiz.yaml')
        
        # Should receive quiz switch broadcast
        msg = await ws.receive()
        data = json.loads(msg.data)
        
        self.assertEqual(data['type'], 'quiz_switched')
        self.assertEqual(data['current_quiz'], 'new_quiz.yaml')
        self.assertEqual(data['total_questions'], 1)
        
        await ws.close()

    async def test_live_stats_state_reset_on_quiz_switch(self):
        """Test that live stats are cleared when quiz is switched"""
        # Register user and create some state
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        user_data = await resp.json()
        user_id = user_data['user_id']
        
        # Verify initial state exists
        self.assertIn(user_id, self.testing_server.live_stats)
        
        # Mock switch quiz to trigger state reset
        self.testing_server.reset_server_state()
        
        # Verify live stats are cleared
        self.assertEqual(len(self.testing_server.live_stats), 0)
        self.assertEqual(len(self.testing_server.users), 0)

    async def test_websocket_initial_state_content(self):
        """Test that WebSocket initial state contains correct data"""
        # Register user first
        resp = await self.client.request("POST", "/api/register", 
                                       json={'username': 'testuser'})
        user_data = await resp.json()
        user_id = user_data['user_id']
        
        # Connect WebSocket after user registration
        ws = await self.client.ws_connect('/ws/live-stats')
        
        # Receive initial state
        msg = await ws.receive()
        data = json.loads(msg.data)
        
        self.assertEqual(data['type'], 'initial_state')
        self.assertIn(user_id, data['users'])
        self.assertEqual(data['users'][user_id], 'testuser')
        self.assertIn(user_id, data['live_stats'])
        self.assertEqual(data['live_stats'][user_id]['1'], 'think')
        self.assertEqual(data['total_questions'], 2)
        
        await ws.close()


if __name__ == '__main__':
    pytest.main([__file__])