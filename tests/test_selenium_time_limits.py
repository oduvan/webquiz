"""Selenium tests for time limits on the student quiz page."""

import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server
from selenium_helpers import (
    browser,
    register_user,
    skip_if_selenium_disabled,
    wait_for_element,
    wait_for_question_containing_text,
)

EN = {"language": "en"}


def question(text="Q?", **extra):
    return {"question": text, "options": ["A", "B"], "correct_answer": 0, **extra}


def timed_quiz(time_limit, questions=None, **settings):
    return {"timed.yaml": {"title": "Timed", "time_limit": time_limit, "questions": questions or [question()], **settings}}


def timer_seconds(element):
    minutes, seconds = element.text.strip().split(":")
    return int(minutes) * 60 + int(seconds)


@skip_if_selenium_disabled
def test_question_countdown_is_shown(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=timed_quiz({"per_question": 5})) as (proc, port):
        register_user(browser, port)
        timer = wait_for_element(browser, By.ID, "question-timer")
        WebDriverWait(browser, 5).until(lambda d: re.match(r"^\d:\d\d$", timer.text.strip()))
        assert timer.is_displayed()
        assert not browser.find_element(By.ID, "quiz-timer").is_displayed()


@skip_if_selenium_disabled
def test_time_up_shows_message_and_continue(temp_dir, browser):
    quizzes = timed_quiz({"per_question": 2}, questions=[question("Q1?"), question("Q2?")], show_right_answer=True)
    with custom_webquiz_server(config=EN, quizzes=quizzes) as (proc, port):
        register_user(browser, port)
        message = WebDriverWait(browser, 6).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#current-question-container .time-up-message"))
        )
        assert "Time is up" in message.text
        WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "continue-btn")))


@skip_if_selenium_disabled
def test_time_up_auto_advances_without_right_answer(temp_dir, browser):
    quizzes = timed_quiz(
        {"per_question": 2}, questions=[question("First?"), question("Second?")], show_right_answer=False
    )
    with custom_webquiz_server(config=EN, quizzes=quizzes) as (proc, port):
        register_user(browser, port)
        wait_for_question_containing_text(browser, "First?")
        wait_for_question_containing_text(browser, "Second?", timeout=8)


@skip_if_selenium_disabled
def test_whole_quiz_time_up_shows_results(temp_dir, browser):
    quizzes = timed_quiz({"whole_quiz": 3}, questions=[question("Q1?"), question("Q2?"), question("Q3?")])
    with custom_webquiz_server(config=EN, quizzes=quizzes) as (proc, port):
        register_user(browser, port)
        quiz_timer = wait_for_element(browser, By.ID, "quiz-timer")
        assert quiz_timer.is_displayed()
        WebDriverWait(browser, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, ".results-table .time-up-message")) == 3
        )


@skip_if_selenium_disabled
def test_reload_keeps_counting_down(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=timed_quiz({"per_question": 20})) as (proc, port):
        register_user(browser, port)
        wait_for_element(browser, By.ID, "question-timer")
        time.sleep(4)
        browser.refresh()
        timer = wait_for_element(browser, By.ID, "question-timer")
        WebDriverWait(browser, 5).until(lambda d: re.match(r"^\d:\d\d$", timer.text.strip()))
        assert timer_seconds(timer) <= 17


@skip_if_selenium_disabled
def test_timer_fits_mobile_width(temp_dir, browser):
    browser.set_window_size(375, 800)
    quizzes = timed_quiz({"whole_quiz": 300}, questions=[question("A fairly long question text for a phone?")])
    with custom_webquiz_server(config=EN, quizzes=quizzes) as (proc, port):
        register_user(browser, port)
        wait_for_element(browser, By.ID, "quiz-timer")
        assert browser.execute_script("return document.documentElement.scrollWidth <= window.innerWidth")
