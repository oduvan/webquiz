import os
import json
import requests
import yaml
from conftest import custom_webquiz_server


def test_admin_create_quiz_wizard_mode(temp_dir):
    """Test creating a quiz using wizard mode with structured data."""
    with custom_webquiz_server() as (proc, port):
        quiz_data = {
            'title': 'Math Basics',
            'description': 'Basic mathematics quiz',
            'questions': [
                {
                    'question': 'What is 5 + 3?',
                    'options': ['6', '7', '8', '9'],
                    'correct_answer': 2
                },
                {
                    'question': 'What is 10 - 4?',
                    'options': ['5', '6', '7', '8'],
                    'correct_answer': 1
                }
            ]
        }

        create_data = {
            'filename': 'math_basics',
            'mode': 'wizard',
            'quiz_data': quiz_data
        }

        headers = {'X-Master-Key': 'test123'}
        response = requests.post(
            f'http://localhost:{port}/api/admin/create-quiz',
            headers=headers,
            json=create_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'math_basics.yaml' in data['message']
        assert data['filename'] == 'math_basics.yaml'


def test_admin_create_quiz_text_mode(temp_dir):
    """Test creating a quiz using raw YAML text mode."""
    quiz_yaml = '''title: Science Quiz
description: Basic science questions
questions:
  - question: What is H2O?
    options:
      - Oxygen
      - Water
      - Hydrogen
      - Salt
    correct_answer: 1
  - question: How many planets in our solar system?
    options:
      - "7"
      - "8"
      - "9"
      - "10"
    correct_answer: 1
'''

    with custom_webquiz_server() as (proc, port):
        create_data = {
            'filename': 'science_quiz',
            'mode': 'text',
            'content': quiz_yaml
        }

        headers = {'X-Master-Key': 'test123'}
        response = requests.post(
            f'http://localhost:{port}/api/admin/create-quiz',
            headers=headers,
            json=create_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'science_quiz.yaml' in data['message']


def test_admin_create_quiz_already_exists(temp_dir):
    """Test error when trying to create a quiz that already exists."""
    existing_quiz = {
        'existing_quiz.yaml': {
            'title': 'Existing Quiz',
            'questions': [
                {
                    'question': 'Test question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=existing_quiz) as (proc, port):
        create_data = {
            'filename': 'existing_quiz',
            'mode': 'wizard',
            'quiz_data': {
                'title': 'Duplicate Quiz',
                'questions': [{'question': 'New?', 'options': ['Yes', 'No'], 'correct_answer': 0}]
            }
        }

        headers = {'X-Master-Key': 'test123'}
        response = requests.post(
            f'http://localhost:{port}/api/admin/create-quiz',
            headers=headers,
            json=create_data
        )

        assert response.status_code == 409
        data = response.json()
        assert 'already exists' in data['error']


def test_admin_get_quiz_content(temp_dir):
    """Test retrieving existing quiz content for editing."""
    quiz_data = {
        'title': 'Geography Quiz',
        'questions': [
            {
                'question': 'Capital of France?',
                'options': ['London', 'Paris', 'Berlin', 'Madrid'],
                'correct_answer': 1
            }
        ]
    }

    quizzes = {'geography.yaml': quiz_data}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.get(
            f'http://localhost:{port}/api/admin/quiz/geography.yaml',
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['filename'] == 'geography.yaml'
        assert 'content' in data
        assert 'parsed' in data

        # Verify content is valid YAML
        parsed_quiz = yaml.safe_load(data['content'])
        assert parsed_quiz['title'] == 'Geography Quiz'
        assert len(parsed_quiz['questions']) == 1


def test_admin_get_nonexistent_quiz(temp_dir):
    """Test 404 when retrieving non-existent quiz."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.get(
            f'http://localhost:{port}/api/admin/quiz/nonexistent.yaml',
            headers=headers
        )

        assert response.status_code == 404
        data = response.json()
        assert 'not found' in data['error']


def test_admin_update_quiz_wizard_mode(temp_dir):
    """Test updating a quiz using wizard mode."""
    original_quiz = {
        'title': 'Original Quiz',
        'questions': [
            {
                'question': 'Original question?',
                'options': ['A', 'B'],
                'correct_answer': 0
            }
        ]
    }

    quizzes = {'update_test.yaml': original_quiz}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        updated_quiz_data = {
            'title': 'Updated Quiz',
            'questions': [
                {
                    'question': 'Updated question?',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': 1
                }
            ]
        }

        update_data = {
            'mode': 'wizard',
            'quiz_data': updated_quiz_data
        }

        headers = {'X-Master-Key': 'test123'}
        response = requests.put(
            f'http://localhost:{port}/api/admin/quiz/update_test.yaml',
            headers=headers,
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'updated successfully' in data['message']
        assert 'backup_created' in data

        # Verify the file was actually updated by retrieving it
        get_response = requests.get(
            f'http://localhost:{port}/api/admin/quiz/update_test.yaml',
            headers=headers
        )
        assert get_response.status_code == 200

        updated_content = get_response.json()
        updated_quiz = yaml.safe_load(updated_content['content'])

        # Verify the content was actually changed
        assert updated_quiz['title'] == 'Updated Quiz'
        assert updated_quiz['questions'][0]['question'] == 'Updated question?'
        assert updated_quiz['questions'][0]['options'] == ['X', 'Y', 'Z']
        assert updated_quiz['questions'][0]['correct_answer'] == 1

        # Verify it's different from original
        assert updated_quiz['title'] != original_quiz['title']
        assert len(updated_quiz['questions'][0]['options']) == 3  # vs original 2


def test_admin_update_quiz_text_mode(temp_dir):
    """Test updating a quiz using raw YAML text."""
    original_quiz = {
        'title': 'Text Update Test',
        'questions': [
            {
                'question': 'Before update?',
                'options': ['A', 'B'],
                'correct_answer': 0
            }
        ]
    }

    quizzes = {'text_update.yaml': original_quiz}

    updated_yaml = '''title: Updated via Text
questions:
  - question: After update?
    options: ['X', 'Y', 'Z']
    correct_answer: 2
'''

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        update_data = {
            'mode': 'text',
            'content': updated_yaml
        }

        headers = {'X-Master-Key': 'test123'}
        response = requests.put(
            f'http://localhost:{port}/api/admin/quiz/text_update.yaml',
            headers=headers,
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'backup_created' in data

        # Verify the file was actually updated by retrieving it
        get_response = requests.get(
            f'http://localhost:{port}/api/admin/quiz/text_update.yaml',
            headers=headers
        )
        assert get_response.status_code == 200

        updated_content = get_response.json()
        updated_quiz = yaml.safe_load(updated_content['content'])

        # Verify the content was actually changed
        assert updated_quiz['title'] == 'Updated via Text'
        assert updated_quiz['questions'][0]['question'] == 'After update?'
        assert updated_quiz['questions'][0]['options'] == ['X', 'Y', 'Z']
        assert updated_quiz['questions'][0]['correct_answer'] == 2

        # Verify it's different from original
        assert updated_quiz['title'] != original_quiz['title']
        assert updated_quiz['questions'][0]['question'] != original_quiz['questions'][0]['question']


def test_admin_delete_quiz(temp_dir):
    """Test deleting a quiz file (should create backup)."""
    quiz_to_delete = {
        'delete_me.yaml': {
            'title': 'Quiz to Delete',
            'questions': [
                {
                    'question': 'Will be deleted?',
                    'options': ['Yes', 'No'],
                    'correct_answer': 0
                }
            ]
        },
        'keep_me.yaml': {
            'title': 'Quiz to Keep',
            'questions': [
                {
                    'question': 'Will stay?',
                    'options': ['Yes', 'No'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_to_delete) as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.delete(
            f'http://localhost:{port}/api/admin/quiz/delete_me.yaml',
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'deleted successfully' in data['message']
        assert 'backup_created' in data


def test_admin_delete_active_quiz(temp_dir):
    """Test preventing deletion of currently active quiz."""
    # Start server with a single quiz (which becomes active)
    active_quiz = {
        'active_quiz.yaml': {
            'title': 'Active Quiz',
            'questions': [
                {
                    'question': 'Am I active?',
                    'options': ['Yes', 'No'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=active_quiz) as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.delete(
            f'http://localhost:{port}/api/admin/quiz/active_quiz.yaml',
            headers=headers
        )

        assert response.status_code == 400
        data = response.json()
        assert 'currently active' in data['error']


def test_admin_delete_nonexistent_quiz(temp_dir):
    """Test 404 when deleting non-existent quiz."""
    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.delete(
            f'http://localhost:{port}/api/admin/quiz/nonexistent.yaml',
            headers=headers
        )

        assert response.status_code == 404
        data = response.json()
        assert 'not found' in data['error']


def test_validate_quiz_valid_structure(temp_dir):
    """Test validation of valid quiz YAML structure."""
    valid_quiz_yaml = '''title: Valid Quiz
questions:
  - question: Is this valid?
    options: ['Yes', 'No', 'Maybe']
    correct_answer: 0
  - question: Another question?
    options: ['A', 'B']
    correct_answer: 1
'''

    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': valid_quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True
        assert data['question_count'] == 2
        assert 'parsed' in data


def test_validate_quiz_missing_or_empty_questions(temp_dir):
    """Test validation of quiz without questions array or empty questions array."""
    # Test 1: Quiz without questions array
    missing_questions_yaml = '''title: Invalid Quiz
description: This quiz has no questions
'''

    # Test 2: Quiz with empty questions array
    empty_questions_yaml = '''title: Empty Quiz
questions: []
'''

    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Test missing questions array
        response1 = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': missing_questions_yaml}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1['valid'] is False
        assert len(data1['errors']) > 0
        assert any('questions' in error for error in data1['errors'])

        # Test empty questions array
        response2 = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': empty_questions_yaml}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2['valid'] is False
        assert any('принаймні одне питання' in error for error in data2['errors'])


def test_validate_quiz_invalid_yaml(temp_dir):
    """Test validation of malformed YAML syntax."""
    invalid_yaml = '''title: Invalid YAML
questions:
  - question: What's wrong here?
    options: ['A', 'B'
    correct_answer: 0  # Missing closing bracket above
'''

    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': invalid_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is False
        assert len(data['errors']) > 0
        assert any('YAML syntax error' in error for error in data['errors'])


def test_validate_quiz_invalid_question_structure(temp_dir):
    """Test validation of questions with missing required fields or invalid answer indices."""
    # Test 1: Missing required fields
    incomplete_quiz_yaml = '''title: Incomplete Quiz
questions:
  - question: Where are my options?
    correct_answer: 0
  - options: ['A', 'B', 'C']
    # Missing question and correct_answer
'''

    # Test 2: Invalid correct answer index
    invalid_index_yaml = '''title: Invalid Index Quiz
questions:
  - question: What's the answer?
    options: ['A', 'B']
    correct_answer: 5  # Out of range!
'''

    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Test missing required fields
        response1 = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': incomplete_quiz_yaml}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1['valid'] is False
        assert len(data1['errors']) > 0

        # Test invalid correct answer index
        response2 = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': invalid_index_yaml}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2['valid'] is False
        assert any('out of range' in error for error in data2['errors'])




def test_validate_quiz_image_only_questions(temp_dir):
    """Test validation of questions with only images (no text)."""
    image_quiz_yaml = '''title: Image Quiz
questions:
  - image: /imgs/question1.png
    options: ['A', 'B', 'C']
    correct_answer: 1
  - question: Text question too
    options: ['X', 'Y']
    correct_answer: 0
'''

    with custom_webquiz_server() as (proc, port):
        headers = {'X-Master-Key': 'test123'}
        response = requests.post(
            f'http://localhost:{port}/api/admin/validate-quiz',
            headers=headers,
            json={'content': image_quiz_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True  # Image-only questions should be valid
        assert data['question_count'] == 2



def test_update_active_quiz_affects_server_state(temp_dir):
    """Test that updating the currently active quiz reloads it on the server."""
    original_quiz = {
        'title': 'Active Quiz Original',
        'questions': [
            {
                'question': 'Original active question?',
                'options': ['A', 'B'],
                'correct_answer': 0
            }
        ]
    }

    # Start with single quiz (becomes active)
    quizzes = {'active_quiz.yaml': original_quiz}

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        headers = {'X-Master-Key': 'test123'}

        # Verify the current quiz is active
        list_response = requests.get(
            f'http://localhost:{port}/api/admin/list-quizzes',
            headers=headers
        )
        assert list_response.status_code == 200
        assert list_response.json()['current_quiz'] == 'active_quiz.yaml'

        # Update the active quiz
        updated_quiz_data = {
            'title': 'Active Quiz Updated',
            'questions': [
                {
                    'question': 'Updated active question?',
                    'options': ['X', 'Y', 'Z', 'W'],
                    'correct_answer': 2
                }
            ]
        }

        update_data = {
            'mode': 'wizard',
            'quiz_data': updated_quiz_data
        }

        update_response = requests.put(
            f'http://localhost:{port}/api/admin/quiz/active_quiz.yaml',
            headers=headers,
            json=update_data
        )

        assert update_response.status_code == 200
        assert update_response.json()['success'] is True

        # Verify the quiz was actually updated on the server by retrieving it
        get_response = requests.get(
            f'http://localhost:{port}/api/admin/quiz/active_quiz.yaml',
            headers=headers
        )
        assert get_response.status_code == 200

        updated_content = get_response.json()
        updated_quiz = yaml.safe_load(updated_content['content'])

        # Verify the active quiz content changed
        assert updated_quiz['title'] == 'Active Quiz Updated'
        assert updated_quiz['questions'][0]['question'] == 'Updated active question?'
        assert len(updated_quiz['questions'][0]['options']) == 4


def test_create_then_switch_to_new_quiz(temp_dir):
    """Test creating a quiz and immediately switching to it."""
    with custom_webquiz_server() as (proc, port):
        # Create a new quiz
        quiz_data = {
            'title': 'New Quiz for Switch',
            'questions': [
                {
                    'question': 'Switch to me?',
                    'options': ['Yes', 'No'],
                    'correct_answer': 0
                }
            ]
        }

        create_data = {
            'filename': 'switch_target',
            'mode': 'wizard',
            'quiz_data': quiz_data
        }

        headers = {'X-Master-Key': 'test123'}

        # Create the quiz
        create_response = requests.post(
            f'http://localhost:{port}/api/admin/create-quiz',
            headers=headers,
            json=create_data
        )
        assert create_response.status_code == 200

        # Switch to the new quiz
        switch_data = {'quiz_filename': 'switch_target.yaml'}
        switch_response = requests.post(
            f'http://localhost:{port}/api/admin/switch-quiz',
            headers=headers,
            json=switch_data
        )

        assert switch_response.status_code == 200
        switch_result = switch_response.json()
        assert switch_result['success'] is True
        assert 'switch_target.yaml' in switch_result['message']


def test_quiz_operations_without_auth(temp_dir):
    """Test that all quiz management operations require authentication."""
    with custom_webquiz_server() as (proc, port):
        base_url = f'http://localhost:{port}/api/admin'

        # Test operations without auth headers
        operations = [
            ('GET', f'{base_url}/quiz/test.yaml'),
            ('POST', f'{base_url}/create-quiz', {'filename': 'test', 'mode': 'wizard', 'quiz_data': {}}),
            ('PUT', f'{base_url}/quiz/test.yaml', {'mode': 'text', 'content': 'test'}),
            ('DELETE', f'{base_url}/quiz/test.yaml'),
            ('POST', f'{base_url}/validate-quiz', {'content': 'test: content'})
        ]

        for method, url, *data in operations:
            json_data = data[0] if data else None
            if method == 'GET':
                response = requests.get(url)
            elif method == 'POST':
                response = requests.post(url, json=json_data)
            elif method == 'PUT':
                response = requests.put(url, json=json_data)
            elif method == 'DELETE':
                response = requests.delete(url)

            assert response.status_code == 401, f"Operation {method} {url} should require auth"