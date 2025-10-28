"""Tests for auto-advance behavior when show_right_answer is false."""

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
    find_register_button,
    find_option_by_text,
    wait_for_question_text,
    wait_for_question_containing_text,
)


@skip_if_selenium_disabled
def test_auto_advance_with_show_right_answer_false(temp_dir, browser):
    """Test that quiz auto-advances to next question when show_right_answer is false."""
    quiz_data = {
        "default.yaml": {
            "title": "Auto Advance Quiz",
            "show_right_answer": False,
            "questions": [
                {"question": "Question 1?", "options": ["A", "B", "C"], "correct_answer": 1},
                {"question": "Question 2?", "options": ["X", "Y", "Z"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        # Register user
        username_input = wait_for_element(browser, By.ID, "username")
        username_input.send_keys("AutoAdvanceTester")
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, "current-question-container")

        # Verify we're on question 1
        assert "Question 1?" in browser.page_source

        # Select and submit answer for question 1
        option = find_option_by_text(browser, "A")
        option.click()

        submit_button = browser.find_element(By.ID, "submit-answer-btn")
        submit_button.click()

        # Continue button should NOT appear (verify it stays hidden)
        continue_button = browser.find_element(By.ID, "continue-btn")
        assert "hidden" in continue_button.get_attribute(
            "class"
        ), "Continue button should remain hidden with auto-advance"

        # Question 2 should appear automatically without clicking continue
        # Wait for animation to complete (200ms delay + 900ms fade-out + 1000ms fade-in)
        wait_for_question_containing_text(browser, "Question 2?", timeout=5)
        question_text = browser.find_element(By.CSS_SELECTOR, ".question-text")
        assert "Question 2?" in question_text.text, "Should auto-advance to Question 2 without clicking continue button"

        # Submit answer for question 2
        option2 = find_option_by_text(browser, "X")
        option2.click()
        browser.find_element(By.ID, "submit-answer-btn").click()

        # Should auto-advance to results
        wait_for_element(browser, By.ID, "results", timeout=3)
        assert "Результат:" in browser.page_source


@skip_if_selenium_disabled
def test_manual_continue_with_show_right_answer_true(temp_dir, browser):
    """Test that quiz requires manual continue button click when show_right_answer is true."""
    quiz_data = {
        "default.yaml": {
            "title": "Manual Continue Quiz",
            "show_right_answer": True,
            "questions": [
                {"question": "Question 1?", "options": ["A", "B", "C"], "correct_answer": 1},
                {"question": "Question 2?", "options": ["X", "Y", "Z"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        # Register user
        username_input = wait_for_element(browser, By.ID, "username")
        username_input.send_keys("ManualContinueTester")
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, "current-question-container")

        # Verify we're on question 1
        assert "Question 1?" in browser.page_source

        # Select and submit answer for question 1
        option = find_option_by_text(browser, "A")
        option.click()

        submit_button = browser.find_element(By.ID, "submit-answer-btn")
        submit_button.click()

        # Continue button SHOULD appear and be clickable
        continue_button = wait_for_clickable(browser, By.ID, "continue-btn", timeout=3)
        assert "hidden" not in continue_button.get_attribute(
            "class"
        ), "Continue button should be visible with show_right_answer: true"

        # Verify feedback is shown
        assert "feedback-" in browser.page_source, "Visual feedback should be shown with show_right_answer: true"

        # Wait a moment to ensure no auto-advance happens
        time.sleep(1.5)

        # Should still be on question 1 (no auto-advance)
        # Check the displayed question text, not the page source (which includes all questions in embedded JS)
        question_text = browser.find_element(By.CSS_SELECTOR, ".question-text")
        assert "Question 1?" in question_text.text, "Should NOT auto-advance when show_right_answer is true"

        # Now click continue button manually
        continue_button.click()

        # Now should advance to question 2
        # Wait for the text to actually change (animation takes ~2 seconds)
        WebDriverWait(browser, 5).until(
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".question-text"), "Question 2?")
        )
        question_text = browser.find_element(By.CSS_SELECTOR, ".question-text")
        assert "Question 2?" in question_text.text


@skip_if_selenium_disabled
def test_auto_advance_multiple_questions(temp_dir, browser):
    """Test auto-advance through multiple questions seamlessly."""
    quiz_data = {
        "default.yaml": {
            "title": "Multi Question Auto Advance",
            "show_right_answer": False,
            "questions": [
                {"question": "Q1?", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2?", "options": ["C", "D"], "correct_answer": 1},
                {"question": "Q3?", "options": ["E", "F"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        # Register user
        username_input = wait_for_element(browser, By.ID, "username")
        username_input.send_keys("MultiAutoTester")
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, "current-question-container")

        # Answer Q1
        assert "Q1?" in browser.page_source
        find_option_by_text(browser, "A").click()
        browser.find_element(By.ID, "submit-answer-btn").click()

        # Should auto-advance to Q2 (wait for animation)
        wait_for_question_containing_text(browser, "Q2?", timeout=5)
        assert "Q2?" in browser.page_source

        # Answer Q2
        find_option_by_text(browser, "C").click()
        browser.find_element(By.ID, "submit-answer-btn").click()

        # Should auto-advance to Q3 (wait for animation)
        wait_for_question_containing_text(browser, "Q3?", timeout=5)
        assert "Q3?" in browser.page_source

        # Answer Q3
        find_option_by_text(browser, "E").click()
        browser.find_element(By.ID, "submit-answer-btn").click()

        # Should auto-advance to results
        wait_for_element(browser, By.ID, "results", timeout=3)
        assert "Результат:" in browser.page_source


@skip_if_selenium_disabled
def test_auto_advance_no_visual_feedback(temp_dir, browser):
    """Test that auto-advance happens without showing visual feedback."""
    quiz_data = {
        "default.yaml": {
            "title": "No Feedback Auto Advance",
            "show_right_answer": False,
            "questions": [
                {"question": "Question?", "options": ["Wrong", "Right"], "correct_answer": 1},
                {"question": "Next?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        # Register user
        username_input = wait_for_element(browser, By.ID, "username")
        username_input.send_keys("NoFeedbackTester")
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, "current-question-container")

        # Select WRONG answer
        wrong_option = find_option_by_text(browser, "Wrong")
        correct_option = find_option_by_text(browser, "Right")

        wrong_option.click()
        browser.find_element(By.ID, "submit-answer-btn").click()

        # Wait for next question to appear (wait for animation)
        wait_for_question_containing_text(browser, "Next?", timeout=5)

        # Verify we're on next question (check displayed text, not page source)
        question_text = browser.find_element(By.CSS_SELECTOR, ".question-text")
        assert "Next?" in question_text.text, "Should have auto-advanced to next question"


@skip_if_selenium_disabled
def test_auto_advance_to_results_last_question(temp_dir, browser):
    """Test that auto-advance works correctly for the last question going to results."""
    quiz_data = {
        "default.yaml": {
            "title": "Last Question Auto Advance",
            "show_right_answer": False,
            "questions": [
                {"question": "Only Question?", "options": ["A", "B"], "correct_answer": 0},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        # Register user
        username_input = wait_for_element(browser, By.ID, "username")
        username_input.send_keys("LastQuestionTester")
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, "current-question-container")

        # Answer the only question
        find_option_by_text(browser, "A").click()
        browser.find_element(By.ID, "submit-answer-btn").click()

        # Should auto-advance directly to results without continue button
        wait_for_element(browser, By.ID, "results", timeout=3)
        assert "Результат:" in browser.page_source

        # Verify continue button never appeared
        continue_button = browser.find_element(By.ID, "continue-btn")
        assert "hidden" in continue_button.get_attribute("class")


@skip_if_selenium_disabled
def test_button_state_during_auto_advance(temp_dir, browser):
    """Test that submit button is properly hidden during auto-advance."""
    quiz_data = {
        "default.yaml": {
            "title": "Button State Test",
            "show_right_answer": False,
            "questions": [
                {"question": "First?", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Second?", "options": ["C", "D"], "correct_answer": 1},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        # Register user
        username_input = wait_for_element(browser, By.ID, "username")
        username_input.send_keys("ButtonStateTester")
        find_register_button(browser).click()

        wait_for_element(browser, By.ID, "current-question-container")

        # Submit first answer
        find_option_by_text(browser, "A").click()
        submit_button = browser.find_element(By.ID, "submit-answer-btn")
        submit_button.click()

        # Wait for next question to appear (auto-advance should happen, wait for animation)
        wait_for_question_containing_text(browser, "Second?", timeout=5)

        # Verify we're on second question with fresh button state
        question_text = browser.find_element(By.CSS_SELECTOR, ".question-text")
        assert "Second?" in question_text.text

        # Re-find submit button after DOM update (auto-advance replaces the DOM)
        submit_button = browser.find_element(By.ID, "submit-answer-btn")

        # Submit button should be visible again (but disabled until selection)
        assert "hidden" not in submit_button.get_attribute("class"), "Submit button should be visible on new question"
        assert submit_button.get_attribute("disabled") == "true", "Submit button should be disabled initially"
