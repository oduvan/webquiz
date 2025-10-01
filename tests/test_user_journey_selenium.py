import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from conftest import custom_webquiz_server
from selenium_helpers import (
    skip_if_selenium_disabled,
    browser,
    wait_for_element,
    wait_for_clickable,
    find_register_button,
    find_option_by_index,
    find_option_by_text,
    wait_for_question_text
)


@skip_if_selenium_disabled
def test_user_registration_complete_flow(temp_dir, browser):
    """Test complete user registration workflow."""
    quiz_data = {
        'default.yaml': {
            'title': 'Registration Test Quiz',
            'questions': [
                {
                    'question': 'Test registration question?',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        # Navigate to quiz
        browser.get(f'http://localhost:{port}/')

        # Wait for loading to complete and registration form to appear
        username_input = wait_for_element(browser, By.ID, 'username')

        # Verify registration form elements
        assert username_input.is_displayed()
        register_button = find_register_button(browser)
        assert register_button.is_displayed()

        # Test registration with valid username
        username_input.send_keys('TestUser123')
        register_button.click()

        # Wait for quiz section to appear (registration successful)
        quiz_section = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'test-section'))
        )

        # Verify user info is displayed
        user_info = wait_for_element(browser, By.ID, 'user-info')
        assert 'TestUser123' in user_info.text


@skip_if_selenium_disabled
def test_registration_form_validation(temp_dir, browser):
    """Test registration form validation with empty username."""
    with custom_webquiz_server() as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Wait for registration form
        username_input = wait_for_element(browser, By.ID, 'username')
        register_button = find_register_button(browser)

        # Try to register with empty username
        register_button.click()

        # Should show alert or stay on registration page
        # The registration form should still be visible
        assert username_input.is_displayed()

        # Registration section should still be visible
        registration_section = browser.find_element(By.ID, 'registration')
        assert not registration_section.get_attribute('class').__contains__('hidden')


@skip_if_selenium_disabled
def test_complete_quiz_journey(temp_dir, browser):
    """Test complete end-to-end quiz taking journey."""
    quiz_data = {
        'default.yaml': {
            'title': 'Complete Journey Test',
            'questions': [
                {
                    'question': 'What is 2 + 2?',
                    'options': ['3', '4', '5'],
                    'correct_answer': 1
                },
                {
                    'question': 'What is the capital of France?',
                    'options': ['London', 'Paris', 'Berlin'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register user
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('JourneyTester')
        register_button = find_register_button(browser)
        register_button.click()

        # Wait for quiz to start
        question_container = wait_for_element(browser, By.ID, 'current-question-container')

        # Answer first question
        assert 'What is 2 + 2?' in browser.page_source

        # Select correct answer (option with text "4")
        option_element = find_option_by_text(browser, "4")
        option_element.click()

        # Verify option is selected
        assert 'selected' in option_element.get_attribute('class')

        # Submit answer
        submit_button = wait_for_clickable(browser, By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback and continue button
        continue_button = wait_for_clickable(browser, By.ID, 'continue-btn')

        # Verify feedback styling
        assert 'feedback-correct' in option_element.get_attribute('class')

        # Continue to next question
        continue_button.click()

        # Answer second question
        wait_for_question_text(browser)

        paris_option = find_option_by_text(browser, "Paris")
        paris_option.click()

        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        continue_button = wait_for_clickable(browser, By.ID, 'continue-btn')
        continue_button.click()

        # Wait for results page to load
        wait_for_element(browser, By.ID, 'results')

        # Verify that the basic quiz journey worked:
        # 1. We reached the results page
        # 2. Results content is shown
        assert 'Результат:' in browser.page_source
        print("SUCCESS: Quiz journey completed successfully - reached results page")


@skip_if_selenium_disabled
def test_question_selection_and_feedback(temp_dir, browser):
    """Test question selection and visual feedback system."""
    quiz_data = {
        'default.yaml': {
            'title': 'Feedback Test',
            'questions': [
                {
                    'question': 'Test question for feedback?',
                    'options': ['Wrong', 'Correct', 'Also Wrong'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register and start quiz
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('FeedbackTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Test selecting different options
        wrong_option = find_option_by_text(browser, "Wrong")
        correct_option = find_option_by_text(browser, "Correct")

        # Select wrong option first
        wrong_option.click()
        assert 'selected' in wrong_option.get_attribute('class')
        assert 'selected' not in correct_option.get_attribute('class')

        # Change to correct option
        correct_option.click()
        assert 'selected' in correct_option.get_attribute('class')
        assert 'selected' not in wrong_option.get_attribute('class')

        # Submit button should be enabled
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        assert not submit_button.get_attribute('disabled')

        # Submit answer
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Verify correct feedback styling
        assert 'feedback-correct' in correct_option.get_attribute('class')

        # Verify options are disabled after submission
        assert 'disabled' in correct_option.get_attribute('class')


@skip_if_selenium_disabled
def test_progress_bar_functionality(temp_dir, browser):
    """Test progress bar updates throughout quiz."""
    quiz_data = {
        'default.yaml': {
            'title': 'Progress Test',
            'questions': [
                {
                    'question': 'Question 1?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                },
                {
                    'question': 'Question 2?',
                    'options': ['X', 'Y'],
                    'correct_answer': 1
                },
                {
                    'question': 'Question 3?',
                    'options': ['1', '2'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('ProgressTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Check initial progress
        progress_text = browser.find_element(By.ID, 'progress-text')
        assert 'Питання 1 з 3' in progress_text.text

        # Answer first question and continue
        find_option_by_index(browser, 0).click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check progress after first question
        progress_text = browser.find_element(By.ID, 'progress-text')
        assert 'Питання 2 з 3' in progress_text.text

        # Check progress bar fill
        progress_fill = browser.find_element(By.ID, 'progress-fill')
        width = progress_fill.get_attribute('style')
        # Should be approximately 67% (2/3)
        assert '66' in width or '67' in width

        # Complete second question
        find_option_by_index(browser, 1).click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check final progress
        progress_text = browser.find_element(By.ID, 'progress-text')
        assert 'Питання 3 з 3' in progress_text.text


@skip_if_selenium_disabled
def test_theme_toggle_functionality(temp_dir, browser):
    """Test dark/light theme switching."""
    with custom_webquiz_server() as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Wait for page to load
        wait_for_element(browser, By.ID, 'username')

        # Find theme toggle button
        theme_button = browser.find_element(By.CLASS_NAME, 'theme-toggle')

        # Check initial state (should be light theme)
        body = browser.find_element(By.TAG_NAME, 'body')
        initial_theme = body.get_attribute('data-theme')

        # Toggle to dark theme
        theme_button.click()

        # Verify theme changed
        time.sleep(0.5)  # Allow for transition
        new_theme = body.get_attribute('data-theme')
        assert new_theme != initial_theme

        # Toggle back
        theme_button.click()
        time.sleep(0.5)

        # Should be back to original state
        final_theme = body.get_attribute('data-theme')
        assert final_theme == initial_theme


@skip_if_selenium_disabled
def test_session_persistence_on_reload(temp_dir, browser):
    """Test that user session persists across page reload."""
    quiz_data = {
        'default.yaml': {
            'title': 'Session Test',
            'questions': [
                {
                    'question': 'Session test question?',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': 1
                },
                {
                    'question': 'Second question?',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register user
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('SessionTester')
        find_register_button(browser).click()

        # Start quiz
        wait_for_element(browser, By.ID, 'current-question-container')

        # Answer first question
        find_option_by_text(browser, "B").click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Verify we're on second question
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        question_text = browser.find_element(By.CSS_SELECTOR, '.question-text')
        assert 'Second question?' in question_text.text

        # Reload page
        browser.refresh()

        # Should skip registration and loading, go directly to current question
        # Wait for either the quiz section or results (depending on server state)
        try:
            # If quiz continues from where we left off
            current_question = wait_for_element(browser, By.ID, 'current-question-container', timeout=5)
            # Should be on second question or results
            assert current_question.is_displayed()
        except TimeoutException:
            # Or if already completed, should show results
            results = wait_for_element(browser, By.ID, 'results', timeout=5)
            assert results.is_displayed()

        # User info should still be displayed
        user_info = browser.find_element(By.ID, 'user-info')
        assert 'SessionTester' in browser.page_source


@skip_if_selenium_disabled
def test_different_question_types(temp_dir, browser):
    """Test quiz with different question formats."""
    quiz_data = {
        'default.yaml': {
            'title': 'Mixed Question Types',
            'questions': [
                {
                    'question': 'Text only question?',
                    'options': ['Text A', 'Text B'],
                    'correct_answer': 0
                },
                {
                    'question': 'Question with image?',
                    'image': '/imgs/test.jpg',
                    'options': ['With image A', 'With image B'],
                    'correct_answer': 1
                },
                {
                    # Image-only question
                    'image': '/imgs/image-only.png',
                    'options': ['Image only A', 'Image only B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('TypeTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Question 1: Text only
        assert 'Text only question?' in browser.page_source
        find_option_by_text(browser, "Text A").click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Question 2: Text with image
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        question_text = browser.find_element(By.CSS_SELECTOR, '.question-text')
        assert 'Question with image?' in question_text.text
        # Should have both text and image
        assert 'Question with image?' in browser.page_source
        try:
            image = browser.find_element(By.CLASS_NAME, 'question-image')
            assert image.is_displayed()
        except NoSuchElementException:
            # Image might not load in headless mode, but img tag should exist
            img_tag = browser.find_element(By.CSS_SELECTOR, 'img[src*="/imgs/test.jpg"]')
            assert img_tag

        find_option_by_text(browser, "With image B").click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Question 3: Image only (no text)
        # Should not have question text, only image and options
        current_html = browser.page_source
        assert 'Image only A' in current_html  # Options should be there

        find_option_by_text(browser, 'Image only A').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Should reach results - wait for content to be fully rendered
        WebDriverWait(browser, 10).until(
            lambda driver: '3/3 (100%)' in driver.page_source
        )
        assert 'Результат:' in browser.page_source
        assert '3/3 (100%)' in browser.page_source


@skip_if_selenium_disabled
def test_button_state_management(temp_dir, browser):
    """Test submit/continue button behavior and state management."""
    quiz_data = {
        'default.yaml': {
            'title': 'Button Test',
            'questions': [
                {
                    'question': 'Button test question?',
                    'options': ['Option 1', 'Option 2'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('ButtonTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Initially submit button should be disabled
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        continue_button = browser.find_element(By.ID, 'continue-btn')

        assert submit_button.get_attribute('disabled') == 'true'
        assert 'hidden' in continue_button.get_attribute('class')

        # Select an option - submit button should be enabled
        find_option_by_text(browser, 'Option 1').click()
        assert submit_button.get_attribute('disabled') is None

        # Submit answer
        submit_button.click()

        # After submission:
        # - Submit button should be hidden
        # - Continue button should be visible and clickable
        wait_for_clickable(browser, By.ID, 'continue-btn')

        assert 'hidden' in submit_button.get_attribute('class')
        assert 'hidden' not in continue_button.get_attribute('class')


@skip_if_selenium_disabled
def test_results_display_accuracy(temp_dir, browser):
    """Test that results display matches expected calculations."""
    quiz_data = {
        'default.yaml': {
            'title': 'Results Accuracy Test',
            'questions': [
                {
                    'question': 'Correct answer question?',
                    'options': ['Wrong', 'Right', 'Wrong2'],
                    'correct_answer': 1
                },
                {
                    'question': 'Incorrect answer question?',
                    'options': ['Wrong', 'Right', 'Wrong2'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('ResultsTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Answer first question correctly
        find_option_by_text(browser, 'Right').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Answer second question incorrectly
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        question_text = browser.find_element(By.CSS_SELECTOR, '.question-text')
        assert 'Incorrect answer question?' in question_text.text
        find_option_by_text(browser, 'Wrong').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results - wait for actual content to be rendered
        WebDriverWait(browser, 10).until(
            lambda driver: '1/2 (50%)' in driver.page_source
        )

        # Should show 1/2 (50%)
        assert 'Результат:' in browser.page_source
        assert '1/2 (50%)' in browser.page_source

        # Check results table exists
        results_table = browser.find_element(By.CLASS_NAME, 'results-table')
        assert results_table.is_displayed()

        # Should have checkmarks and X marks
        assert '✓' in browser.page_source
        assert '✗' in browser.page_source


@skip_if_selenium_disabled
def test_browser_navigation_behavior(temp_dir, browser):
    """Test back/forward button behavior during quiz."""
    quiz_data = {
        'default.yaml': {
            'title': 'Navigation Test',
            'questions': [
                {
                    'question': 'Navigation test?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('NavTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Try browser back button
        browser.back()

        # Should still be on the same page or handle gracefully
        # The quiz should continue functioning
        try:
            # Either we're still on quiz page
            browser.find_element(By.ID, 'current-question-container')
        except NoSuchElementException:
            # Or we went back but can navigate forward
            browser.forward()
            wait_for_element(browser, By.ID, 'current-question-container')

        # Quiz should still be functional
        find_option_by_text(browser, 'A').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()

        # Should be able to complete quiz
        wait_for_clickable(browser, By.ID, 'continue-btn').click()
        wait_for_element(browser, By.ID, 'results')


@skip_if_selenium_disabled
def test_show_right_answer_true_visual_feedback(temp_dir, browser):
    """Test visual feedback when show_right_answer is true (default behavior)."""
    quiz_data = {
        'default.yaml': {
            'title': 'Show Answers Quiz',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'What is 2 + 2?',
                    'options': ['3', '4', '5', '6'],
                    'correct_answer': 1  # '4' is correct
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register user
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('ShowAnswersTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Select WRONG answer intentionally
        wrong_option = find_option_by_text(browser, '3')  # Wrong answer
        correct_option = find_option_by_text(browser, '4')  # Correct answer
        
        wrong_option.click()
        
        # Submit answer
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # With show_right_answer: true, BOTH wrong and correct answers should be highlighted
        assert 'feedback-incorrect' in wrong_option.get_attribute('class'), "Wrong answer should be highlighted as incorrect"
        assert 'feedback-correct' in correct_option.get_attribute('class'), "Correct answer should be highlighted as correct"
        
        # Continue to results
        continue_button = browser.find_element(By.ID, 'continue-btn')
        continue_button.click()

        # Wait for results
        wait_for_element(browser, By.ID, 'results')
        
        # Results should show correct answer hint
        assert 'Правильна:' in browser.page_source, "Results should show 'Correct:' hint"
        assert '4' in browser.page_source, "Results should show the correct answer '4'"


@skip_if_selenium_disabled
def test_show_right_answer_false_visual_feedback(temp_dir, browser):
    """Test visual feedback when show_right_answer is false (hides correct answers)."""
    quiz_data = {
        'default.yaml': {
            'title': 'Hide Answers Quiz',
            'show_right_answer': False,
            'questions': [
                {
                    'question': 'What is 3 + 3?',
                    'options': ['5', '6', '7', '8'],
                    'correct_answer': 1  # '6' is correct
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register user
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('HideAnswersTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Select WRONG answer intentionally
        wrong_option = find_option_by_text(browser, '5')  # Wrong answer
        correct_option = find_option_by_text(browser, '6')  # Correct answer
        
        wrong_option.click()
        
        # Submit answer
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # With show_right_answer: false, NO visual feedback should be shown at all
        assert 'feedback-incorrect' not in wrong_option.get_attribute('class'), "Wrong answer should NOT be highlighted when show_right_answer is false"
        assert 'feedback-correct' not in correct_option.get_attribute('class'), "Correct answer should NOT be highlighted when show_right_answer is false"
        
        # Options should still be disabled after submission
        assert 'disabled' in wrong_option.get_attribute('class'), "Options should be disabled after submission"
        
        # Continue to results
        continue_button = browser.find_element(By.ID, 'continue-btn')
        continue_button.click()

        # Wait for results
        wait_for_element(browser, By.ID, 'results')

        # Debug: Check the showRightAnswer variable value and results HTML
        show_right_answer_value = browser.execute_script("return showRightAnswer;")
        print(f"DEBUG: showRightAnswer = {show_right_answer_value}")

        results_content = browser.execute_script("return document.getElementById('results-content').innerHTML;")
        print(f"DEBUG: results content = {results_content[:500]}")

        # Results should NOT show correct answer hints (check actual rendered content, not page source)
        results_content = browser.execute_script("return document.getElementById('results-content').innerHTML;")
        assert 'Правильна:' not in results_content, "Results should NOT show 'Correct:' hint when show_right_answer is false"
        
        # Should show the score but not the correct answers
        assert '0/1' in browser.page_source or '0%' in browser.page_source, "Results should show score"


@skip_if_selenium_disabled
def test_show_right_answer_false_correct_answer_visual_feedback(temp_dir, browser):
    """Test visual feedback when show_right_answer is false and user answers correctly."""
    quiz_data = {
        'default.yaml': {
            'title': 'Hide Answers Quiz',
            'show_right_answer': False,
            'questions': [
                {
                    'question': 'What is 4 + 4?',
                    'options': ['6', '7', '8', '9'],
                    'correct_answer': 2  # '8' is correct
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register user
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('CorrectAnswerTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Select CORRECT answer
        correct_option = find_option_by_text(browser, '8')  # Correct answer
        
        correct_option.click()
        
        # Submit answer
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # With show_right_answer: false, NO visual feedback should be shown even for correct answers
        assert 'feedback-correct' not in correct_option.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        
        # Options should still be disabled after submission
        assert 'disabled' in correct_option.get_attribute('class'), "Options should be disabled after submission"
        
        # Continue to results
        continue_button = browser.find_element(By.ID, 'continue-btn')
        continue_button.click()

        # Wait for results
        wait_for_element(browser, By.ID, 'results')
        
        # Results should show perfect score but no correct answer hints
        assert '1/1' in browser.page_source or '100%' in browser.page_source, "Results should show perfect score"
        results_content = browser.execute_script("return document.getElementById('results-content').innerHTML;")
        assert 'Правильна:' not in results_content, "Results should NOT show 'Correct:' hint even for correct answers when show_right_answer is false"


@skip_if_selenium_disabled
def test_show_right_answer_multi_question_journey(temp_dir, browser):
    """Test complete quiz journey with mixed correct/incorrect answers and show_right_answer disabled."""
    quiz_data = {
        'default.yaml': {
            'title': 'Multi Question Hide Answers Quiz',
            'show_right_answer': False,
            'questions': [
                {
                    'question': 'What is 1 + 1?',
                    'options': ['1', '2', '3', '4'],
                    'correct_answer': 1  # '2' is correct
                },
                {
                    'question': 'What is 2 * 3?',
                    'options': ['4', '5', '6', '7'],
                    'correct_answer': 2  # '6' is correct
                },
                {
                    'question': 'What is 10 / 2?',
                    'options': ['3', '4', '5', '6'],
                    'correct_answer': 2  # '5' is correct
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register user
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('MultiQuestionTester')
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Question 1: Answer CORRECTLY
        correct_option_1 = find_option_by_text(browser, '2')
        correct_option_1.click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        
        # Should show NO feedback at all when show_right_answer is false
        wait_for_clickable(browser, By.ID, 'continue-btn')
        assert 'feedback-correct' not in correct_option_1.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        
        # Continue to next question
        browser.find_element(By.ID, 'continue-btn').click()

        # Question 2: Answer INCORRECTLY  
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        question_text = browser.find_element(By.CSS_SELECTOR, '.question-text')
        assert 'What is 2 * 3?' in question_text.text
        wrong_option_2 = find_option_by_text(browser, '4')  # Wrong: should be 6
        correct_option_2 = find_option_by_text(browser, '6')  # Correct answer
        
        wrong_option_2.click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        
        # Should show NO feedback on any option when show_right_answer is false
        wait_for_clickable(browser, By.ID, 'continue-btn')
        assert 'feedback-incorrect' not in wrong_option_2.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        assert 'feedback-correct' not in correct_option_2.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        
        # Continue to next question
        browser.find_element(By.ID, 'continue-btn').click()

        # Question 3: Answer INCORRECTLY
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        question_text = browser.find_element(By.CSS_SELECTOR, '.question-text')
        assert 'What is 10 / 2?' in question_text.text
        wrong_option_3 = find_option_by_text(browser, '3')  # Wrong: should be 5
        correct_option_3 = find_option_by_text(browser, '5')  # Correct answer
        
        wrong_option_3.click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        
        # Should show NO feedback on any option when show_right_answer is false
        wait_for_clickable(browser, By.ID, 'continue-btn')
        assert 'feedback-incorrect' not in wrong_option_3.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        assert 'feedback-correct' not in correct_option_3.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        
        # Continue to results
        browser.find_element(By.ID, 'continue-btn').click()

        # Wait for results
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'results'))
        )

        # Should show 1/3 (33%) but NO correct answer hints anywhere
        assert 'Результат: 1/3' in browser.page_source or '1/3' in browser.page_source, "Results should show 1 out of 3 correct"
        assert '33%' in browser.page_source or '(33%)' in browser.page_source, "Results should show 33% score"
        results_content = browser.execute_script("return document.getElementById('results-content').innerHTML;")
        assert 'Правильна:' not in results_content, "Results should NOT show any 'Correct:' hints when show_right_answer is false"
        
        # Results table should exist but without correct answer columns/hints
        results_table = browser.find_element(By.CLASS_NAME, 'results-table')
        assert results_table.is_displayed()
        
        # Should have checkmarks and X marks for user's answers
        assert '✓' in browser.page_source, "Should show checkmark for correct answer"
        assert '✗' in browser.page_source, "Should show X marks for incorrect answers"