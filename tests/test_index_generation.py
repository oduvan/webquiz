import os
import json
import re
import requests
from pathlib import Path
from conftest import custom_webquiz_server


def test_questions_data_embedded_correctly(temp_dir):
    """Test that questions data is properly embedded in index.html without correct answers."""
    quiz_data = {
        'test_quiz.yaml': {
            'title': 'Data Embedding Test',
            'questions': [
                {
                    'question': 'What is 2 + 2?',
                    'options': ['3', '4', '5', '6'],
                    'correct_answer': 1
                },
                {
                    'question': 'What color is the sky?',
                    'options': ['Red', 'Blue', 'Green'],
                    'correct_answer': 1,
                    'image': '/imgs/sky.png'
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Get the static directory path from server configuration
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        # Verify the file was created
        assert index_path.exists(), "index.html should be created in static directory"

        # Read the generated HTML file
        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Extract embedded questions JSON from JavaScript
        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        assert questions_match, "Questions JSON should be embedded in HTML"

        embedded_questions = json.loads(questions_match.group(1))

        # Verify structure and content
        assert len(embedded_questions) == 2, "Should embed both questions"

        # Check first question
        q1 = embedded_questions[0]
        assert q1['id'] == 1
        assert q1['question'] == 'What is 2 + 2?'
        assert q1['options'] == ['3', '4', '5', '6']
        assert 'correct_answer' not in q1, "Correct answer should NOT be included in client data"
        assert 'image' not in q1, "Image should not be present for this question"

        # Check second question (with image)
        q2 = embedded_questions[1]
        assert q2['id'] == 2
        assert q2['question'] == 'What color is the sky?'
        assert q2['options'] == ['Red', 'Blue', 'Green']
        assert q2['image'] == '/imgs/sky.png', "Image should be included when present"
        assert 'correct_answer' not in q2, "Correct answer should NOT be included in client data"


def test_quiz_title_embedded(temp_dir):
    """Test that quiz title is properly embedded in HTML."""
    quiz_data = {
        'title_test.yaml': {
            'title': 'Amazing Quiz Title!',
            'questions': [
                {
                    'question': 'Test question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check title in <title> tag
        assert '<title>Amazing Quiz Title!</title>' in html_content

        # Check title in <h1> tag
        assert '<h1>Amazing Quiz Title!</h1>' in html_content


def test_webquiz_version_embedded(temp_dir):
    """Test that WebQuiz version is embedded in HTML."""
    with custom_webquiz_server() as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Look for version in footer
        version_pattern = r'WebQuiz v[\d\w\.\-]+'
        assert re.search(version_pattern, html_content), "WebQuiz version should be embedded in footer"


def test_correct_answers_excluded_from_client_data(temp_dir):
    """Security test: ensure correct answers are never leaked to client."""
    quiz_data = {
        'security_test.yaml': {
            'title': 'Security Test Quiz',
            'questions': [
                {
                    'question': 'Secret answer test?',
                    'options': ['Wrong', 'Correct!', 'Also wrong'],
                    'correct_answer': 1  # This should never appear in HTML
                },
                {
                    'question': 'Another secret?',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_answer': 3
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Extract questions JSON
        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))

        # Verify no correct_answer fields exist
        for question in embedded_questions:
            assert 'correct_answer' not in question, f"Question {question['id']} should not contain correct_answer"

            # Also check the raw HTML doesn't contain the literal values
            assert '"correct_answer":' not in html_content, "correct_answer field should not appear anywhere in HTML"

        # Double-check by searching for the specific correct answer indices
        assert '"correct_answer": 1' not in html_content
        assert '"correct_answer": 3' not in html_content
        assert 'correct_answer: 1' not in html_content
        assert 'correct_answer: 3' not in html_content


def test_optional_fields_included(temp_dir):
    """Test that optional fields like images are properly included when present."""
    quiz_data = {
        'optional_fields.yaml': {
            'title': 'Optional Fields Test',
            'questions': [
                {
                    'question': 'Text only question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                },
                {
                    'question': 'Question with image?',
                    'options': ['Yes', 'No'],
                    'correct_answer': 0,
                    'image': '/imgs/test.jpg'
                },
                {
                    # Image-only question (no text)
                    'options': ['Option 1', 'Option 2'],
                    'correct_answer': 1,
                    'image': '/imgs/image_only.png'
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))

        assert len(embedded_questions) == 3

        # Question 1: text only, no image
        q1 = embedded_questions[0]
        assert 'question' in q1
        assert q1['question'] == 'Text only question?'
        assert 'image' not in q1

        # Question 2: text and image
        q2 = embedded_questions[1]
        assert 'question' in q2
        assert q2['question'] == 'Question with image?'
        assert 'image' in q2
        assert q2['image'] == '/imgs/test.jpg'

        # Question 3: image only, no text
        q3 = embedded_questions[2]
        assert 'question' not in q3, "Question without text should not have question field"
        assert 'image' in q3
        assert q3['image'] == '/imgs/image_only.png'


def test_questions_without_text_only_images(temp_dir):
    """Test image-only questions are handled correctly."""
    quiz_data = {
        'image_only.yaml': {
            'title': 'Image Quiz',
            'questions': [
                {
                    'image': '/imgs/question1.png',
                    'options': ['/imgs/a.png', '/imgs/b.png', '/imgs/c.png'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))

        q = embedded_questions[0]
        assert 'question' not in q, "Image-only question should not have question text"
        assert q['image'] == '/imgs/question1.png'
        assert q['options'] == ['/imgs/a.png', '/imgs/b.png', '/imgs/c.png']


def test_template_placeholder_replacement(temp_dir):
    """Test that all template placeholders are properly replaced."""
    quiz_data = {
        'placeholder_test.yaml': {
            'title': 'Placeholder Test Quiz',
            'questions': [
                {
                    'question': 'Test?',
                    'options': ['Yes', 'No'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verify no unreplaced placeholders remain
        assert '{{QUESTIONS_DATA}}' not in html_content, "QUESTIONS_DATA placeholder should be replaced"
        assert '{{QUIZ_TITLE}}' not in html_content, "QUIZ_TITLE placeholder should be replaced"
        assert '{{WEBQUIZ_VERSION}}' not in html_content, "WEBQUIZ_VERSION placeholder should be replaced"

        # Verify the actual data is present
        assert 'Placeholder Test Quiz' in html_content
        assert 'let questions = [' in html_content
        assert 'WebQuiz v' in html_content


def test_index_html_file_created_in_static_dir(temp_dir):
    """Test that index.html is created in the correct static directory."""
    with custom_webquiz_server() as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        # Verify static directory was created
        assert static_path.exists(), f"Static directory should be created at {static_path}"
        assert static_path.is_dir(), "Static path should be a directory"

        # Verify index.html file was created
        assert index_path.exists(), "index.html should be created"
        assert index_path.is_file(), "index.html should be a file"

        # Verify file has content
        assert index_path.stat().st_size > 0, "index.html should not be empty"


def test_index_html_content_is_valid_html(temp_dir):
    """Test that generated HTML has valid basic structure."""
    with custom_webquiz_server() as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Basic HTML structure checks
        assert html_content.startswith('<!DOCTYPE html>')
        assert '<html lang="en">' in html_content
        assert '<head>' in html_content and '</head>' in html_content
        assert '<body>' in html_content and '</body>' in html_content
        assert '</html>' in html_content

        # Check required meta tags
        assert '<meta charset="UTF-8">' in html_content
        assert '<meta name="viewport"' in html_content

        # Check for required JavaScript
        assert '<script>' in html_content and '</script>' in html_content
        assert 'let questions =' in html_content


def test_regeneration_on_quiz_switch(temp_dir):
    """Test that index.html is regenerated when switching quizzes."""
    quiz1_data = {
        'default.yaml': {  # Use default.yaml so it loads automatically
            'title': 'First Quiz',
            'questions': [
                {
                    'question': 'Question 1?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        },
        'quiz2.yaml': {
            'title': 'Second Quiz',
            'questions': [
                {
                    'question': 'Question 2?',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz1_data) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        # Read initial HTML
        with open(index_path, 'r', encoding='utf-8') as f:
            initial_html = f.read()

        assert 'First Quiz' in initial_html
        assert 'Question 1?' in initial_html

        # Switch to second quiz
        headers = {'X-Master-Key': 'test123'}
        switch_response = requests.post(
            f'http://localhost:{port}/api/admin/switch-quiz',
            headers=headers,
            json={'quiz_filename': 'quiz2.yaml'}
        )
        assert switch_response.status_code == 200

        # Read updated HTML
        with open(index_path, 'r', encoding='utf-8') as f:
            updated_html = f.read()

        # Verify content changed
        assert 'Second Quiz' in updated_html
        assert 'Question 2?' in updated_html
        assert 'First Quiz' not in updated_html
        assert 'Question 1?' not in updated_html

        # Verify questions array was updated
        questions_match = re.search(r'let questions = (\[.*?\]);', updated_html, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))
        assert len(embedded_questions) == 1
        assert embedded_questions[0]['options'] == ['X', 'Y', 'Z']


def test_multiple_quiz_data_formats(temp_dir):
    """Test index generation with different quiz data structures."""
    varied_quiz = {
        'varied.yaml': {
            'title': 'Varied Format Quiz',
            'description': 'Testing different formats',
            'questions': [
                {
                    'question': 'Simple text question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                },
                {
                    'image': '/imgs/visual.png',
                    'options': ['Visual A', 'Visual B', 'Visual C'],
                    'correct_answer': 2
                },
                {
                    'question': 'Mixed question with image?',
                    'image': '/imgs/mixed.jpg',
                    'options': ['/imgs/opt1.png', '/imgs/opt2.png'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=varied_quiz) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))

        assert len(embedded_questions) == 3

        # Text only
        q1 = embedded_questions[0]
        assert 'question' in q1
        assert 'image' not in q1

        # Image only
        q2 = embedded_questions[1]
        assert 'question' not in q2
        assert q2['image'] == '/imgs/visual.png'

        # Mixed (both text and image)
        q3 = embedded_questions[2]
        assert 'question' in q3
        assert q3['image'] == '/imgs/mixed.jpg'


def test_empty_quiz_handling(temp_dir):
    """Test handling of quiz with no questions."""
    empty_quiz = {
        'empty.yaml': {
            'title': 'Empty Quiz',
            'questions': []
        }
    }

    with custom_webquiz_server(quizzes=empty_quiz) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Should still generate valid HTML
        assert '<title>Empty Quiz</title>' in html_content

        # Questions array should be empty
        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))
        assert embedded_questions == []


def test_special_characters_in_quiz_data(temp_dir):
    """Test proper JSON escaping of special characters."""
    special_quiz = {
        'special_chars.yaml': {
            'title': 'Quiz "with" special & characters',
            'questions': [
                {
                    'question': 'What about "quotes" & <tags>?',
                    'options': [
                        'Option with "quotes"',
                        'Option with & ampersand',
                        'Option with <html> tags',
                        "Option with 'single quotes'"
                    ],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=special_quiz) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verify title is properly escaped
        assert 'Quiz "with" special & characters' in html_content

        # Extract and parse questions JSON to verify proper escaping
        questions_match = re.search(r'let questions = (\[.*?\]);', html_content, re.DOTALL)
        embedded_questions = json.loads(questions_match.group(1))  # This will fail if JSON is invalid

        q = embedded_questions[0]
        assert q['question'] == 'What about "quotes" & <tags>?'
        assert 'Option with "quotes"' in q['options']
        assert 'Option with & ampersand' in q['options']
        assert 'Option with <html> tags' in q['options']


def test_very_long_quiz_titles(temp_dir):
    """Test handling of extremely long quiz titles."""
    long_title = "This is a very " * 50 + "long quiz title!"

    long_title_quiz = {
        'long_title.yaml': {
            'title': long_title,
            'questions': [
                {
                    'question': 'Short question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=long_title_quiz) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verify long title is properly embedded
        assert f'<title>{long_title}</title>' in html_content
        assert f'<h1>{long_title}</h1>' in html_content

        # Verify HTML structure is still valid
        assert html_content.count('<title>') == 1
        assert html_content.count('</title>') == 1


def test_index_html_served_correctly(temp_dir):
    """Test that generated index.html is properly served via HTTP."""
    with custom_webquiz_server() as (proc, port):
        # Request the root path which should serve index.html
        response = requests.get(f'http://localhost:{port}/')

        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/html'

        html_content = response.text

        # Verify it's the generated index.html
        assert 'let questions =' in html_content
        assert 'WebQuiz v' in html_content
        assert '<script>' in html_content


def test_quiz_switch_updates_index_html(temp_dir):
    """Test that quiz switching properly updates the served index.html."""
    quiz_a = {
        'default.yaml': {  # Use default.yaml so it loads automatically
            'title': 'Quiz A Title',
            'questions': [
                {
                    'question': 'Question A?',
                    'options': ['A1', 'A2'],
                    'correct_answer': 0
                }
            ]
        },
        'quiz_b.yaml': {
            'title': 'Quiz B Title',
            'questions': [
                {
                    'question': 'Question B?',
                    'options': ['B1', 'B2', 'B3'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_a) as (proc, port):
        # Get initial served content
        initial_response = requests.get(f'http://localhost:{port}/')
        initial_html = initial_response.text

        assert 'Quiz A Title' in initial_html
        assert 'Question A?' in initial_html

        # Switch quiz
        headers = {'X-Master-Key': 'test123'}
        requests.post(
            f'http://localhost:{port}/api/admin/switch-quiz',
            headers=headers,
            json={'quiz_filename': 'quiz_b.yaml'}
        )

        # Get updated served content
        updated_response = requests.get(f'http://localhost:{port}/')
        updated_html = updated_response.text

        assert 'Quiz B Title' in updated_html
        assert 'Question B?' in updated_html
        assert 'Quiz A Title' not in updated_html


def test_multiple_quizzes_generate_different_content(temp_dir):
    """Test that different quizzes produce different index.html content."""
    quiz_1 = {
        'test_quiz.yaml': {  # Single quiz will auto-load
            'title': 'Unique Quiz One',
            'questions': [
                {
                    'question': 'Unique question 1?',
                    'options': ['U1', 'U2'],
                    'correct_answer': 0
                }
            ]
        }
    }

    quiz_2 = {
        'test_quiz.yaml': {  # Single quiz will auto-load
            'title': 'Unique Quiz Two',
            'questions': [
                {
                    'question': 'Different question 2?',
                    'options': ['D1', 'D2', 'D3', 'D4'],
                    'correct_answer': 2
                },
                {
                    'question': 'Another question?',
                    'options': ['X', 'Y'],
                    'correct_answer': 1
                }
            ]
        }
    }

    # Test first quiz
    with custom_webquiz_server(quizzes=quiz_1) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_1 = f.read()

    # Test second quiz
    with custom_webquiz_server(quizzes=quiz_2) as (proc, port):
        static_path = Path(temp_dir) / f'static_{port}'
        index_path = static_path / 'index.html'

        with open(index_path, 'r', encoding='utf-8') as f:
            html_2 = f.read()

    # Verify different content
    assert html_1 != html_2, "Different quizzes should generate different HTML"

    # Verify specific differences
    assert 'Unique Quiz One' in html_1
    assert 'Unique Quiz Two' in html_2
    assert 'Unique question 1?' in html_1
    assert 'Different question 2?' in html_2

    # Check questions arrays are different
    q1_match = re.search(r'let questions = (\[.*?\]);', html_1, re.DOTALL)
    q2_match = re.search(r'let questions = (\[.*?\]);', html_2, re.DOTALL)

    q1_data = json.loads(q1_match.group(1))
    q2_data = json.loads(q2_match.group(1))

    assert len(q1_data) == 1
    assert len(q2_data) == 2
    assert q1_data != q2_data