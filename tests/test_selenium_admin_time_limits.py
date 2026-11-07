"""Selenium tests for the time limit fields in the admin quiz editor."""

import requests
import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from conftest import custom_webquiz_server, get_admin_session
from selenium_helpers import browser, skip_if_selenium_disabled, wait_for_element
from test_selenium_admin_decimal_points import expand_question, save_quiz
from test_selenium_quiz_editor import admin_login, select_and_edit_quiz


def timed_quiz(time_limit):
    data = {
        "title": "Editor Time Limits",
        "questions": [
            {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "time_limit": 10},
            {"question": "Q2", "options": ["A", "B"], "correct_answer": 1},
        ],
    }
    if time_limit is not None:
        data["time_limit"] = time_limit
    return {"default.yaml": data}


def saved_quiz(port):
    cookies = get_admin_session(port)
    response = requests.get(f"http://localhost:{port}/api/admin/quiz/default.yaml", cookies=cookies)
    return yaml.safe_load(response.json()["content"])


@skip_if_selenium_disabled
def test_editor_loads_and_saves_per_question_time_limit(temp_dir, browser):
    with custom_webquiz_server(quizzes=timed_quiz({"per_question": 30})) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        mode = Select(wait_for_element(browser, By.ID, "time-limit-mode"))
        assert mode.first_selected_option.get_attribute("value") == "per_question"
        assert browser.find_element(By.ID, "time-limit-seconds").get_attribute("value") == "30"
        item = expand_question(browser, 0)
        question_field = item.find_element(By.CSS_SELECTOR, ".question-time-limit-input")
        assert question_field.get_attribute("value") == "10"
        assert question_field.is_displayed()

        save_quiz(browser)

        quiz = saved_quiz(port)
        assert quiz["time_limit"] == {"per_question": 30}
        assert quiz["questions"][0]["time_limit"] == 10
        assert "time_limit" not in quiz["questions"][1]


@skip_if_selenium_disabled
def test_editor_hides_question_field_outside_per_question_mode(temp_dir, browser):
    with custom_webquiz_server(quizzes=timed_quiz({"per_question": 30})) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        Select(wait_for_element(browser, By.ID, "time-limit-mode")).select_by_value("whole_quiz")
        seconds = browser.find_element(By.ID, "time-limit-seconds")
        seconds.clear()
        seconds.send_keys("600")

        item = expand_question(browser, 0)
        assert not item.find_element(By.CSS_SELECTOR, ".question-time-limit-group").is_displayed()

        save_quiz(browser)

        quiz = saved_quiz(port)
        assert quiz["time_limit"] == {"whole_quiz": 600}
        assert quiz["questions"][0]["time_limit"] == 10  # kept while hidden


@skip_if_selenium_disabled
def test_editor_sets_none_removes_time_limit(temp_dir, browser):
    with custom_webquiz_server(quizzes=timed_quiz({"whole_quiz": 900})) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)

        Select(wait_for_element(browser, By.ID, "time-limit-mode")).select_by_value("none")
        assert not browser.find_element(By.ID, "time-limit-seconds").is_displayed()

        save_quiz(browser)

        assert "time_limit" not in saved_quiz(port)
