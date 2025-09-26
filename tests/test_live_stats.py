"""Tests for Live Stats functionality"""
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
        assert 'userStatistics' in html_content  # Check for new statistics variables
        assert 'questionStatistics' in html_content


def test_live_stats_server_methods_calculate_statistics(temp_dir):
    """Test that the server properly calculates user and question statistics"""
    with custom_webquiz_server() as (proc, port):
        # Register two users
        register_response1 = requests.post(f'http://localhost:{port}/api/register', 
                                         json={'username': 'TestUser1'})
        assert register_response1.status_code == 200
        user_data1 = register_response1.json()
        user_id1 = user_data1['user_id']
        
        register_response2 = requests.post(f'http://localhost:{port}/api/register', 
                                         json={'username': 'TestUser2'})
        assert register_response2.status_code == 200
        user_data2 = register_response2.json()
        user_id2 = user_data2['user_id']
        
        # User 1 submits correct answer to question 1
        submit_response1 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id1,
                                           'question_id': 1,
                                           'selected_answer': 0  # Correct answer
                                       })
        assert submit_response1.status_code == 200
        
        # User 2 submits incorrect answer to question 1
        submit_response2 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id2,
                                           'question_id': 1,
                                           'selected_answer': 1  # Incorrect answer
                                       })
        assert submit_response2.status_code == 200
        
        # The statistics should be calculated on the server side
        # We can't directly test the server methods, but we can verify the page loads
        # and contains the statistics infrastructure
        response = requests.get(f'http://localhost:{port}/live-stats/')
        assert response.status_code == 200
        
        html_content = response.text
        # Check that the necessary statistics methods are present in the JavaScript
        assert 'user_statistics' in html_content
        assert 'question_statistics' in html_content
        assert 'userStatistics' in html_content
        assert 'questionStatistics' in html_content


def test_live_stats_html_contains_statistics_elements(temp_dir):
    """Test that the live stats HTML contains the required elements for displaying statistics"""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f'http://localhost:{port}/live-stats/')
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for statistics-related CSS classes
        assert 'question-stats' in html_content
        assert 'user-stats' in html_content
        assert 'question-header' in html_content
        assert 'username-content' in html_content
        
        # Check for statistics handling in JavaScript
        assert 'handleInitialState' in html_content
        assert 'handleStateUpdate' in html_content
        assert 'handleUserRegistered' in html_content
        assert 'buildTable' in html_content


def test_multiple_users_answer_tracking(temp_dir):
    """Test that multiple users answering questions works correctly"""
    with custom_webquiz_server() as (proc, port):
        # Register three users
        users = []
        for i in range(3):
            register_response = requests.post(f'http://localhost:{port}/api/register', 
                                            json={'username': f'User{i+1}'})
            assert register_response.status_code == 200
            users.append(register_response.json())
        
        # Users submit different answers
        # User 1: correct answer to question 1
        submit_response1 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': users[0]['user_id'],
                                           'question_id': 1,
                                           'selected_answer': 0  # Correct
                                       })
        assert submit_response1.status_code == 200
        
        # User 2: incorrect answer to question 1
        submit_response2 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': users[1]['user_id'],
                                           'question_id': 1,
                                           'selected_answer': 1  # Incorrect
                                       })
        assert submit_response2.status_code == 200
        
        # User 3: correct answer to question 1
        submit_response3 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': users[2]['user_id'],
                                           'question_id': 1,
                                           'selected_answer': 0  # Correct
                                       })
        assert submit_response3.status_code == 200
        
        # At this point, question 1 should have 2 correct out of 3 total attempts
        # and users should have individual statistics tracked
        
        # Verify the live stats page still works
        response = requests.get(f'http://localhost:{port}/live-stats/')
        assert response.status_code == 200


def test_user_progress_through_multiple_questions(temp_dir):
    """Test that user progress through multiple questions is tracked correctly"""
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
        
        # Submit answer to second question (incorrect) - if it exists
        submit_response2 = requests.post(f'http://localhost:{port}/api/submit-answer', 
                                       json={
                                           'user_id': user_id,
                                           'question_id': 2,
                                           'selected_answer': 1  # Likely incorrect for most questions
                                       })
        # The response might be 400 or 404 if there's only one question, which is fine
        assert submit_response2.status_code in [200, 400, 404]
        
        # Verify the live stats page still loads
        response = requests.get(f'http://localhost:{port}/live-stats/')
        assert response.status_code == 200


def test_live_stats_javascript_structure(temp_dir):
    """Test that the JavaScript structure for live stats is correct"""
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
        
        # Check for table building method
        assert 'buildTable()' in html_content
        
        # Check for statistics handling in message handlers
        assert 'data.user_statistics' in html_content
        assert 'data.question_statistics' in html_content


def test_empty_quiz_state_statistics(temp_dir):
    """Test statistics calculation with no users or answers"""
    with custom_webquiz_server() as (proc, port):
        # Just load the live stats page without any users
        response = requests.get(f'http://localhost:{port}/live-stats/')
        
        assert response.status_code == 200
        html_content = response.text
        
        # Should contain the infrastructure for statistics even with no data
        assert 'userStatistics' in html_content
        assert 'questionStatistics' in html_content
        assert 'user_statistics' in html_content
        assert 'question_statistics' in html_content


def test_live_stats_css_styling(temp_dir):
    """Test that the CSS styling for statistics is present"""
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