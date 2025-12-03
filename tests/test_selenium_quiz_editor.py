"""
Selenium tests for quiz editor collapsible questions feature.

Tests verify:
1. Questions are collapsed by default when editing an existing quiz
2. Clicking on a question header toggles the collapsed state
3. New questions added are expanded by default
4. Question preview text is displayed in the header
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

    login_button = browser.find_element(By.CSS_SELECTOR, "button[onclick='login()']")
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

        # Give time for questions to load
        time.sleep(0.5)

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
            assert body_height == "0px", f"Question {i+1} body should have max-height: 0px when collapsed, got {body_height}"


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
        time.sleep(0.5)

        # Get the question item
        question_item = browser.find_element(By.CSS_SELECTOR, ".question-item")
        question_header = question_item.find_element(By.CSS_SELECTOR, ".question-header")

        # Initially collapsed
        assert "collapsed" in question_item.get_attribute("class")

        # Click header to expand
        question_header.click()
        time.sleep(0.3)  # Wait for animation

        # Should be expanded now
        assert "collapsed" not in question_item.get_attribute("class"), "Question should be expanded after click"

        # Click header again to collapse
        question_header.click()
        time.sleep(0.3)

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
        time.sleep(0.5)

        # Find and click the "Add Question" button
        add_button = browser.find_element(By.XPATH, "//button[contains(text(), 'Додати Питання')]")
        add_button.click()
        time.sleep(0.3)

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
                {"image": "/imgs/test.png", "options": ["A", "B"], "correct_answer": 0},
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
        time.sleep(0.5)

        # Get question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Check first question preview (text question)
        preview1 = question_items[0].find_element(By.CSS_SELECTOR, ".question-preview")
        assert "What is the capital of Ukraine?" in preview1.text, f"Preview should contain question text, got: {preview1.text}"

        # Check second question preview (image question)
        preview2 = question_items[1].find_element(By.CSS_SELECTOR, ".question-preview")
        assert "[Зображення]" in preview2.text, f"Preview should indicate image, got: {preview2.text}"


@skip_if_selenium_disabled
def test_reorder_buttons_work_when_collapsed(temp_dir, browser):
    """Test that reorder and delete buttons work without expanding the question."""
    quiz_data = {
        "test_quiz.yaml": {
            "title": "Reorder Test Quiz",
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
        time.sleep(0.5)

        # Get question items
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Both should be collapsed
        assert "collapsed" in question_items[0].get_attribute("class")
        assert "collapsed" in question_items[1].get_attribute("class")

        # Find and click the down button on the first question
        down_button = question_items[0].find_element(By.CSS_SELECTOR, "button[onclick*='down']")
        down_button.click()
        time.sleep(0.3)

        # Questions should be reordered but still collapsed
        question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")

        # Verify questions are still collapsed (clicking button shouldn't expand)
        assert "collapsed" in question_items[0].get_attribute("class"), "First question should still be collapsed"
        assert "collapsed" in question_items[1].get_attribute("class"), "Second question should still be collapsed"

        # Verify order changed by checking preview text
        preview1 = question_items[0].find_element(By.CSS_SELECTOR, ".question-preview")
        assert "Question 2" in preview1.text, "Questions should have been reordered"
