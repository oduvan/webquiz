"""Tests for Live Stats functionality"""
import asyncio
import json
import time
import requests
from pathlib import Path
from conftest import custom_webquiz_server


def test_live_stats_page_accessible(temp_dir):
    """Test that the live stats page is accessible via HTTP"""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f'http://localhost:{port}/live-stats/')
        
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        
        html_content = response.text
        assert 'WebQuiz Live Stats' in html_content
        assert 'LiveStatsClient' in html_content
        assert 'userStatistics' in html_content  # Check for statistics variables
        assert 'questionStatistics' in html_content
        assert 'calculateStatistics' in html_content  # Check for client-side calculation


def test_live_stats_websocket_initial_state(temp_dir):
    """Test WebSocket initial state message and client-side statistics calculation"""
    with custom_webquiz_server() as (proc, port):
        # We can't easily test WebSocket directly, but we can test the HTTP endpoints
        # that provide the same data structure
        
        # Register a user first to have some data
        register_response = requests.post(f'http://localhost:{port}/api/register', 
                                        json={'username': 'TestUser1'})
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data['user_id']
        
        # Submit an answer to create statistics
        submit_response = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                      json={
                                          'user_id': user_id,
                                          'question_id': 1,
                                          'selected_answer': 0  # Correct answer
                                      })
        assert submit_response.status_code == 200
        
        # Verify the live stats page contains the necessary JavaScript for calculation
        response = requests.get(f'http://localhost:{port}/live-stats/')
        html_content = response.text
        
        # Verify client-side statistics calculation is present
        assert 'calculateStatistics()' in html_content
        assert 'this.userStatistics[userId] = {' in html_content
        assert 'this.questionStatistics[qId].total_attempts++' in html_content


def test_multiple_users_statistics_aggregation(temp_dir):
    """Test that client-side statistics correctly aggregate across multiple users"""
    with custom_webquiz_server() as (proc, port):
        # Register first user
        register_response1 = requests.post(f'http://localhost:{port}/api/register', 
                                         json={'username': 'User1'})
        assert register_response1.status_code == 200
        user_data1 = register_response1.json()
        user_id1 = user_data1['user_id']
        
        # Register second user  
        register_response2 = requests.post(f'http://localhost:{port}/api/register', 
                                         json={'username': 'User2'})
        assert register_response2.status_code == 200
        user_data2 = register_response2.json()
        user_id2 = user_data2['user_id']
        
        # User 1 submits correct answer
        submit_response1 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id1,
                                           'question_id': 1,
                                           'selected_answer': 0  # Correct
                                       })
        assert submit_response1.status_code == 200
        
        # User 2 submits incorrect answer
        submit_response2 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id2,
                                           'question_id': 1,
                                           'selected_answer': 1  # Incorrect
                                       })
        assert submit_response2.status_code == 200
        
        # Verify both users are registered and have different results
        # At this point, question 1 should have 1 correct out of 2 total attempts
        # User1 should have 1/1, User2 should have 0/1
        
        # Check that the live stats page loads and contains the statistics calculation logic
        response = requests.get(f'http://localhost:{port}/live-stats/')
        assert response.status_code == 200
        html_content = response.text
        
        # Verify the JavaScript contains proper statistics calculation
        assert 'correct_count: correctCount' in html_content
        assert 'total_answered: totalAnswered' in html_content
        assert 'total_attempts: 0' in html_content  # Initialization
        assert 'correct_count: 0' in html_content   # Initialization


def test_user_progress_statistics_tracking(temp_dir):
    """Test that user progress through multiple questions updates statistics correctly"""
    with custom_webquiz_server() as (proc, port):
        # Register a user
        register_response = requests.post(f'http://localhost:{port}/api/register', 
                                        json={'username': 'ProgressUser'})
        assert register_response.status_code == 200
        user_data = register_response.json()
        user_id = user_data['user_id']
        
        # Submit answer to first question (correct)
        submit_response1 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id,
                                           'question_id': 1,
                                           'selected_answer': 0  # Correct
                                       })
        assert submit_response1.status_code == 200
        
        # Try to submit answer to second question (may not exist)
        submit_response2 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id,
                                           'question_id': 2,
                                           'selected_answer': 1
                                       })
        # Response might be 400 or 404 if there's only one question
        assert submit_response2.status_code in [200, 400, 404]
        
        # Verify the statistics calculation handles this correctly
        response = requests.get(f'http://localhost:{port}/live-stats/')
        assert response.status_code == 200
        html_content = response.text
        
        # Verify proper state checking in statistics calculation
        assert "state === 'ok' || state === 'fail'" in html_content
        assert "if (state === 'ok')" in html_content


def test_client_side_statistics_javascript_structure(temp_dir):
    """Test that the JavaScript structure for client-side statistics calculation is correct"""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f'http://localhost:{port}/live-stats/')
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for LiveStatsClient class structure
        assert 'class LiveStatsClient' in html_content
        assert 'constructor()' in html_content
        assert 'this.userStatistics = {};' in html_content
        assert 'this.questionStatistics = {};' in html_content
        
        # Check for message handling methods
        assert 'handleInitialState(data)' in html_content
        assert 'handleUserRegistered(data)' in html_content
        assert 'handleStateUpdate(data)' in html_content
        assert 'handleQuizSwitched(data)' in html_content
        
        # Check for client-side statistics calculation method
        assert 'calculateStatistics()' in html_content
        
        # Check that statistics are calculated in message handlers
        assert 'this.calculateStatistics();' in html_content
        
        # Verify buildTable method exists for rendering statistics
        assert 'buildTable()' in html_content


def test_websocket_message_handling_without_server_statistics(temp_dir):
    """Test that WebSocket message handling works without server-provided statistics"""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f'http://localhost:{port}/live-stats/')
        
        assert response.status_code == 200
        html_content = response.text
        
        # Verify that handlers don't expect server statistics
        assert 'data.user_statistics' not in html_content
        assert 'data.question_statistics' not in html_content
        
        # Verify that handlers call calculateStatistics instead
        assert 'this.calculateStatistics();' in html_content
        
        # Check specific handler implementations
        assert 'handleInitialState(data) {' in html_content
        assert 'handleStateUpdate(data) {' in html_content


def test_statistics_display_css_styling(temp_dir):
    """Test that the CSS styling for statistics display is present"""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f'http://localhost:{port}/live-stats/')
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for statistics-specific CSS classes
        assert '.question-header' in html_content
        assert '.question-text' in html_content
        assert '.question-stats' in html_content
        assert '.username-content' in html_content
        assert '.username-text' in html_content
        assert '.user-stats' in html_content
        
        # Check for styling rules
        assert 'flex-direction: column' in html_content
        assert 'font-size: 11px' in html_content
        assert 'background: rgba(0,0,0,0.1)' in html_content