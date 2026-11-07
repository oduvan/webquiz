"""Selenium tests for the settings pop-up shown when the admin starts a quiz."""

import os

import requests
import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from conftest import custom_webquiz_server, register_student
from selenium_helpers import browser, skip_if_selenium_disabled, wait_for_element
from test_selenium_quiz_editor import admin_login


def quiz(**settings):
    return {
        "q.yaml": {
            "title": "Start Pop-up",
            "questions": [
                {"question": "Q1?", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2?", "options": ["A", "B"], "correct_answer": 1},
            ],
            **settings,
        }
    }


def open_start_popup(browser, port):
    admin_login(browser, port)
    quiz_select = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "quiz-select")))
    quiz_select.find_elements(By.TAG_NAME, "option")[0].click()
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.ID, "switch-btn"))).click()
    return WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.ID, "start-quiz-modal")))


def checked(browser, element_id):
    return browser.find_element(By.ID, element_id).is_selected()


@skip_if_selenium_disabled
def test_start_popup_shows_quiz_file_values(temp_dir, browser):
    quizzes = quiz(
        show_right_answer=False,
        show_answers_on_completion=True,
        randomize_questions=True,
        show_final_list=False,
        time_limit={"per_question": 45},
    )
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        open_start_popup(browser, port)
        WebDriverWait(browser, 5).until(
            lambda d: d.find_element(By.ID, "start-time-limit-seconds").get_attribute("value") == "45"
        )
        assert not checked(browser, "start-show-right-answer")
        assert browser.find_element(By.ID, "start-show-answers-on-completion").is_displayed()
        assert checked(browser, "start-show-answers-on-completion")
        assert checked(browser, "start-randomize-questions")
        assert not checked(browser, "start-show-final-list")
        mode = Select(browser.find_element(By.ID, "start-time-limit-mode"))
        assert mode.first_selected_option.get_attribute("value") == "per_question"


@skip_if_selenium_disabled
def test_start_popup_changes_apply_only_to_the_running_quiz(temp_dir, browser):
    quizzes = quiz(show_final_list=True, time_limit={"per_question": 45})
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        quiz_path = os.path.join(temp_dir, f"quizzes_{port}", "q.yaml")
        with open(quiz_path, encoding="utf-8") as f:
            before = f.read()

        open_start_popup(browser, port)
        seconds = browser.find_element(By.ID, "start-time-limit-seconds")
        WebDriverWait(browser, 5).until(lambda d: seconds.get_attribute("value") == "45")
        seconds.clear()
        seconds.send_keys("20")
        browser.find_element(By.ID, "start-show-final-list").click()  # turn it off
        browser.find_element(By.ID, "start-quiz-confirm").click()
        WebDriverWait(browser, 10).until(EC.invisibility_of_element_located((By.ID, "start-quiz-modal")))

        user_id = register_student(port)
        started = requests.post(
            f"http://localhost:{port}/api/question-start", json={"user_id": user_id, "question_id": 1}
        ).json()
        assert 19 < started["remaining_seconds"] <= 20
        assert "let showFinalList = false" in requests.get(f"http://localhost:{port}/").text

        with open(quiz_path, encoding="utf-8") as f:
            assert f.read() == before  # the quiz file is not changed
        assert yaml.safe_load(before)["time_limit"] == {"per_question": 45}


@skip_if_selenium_disabled
def test_start_popup_cancel_does_not_restart_the_quiz(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        user_id = register_student(port)
        open_start_popup(browser, port)
        browser.find_element(By.ID, "start-quiz-cancel").click()
        WebDriverWait(browser, 5).until(EC.invisibility_of_element_located((By.ID, "start-quiz-modal")))
        # A restart would clear all students
        assert requests.get(f"http://localhost:{port}/api/verify-user/{user_id}").json()["valid"] is True


@skip_if_selenium_disabled
def test_start_popup_fits_mobile_width(temp_dir, browser):
    browser.set_window_size(375, 800)
    with custom_webquiz_server(quizzes=quiz(time_limit={"whole_quiz": 600})) as (proc, port):
        open_start_popup(browser, port)
        wait_for_element(browser, By.ID, "start-quiz-confirm")
        assert browser.execute_script("return document.documentElement.scrollWidth <= window.innerWidth")
        assert browser.find_element(By.ID, "start-quiz-confirm").is_displayed()
