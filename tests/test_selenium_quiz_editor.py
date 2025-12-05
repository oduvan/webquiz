"""
Selenium tests for quiz editor collapsible questions feature.

Tests verify:
1. Questions are collapsed by default when editing an existing quiz
2. Clicking on a question header toggles the collapsed state
3. New questions added are expanded by default
4. Question preview text is displayed in the header
5. File/image indicators are shown
6. Drag handle is present for reordering
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from conftest import custom_webquiz_server
from selenium_helpers import (
    skip_if_selenium_disabled,
    browser,
    wait_for_element,
    wait_for_clickable,
)


def admin_login(browser, port, master_key="test123"):
    """Helper to log in to admin panel."""
    browser.get(f"http://localhost:{port}/admin/")

    # Wait for login form and enter master key
    password_input = wait_for_element(browser, By.ID, "master-key")
    password_input.send_keys(master_key)

    login_button = browser.find_element(By.CSS_SELECTOR, "button[onclick='authenticate()']")
    login_button.click()

    # Wait for admin panel to load
    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, "quiz-management"))
    )


@skip_if_selenium_disabled
def test_questions_collapsed_when_editing_quiz(temp_dir, browser):
    """Test that questions are collapsed by default when editing an existing quiz."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Collapsible Test Quiz",
            "questions": [
                {"question": "Question 1 text here", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Question 2 text here", "options": ["C", "D"], "correct_answer": 1},
                {"question": "Question 3 text here", "options": ["E", "F"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button for the quiz
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        edit_button = None
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                edit_button = btn
                break

        assert edit_button is not None, "Edit button not found"
        edit_button.click()

        # Wait for the quiz editor modal to open
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )

        # Give time for questions to load (increased for CI environments)
        time.sleep(1.0)

        # Find all question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")
        assert len(question_items) == 3, f"Expected 3 questions, found {len(question_items)}"

        # Verify all questions are collapsed
        for i, item in enumerate(question_items):
            assert "collapsed" in item.get_attribute("class"), f"Question {i+1} should be collapsed"

            # Verify the question body is hidden (max-height: 0)
            question_body = item.find_element(By.CSS_SELECTOR, ".question-body")
            # When collapsed, the body should have 0 height due to CSS
            body_height = question_body.value_of_css_property("max-height")
            # CSS might return "0px" or "0" depending on browser
            assert body_height in ("0px", "0"), f"Question {i+1} body should have max-height: 0 when collapsed, got {body_height}"


@skip_if_selenium_disabled
def test_click_header_toggles_collapse(temp_dir, browser):
    """Test that clicking on a question header toggles the collapsed state."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Toggle Test Quiz",
            "questions": [
                {"question": "Toggle question text", "options": ["Yes", "No"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                btn.click()
                break

        # Wait for modal
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )
        time.sleep(1.0)  # Increased for CI environments

        # Get the question item
        question_item = browser.find_element(By.CSS_SELECTOR, ".question-item")
        question_header = question_item.find_element(By.CSS_SELECTOR, ".question-header")

        # Initially collapsed
        assert "collapsed" in question_item.get_attribute("class")

        # Click header to expand
        question_header.click()
        time.sleep(1.0)  # Wait for animation (increased for CI)

        # Should be expanded now
        assert "collapsed" not in question_item.get_attribute("class"), "Question should be expanded after click"

        # Click header again to collapse
        question_header.click()
        time.sleep(1.0)  # Increased for CI

        # Should be collapsed again
        assert "collapsed" in question_item.get_attribute("class"), "Question should be collapsed after second click"


@skip_if_selenium_disabled
def test_new_question_is_expanded(temp_dir, browser):
    """Test that newly added questions are expanded by default."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "New Question Test",
            "questions": [
                {"question": "Existing question", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                btn.click()
                break

        # Wait for modal
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )
        time.sleep(1.0)

        # Find and click the "Add Question" button
        add_button = browser.find_element(By.XPATH, "//button[contains(text(), 'Додати Питання')]")
        add_button.click()
        time.sleep(0.5)

        # Get all question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")
        assert len(question_items) == 2, "Should have 2 questions now"

        # First question (existing) should be collapsed
        assert "collapsed" in question_items[0].get_attribute("class"), "Existing question should remain collapsed"

        # Second question (new) should be expanded
        assert "collapsed" not in question_items[1].get_attribute("class"), "New question should be expanded"


@skip_if_selenium_disabled
def test_question_preview_text_displayed(temp_dir, browser):
    """Test that question preview text is displayed in the collapsed header."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Preview Test Quiz",
            "questions": [
                {"question": "What is the capital of Ukraine?", "options": ["Kyiv", "Lviv"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                btn.click()
                break

        # Wait for modal
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )
        time.sleep(1.0)

        # Get question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Check first question preview (text question)
        preview1 = question_items[0].find_element(By.CSS_SELECTOR, ".question-preview")
        assert "What is the capital of Ukraine?" in preview1.text, f"Preview should contain question text, got: {preview1.text}"


@skip_if_selenium_disabled
def test_file_image_indicators_displayed(temp_dir, browser):
    """Test that file and image indicators are displayed in the collapsed header."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Indicators Test Quiz",
            "questions": [
                {"question": "Question with image", "image": "/imgs/test.png", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Question with file", "file": "data.xlsx", "options": ["C", "D"], "correct_answer": 0},
                {"question": "Question with both", "image": "/imgs/pic.jpg", "file": "doc.pdf", "options": ["E", "F"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                btn.click()
                break

        # Wait for modal
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )
        time.sleep(1.0)

        # Get question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Check first question has image indicator
        indicators1 = question_items[0].find_element(By.CSS_SELECTOR, ".question-indicators")
        # Use base emoji without variation selector for cross-platform compatibility
        assert "\U0001F5BC" in indicators1.text or "🖼" in indicators1.text, f"First question should have image indicator, got: {indicators1.text}"

        # Check second question has file indicator
        indicators2 = question_items[1].find_element(By.CSS_SELECTOR, ".question-indicators")
        assert "\U0001F4CE" in indicators2.text or "📎" in indicators2.text, f"Second question should have file indicator, got: {indicators2.text}"

        # Check third question has both indicators
        indicators3 = question_items[2].find_element(By.CSS_SELECTOR, ".question-indicators")
        assert "\U0001F5BC" in indicators3.text or "🖼" in indicators3.text, f"Third question should have image indicator"
        assert "\U0001F4CE" in indicators3.text or "📎" in indicators3.text, f"Third question should have file indicator"


@skip_if_selenium_disabled
def test_drag_handle_present(temp_dir, browser):
    """Test that drag handle is present for reordering questions."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Drag Handle Test Quiz",
            "questions": [
                {"question": "Question 1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Question 2", "options": ["C", "D"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                btn.click()
                break

        # Wait for modal
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )
        time.sleep(1.0)

        # Get question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Verify drag handle is present on each question
        for i, item in enumerate(question_items):
            drag_handle = item.find_element(By.CSS_SELECTOR, ".drag-handle")
            assert drag_handle is not None, f"Question {i+1} should have drag handle"
            assert drag_handle.is_displayed(), f"Drag handle should be visible for question {i+1}"
            # Unicode TRIGRAM FOR HEAVEN (☰) or its codepoint
            assert "\u2630" in drag_handle.text or "☰" in drag_handle.text, f"Drag handle should show ☰ icon, got: {drag_handle.text}"


@skip_if_selenium_disabled
def test_question_numbers_without_prefix(temp_dir, browser):
    """Test that question numbers are displayed without 'Питання' prefix."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Numbers Test Quiz",
            "questions": [
                {"question": "Question 1", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Question 2", "options": ["C", "D"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        admin_login(browser, port)

        # Find and click edit button
        edit_buttons = browser.find_elements(By.CSS_SELECTOR, ".quiz-item button")
        for btn in edit_buttons:
            if "Редагувати" in btn.text or "Edit" in btn.text:
                btn.click()
                break

        # Wait for modal
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "quiz-editor-modal"))
        )
        time.sleep(1.0)

        # Get question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Check question numbers are just digits with dot
        number1 = question_items[0].find_element(By.CSS_SELECTOR, ".question-number")
        assert number1.text == "1.", f"First question number should be '1.', got: {number1.text}"

        number2 = question_items[1].find_element(By.CSS_SELECTOR, ".question-number")
        assert number2.text == "2.", f"Second question number should be '2.', got: {number2.text}"
