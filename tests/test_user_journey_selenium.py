import pytest
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from conftest import custom_webquiz_server, get_worker_port

# Skip decorator for Selenium tests when SKIP_SELENIUM environment variable is set
skip_if_selenium_disabled = pytest.mark.skipif(
    os.getenv('SKIP_SELENIUM', '').lower() in ('true', '1', 'yes'),
    reason="Selenium tests skipped (SKIP_SELENIUM environment variable is set)"
)


@pytest.fixture
def browser():
    """Set up Chrome/Chromium browser in headless mode for testing."""
    # Get worker-specific port for parallel testing
    worker_port = get_worker_port()
    # Calculate debugging port based on worker port (9222 + offset)
    debug_port = 9222 + (worker_port - 8080)

    options = Options()
    options.add_argument('--headless')  # Always headless for CI/CD
    options.add_argument('--no-sandbox')  # Required for GitHub Actions
    options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
    options.add_argument('--disable-gpu')  # Disable GPU acceleration
    options.add_argument('--disable-extensions')  # Disable extensions
    options.add_argument('--disable-web-security')  # Disable web security for testing
    options.add_argument('--disable-features=VizDisplayCompositor')  # Fix rendering issues
    options.add_argument(f'--remote-debugging-port={debug_port}')  # Worker-specific debugging port
    options.add_argument('--window-size=1920,1080')  # Set consistent window size

    try:
        # Use webdriver-manager for cross-platform compatibility
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)

        yield driver

        # Cleanup
        driver.quit()
    except Exception as e:
        pytest.skip(f"Chrome/Chromium browser not available: {e}")


def wait_for_element(browser, by, selector, timeout=10):
    """Helper function to wait for element with better error handling."""
    try:
        return WebDriverWait(browser, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        print(f"Timeout waiting for element: {by}={selector}")
        print(f"Current page source: {browser.page_source[:500]}...")
        raise


def wait_for_clickable(browser, by, selector, timeout=10):
    """Helper function to wait for clickable element."""
    return WebDriverWait(browser, timeout).until(
        EC.element_to_be_clickable((by, selector))
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
        register_button = browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]')
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
        register_button = browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]')

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
        register_button = browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]')
        register_button.click()

        # Wait for quiz to start
        question_container = wait_for_element(browser, By.ID, 'current-question-container')

        # Answer first question
        assert 'What is 2 + 2?' in browser.page_source

        # Select correct answer (option with text "4")
        option_element = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "4")]')
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
        wait_for_element(browser, By.XPATH, '//h3[contains(text(), "What is the capital of France?")]')

        paris_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Paris")]')
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Test selecting different options
        wrong_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Wrong")]')
        correct_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Correct")]')

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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Check initial progress
        progress_text = browser.find_element(By.ID, 'progress-text')
        assert 'Питання 1 з 3' in progress_text.text

        # Answer first question and continue
        browser.find_element(By.XPATH, '//div[@class="option"][1]').click()
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
        browser.find_element(By.XPATH, '//div[@class="option"][2]').click()
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        # Start quiz
        wait_for_element(browser, By.ID, 'current-question-container')

        # Answer first question
        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "B")]').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Verify we're on second question
        wait_for_element(browser, By.XPATH, '//h3[contains(text(), "Second question?")]')

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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Question 1: Text only
        assert 'Text only question?' in browser.page_source
        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Text A")]').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Question 2: Text with image
        wait_for_element(browser, By.XPATH, '//h3[contains(text(), "Question with image?")]')
        # Should have both text and image
        assert 'Question with image?' in browser.page_source
        try:
            image = browser.find_element(By.CLASS_NAME, 'question-image')
            assert image.is_displayed()
        except NoSuchElementException:
            # Image might not load in headless mode, but img tag should exist
            img_tag = browser.find_element(By.XPATH, '//img[contains(@src, "/imgs/test.jpg")]')
            assert img_tag

        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "With image B")]').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Question 3: Image only (no text)
        # Should not have question text, only image and options
        current_html = browser.page_source
        assert 'Image only A' in current_html  # Options should be there

        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Image only A")]').click()
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Initially submit button should be disabled
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        continue_button = browser.find_element(By.ID, 'continue-btn')

        assert submit_button.get_attribute('disabled') == 'true'
        assert 'hidden' in continue_button.get_attribute('class')

        # Select an option - submit button should be enabled
        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Option 1")]').click()
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Answer first question correctly
        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Right")]').click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Answer second question incorrectly
        wait_for_element(browser, By.XPATH, '//h3[contains(text(), "Incorrect answer question?")]')
        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "Wrong")]').click()
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

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
        browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "A")]').click()
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Select WRONG answer intentionally
        wrong_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "3")]')  # Wrong answer
        correct_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "4")]')  # Correct answer
        
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Select WRONG answer intentionally
        wrong_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "5")]')  # Wrong answer
        correct_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "6")]')  # Correct answer
        
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Select CORRECT answer
        correct_option = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "8")]')  # Correct answer
        
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
        browser.find_element(By.XPATH, '//button[contains(text(), "Зареєструватися")]').click()

        wait_for_element(browser, By.ID, 'current-question-container')

        # Question 1: Answer CORRECTLY
        correct_option_1 = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "2")]')
        correct_option_1.click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        
        # Should show NO feedback at all when show_right_answer is false
        wait_for_clickable(browser, By.ID, 'continue-btn')
        assert 'feedback-correct' not in correct_option_1.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        
        # Continue to next question
        browser.find_element(By.ID, 'continue-btn').click()

        # Question 2: Answer INCORRECTLY  
        wait_for_element(browser, By.XPATH, '//h3[contains(text(), "What is 2 * 3?")]')
        wrong_option_2 = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "4")]')  # Wrong: should be 6
        correct_option_2 = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "6")]')  # Correct answer
        
        wrong_option_2.click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        
        # Should show NO feedback on any option when show_right_answer is false
        wait_for_clickable(browser, By.ID, 'continue-btn')
        assert 'feedback-incorrect' not in wrong_option_2.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        assert 'feedback-correct' not in correct_option_2.get_attribute('class'), "No feedback should be shown when show_right_answer is false"
        
        # Continue to next question
        browser.find_element(By.ID, 'continue-btn').click()

        # Question 3: Answer INCORRECTLY
        wait_for_element(browser, By.XPATH, '//h3[contains(text(), "What is 10 / 2?")]')
        wrong_option_3 = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "3")]')  # Wrong: should be 5
        correct_option_3 = browser.find_element(By.XPATH, '//div[@class="option" and contains(text(), "5")]')  # Correct answer
        
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