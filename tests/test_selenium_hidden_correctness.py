"""Selenium tests: the results table when correct answers are hidden.

With show_right_answer: false (and answers not revealed yet), the server does not
send which answers were right. The table used to show a "Correct" column with
"unknown" in every row, next to a summary that shows the score. The column is
now left out while correctness is hidden; the summary stays.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server
from selenium_helpers import browser, register_user, skip_if_selenium_disabled, wait_for_question_containing_text

EN = {"language": "en"}


def quiz(**settings):
    return {
        "q.yaml": {
            "title": "Hidden",
            "questions": [
                {"question": "First?", "options": ["Right", "Wrong"], "correct_answer": 0},
                {"question": "Second?", "options": ["Right", "Wrong"], "correct_answer": 0},
            ],
            **settings,
        }
    }


def answer(browser, option_index):
    WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.ID, f"option_{option_index}"))).click()
    WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.ID, "submit-answer-btn"))).click()


def results_table(browser):
    return WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".results-table")))


@skip_if_selenium_disabled
def test_hidden_correctness_leaves_out_the_correct_column(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=quiz(show_right_answer=False)) as (proc, port):
        register_user(browser, port)
        wait_for_question_containing_text(browser, "First?")
        answer(browser, 0)
        wait_for_question_containing_text(browser, "Second?")
        answer(browser, 1)

        table = results_table(browser)
        headers = [th.text.strip() for th in table.find_elements(By.TAG_NAME, "th")]
        assert "Correct" not in headers
        assert "unknown" not in table.text
        # The student's own answers and the score summary are still shown
        assert "Right" in table.text and "Wrong" in table.text
        assert "Result: 1/2 (50%)" in browser.find_element(By.ID, "results").text


@skip_if_selenium_disabled
def test_shown_correctness_keeps_the_correct_column(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=quiz(show_right_answer=True)) as (proc, port):
        register_user(browser, port)
        wait_for_question_containing_text(browser, "First?")
        answer(browser, 0)
        WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.ID, "continue-btn"))).click()
        wait_for_question_containing_text(browser, "Second?")
        answer(browser, 1)
        WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.ID, "continue-btn"))).click()

        table = results_table(browser)
        headers = [th.text.strip() for th in table.find_elements(By.TAG_NAME, "th")]
        assert "Correct" in headers
        assert "✓" in table.text and "✗" in table.text
