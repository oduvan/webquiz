"""
Selenium tests for entering decimal question points in the admin quiz editor.

Verifies the points input accepts values like 0.5 and 0.25, that the editor
saves them, and that they are still there when the quiz is reopened.
"""

import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from conftest import custom_webquiz_server, get_admin_session
from selenium_helpers import skip_if_selenium_disabled, browser, wait_for_element
from test_selenium_quiz_editor import admin_login, select_and_edit_quiz


QUIZ = {
    "default.yaml": {
        "title": "Editor Points Quiz",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Q2", "options": ["A", "B"], "correct_answer": 1},
        ],
    }
}


def expand_question(browser, index):
    """Expand the Nth question - the editor collapses them all by default."""
    question_items = browser.find_elements(By.CSS_SELECTOR, ".question-item")
    assert len(question_items) > index, f"Expected more than {index} questions"
    item = question_items[index]
    if "collapsed" in item.get_attribute("class"):
        header = item.find_element(By.CSS_SELECTOR, ".question-header")
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", header)
        # Click via JS: the editor's sticky action bar can sit over the header
        browser.execute_script("arguments[0].click();", header)
        WebDriverWait(browser, 10).until(
            lambda d: "collapsed"
            not in d.find_elements(By.CSS_SELECTOR, ".question-item")[index].get_attribute("class")
        )
        time.sleep(0.5)  # let the expand transition finish
    return browser.find_elements(By.CSS_SELECTOR, ".question-item")[index]


def set_points(browser, index, value):
    """Type a points value into the Nth question's points input."""
    item = expand_question(browser, index)
    field = item.find_element(By.CSS_SELECTOR, ".points-input")
    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", field)
    field.clear()
    field.send_keys(value)
    return field


def save_quiz(browser):
    """Click the editor's save button and wait for the modal to close."""
    save_btn = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Зберегти Quiz')]"))
    )
    browser.execute_script("arguments[0].click();", save_btn)
    WebDriverWait(browser, 10).until(EC.invisibility_of_element_located((By.ID, "quiz-editor-modal")))


@skip_if_selenium_disabled
def test_points_input_accepts_decimal_values(browser):
    """The points input is not restricted to whole numbers."""
    with custom_webquiz_server(quizzes=QUIZ) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        field = set_points(browser, 0, "0.25")

        assert field.get_attribute("value") == "0.25", "Input should hold the decimal value"
        assert field.get_attribute("step") == "0.01", "Input should step by 0.01"
        # A browser marks a number input invalid when the value breaks step/min
        assert browser.execute_script("return arguments[0].checkValidity();", field), "0.25 should be a valid value"


@skip_if_selenium_disabled
def test_editor_saves_decimal_points(browser):
    """Values typed as 0.5 and 0.25 are saved into the quiz file."""
    with custom_webquiz_server(quizzes=QUIZ) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        set_points(browser, 0, "0.5")
        set_points(browser, 1, "0.25")
        save_quiz(browser)

        cookies = get_admin_session(port)
        content = requests.get(f"http://localhost:{port}/api/admin/quiz/default.yaml", cookies=cookies).json()[
            "content"
        ]

        assert "points: 0.5" in content, f"0.5 was not saved. Quiz file:\n{content}"
        assert "points: 0.25" in content, f"0.25 was not saved. Quiz file:\n{content}"


@skip_if_selenium_disabled
def test_decimal_points_reload_into_editor(browser):
    """A quiz already holding decimal points shows them when reopened."""
    quiz = {
        "default.yaml": {
            "title": "Stored Points Quiz",
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 0.25},
                {"question": "Q2", "options": ["A", "B"], "correct_answer": 1, "points": 2.5},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        values = [
            expand_question(browser, i).find_element(By.CSS_SELECTOR, ".points-input").get_attribute("value")
            for i in range(2)
        ]

        assert values[0] == "0.25", f"Expected 0.25 in the first points input, got {values}"
        assert values[1] == "2.5", f"Expected 2.5 in the second points input, got {values}"


@skip_if_selenium_disabled
def test_zero_points_falls_back_to_default(browser):
    """Typing 0 points saves the default instead of a value the server rejects."""
    with custom_webquiz_server(quizzes=QUIZ) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        set_points(browser, 0, "0")
        save_quiz(browser)

        cookies = get_admin_session(port)
        content = requests.get(f"http://localhost:{port}/api/admin/quiz/default.yaml", cookies=cookies).json()[
            "content"
        ]

        assert "points: 0" not in content, f"0 points should not be saved. Quiz file:\n{content}"


@skip_if_selenium_disabled
def test_trophy_indicator_shows_for_half_point(browser):
    """A 0.5 point question shows the trophy indicator in the collapsed header."""
    quiz = {
        "default.yaml": {
            "title": "Indicator Quiz",
            "questions": [{"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 0.5}],
        }
    }

    with custom_webquiz_server(quizzes=quiz) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        indicator = wait_for_element(browser, By.CSS_SELECTOR, ".points-indicator")
        assert indicator is not None, "Trophy indicator should be shown for a 0.5 point question"
        assert "0.5" in indicator.get_attribute("innerHTML"), f"Indicator should show 0.5, got: {indicator.text}"
