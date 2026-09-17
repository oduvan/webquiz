"""
Selenium tests for decimal question points in the student UI.

Checks that the points badge shows decimal values, and that the final results
table shows a decimal score without binary floating point noise.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from conftest import custom_webquiz_server
from selenium_helpers import (
    skip_if_selenium_disabled,
    browser,
    register_user,
    find_options,
    find_option_by_text,
    wait_for_clickable,
    wait_for_element,
)


@skip_if_selenium_disabled
def test_points_badge_shows_decimal_value(browser):
    """A question worth 0.5 points shows a badge with 0.5, not 1 or 0."""
    quiz_data = {
        "default.yaml": {
            "title": "Decimal Points Badge",
            "questions": [
                {"question": "Worth half a point", "options": ["A", "B"], "correct_answer": 0, "points": 0.5}
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        badge = wait_for_element(browser, By.CSS_SELECTOR, ".question-points-badge")
        assert badge is not None, "Points badge should be shown for a 0.5 point question"
        assert "0.5" in badge.text, f"Badge should show 0.5, got: {badge.text}"


@skip_if_selenium_disabled
def test_no_badge_for_default_one_point(browser):
    """A question worth the default 1 point shows no badge."""
    quiz_data = {
        "default.yaml": {
            "title": "Default Points",
            "questions": [{"question": "Plain question", "options": ["A", "B"], "correct_answer": 0}],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)
        find_options(browser)

        badges = browser.find_elements(By.CSS_SELECTOR, ".question-points-badge")
        assert len(badges) == 0, "No points badge should be shown for a 1 point question"


@skip_if_selenium_disabled
def test_final_score_shows_clean_decimal(browser):
    """Final score for 0.1 + 0.2 reads 0.3, not 0.30000000000000004."""
    quiz_data = {
        "default.yaml": {
            "title": "Inexact Points",
            "show_right_answer": True,
            "questions": [
                {"question": "First question?", "options": ["Right", "Wrong"], "correct_answer": 0, "points": 0.1},
                {"question": "Second question?", "options": ["Right", "Wrong"], "correct_answer": 0, "points": 0.2},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Answer the first question correctly
        find_option_by_text(browser, "Right").click()
        browser.find_element(By.ID, "submit-answer-btn").click()
        wait_for_clickable(browser, By.ID, "continue-btn").click()

        # Answer the second question correctly
        WebDriverWait(browser, 10).until(
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".question-text"), "Second question?")
        )
        find_option_by_text(browser, "Right").click()
        browser.find_element(By.ID, "submit-answer-btn").click()
        wait_for_clickable(browser, By.ID, "continue-btn").click()

        WebDriverWait(browser, 10).until(lambda driver: "2/2 (100%)" in driver.page_source)

        results_text = browser.find_element(By.ID, "results").text
        assert "0.30000000000000004" not in results_text, f"Float noise leaked into the results: {results_text}"
        assert "0.3/0.3" in results_text, f"Expected a 0.3/0.3 points score, got: {results_text}"
