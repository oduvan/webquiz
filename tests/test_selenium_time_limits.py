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
    return {
        "timed.yaml": {"title": "Timed", "time_limit": time_limit, "questions": questions or [question()], **settings}
    }


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


@skip_if_selenium_disabled
def test_live_stats_shows_timeout_icon(temp_dir, browser):
    import requests

    quizzes = timed_quiz({"per_question": 30}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(config=EN, quizzes=quizzes) as (proc, port):
        base_url = f"http://localhost:{port}"
        user_id = requests.post(f"{base_url}/api/register", json={"username": "slowstudent"}).json()["user_id"]
        requests.post(f"{base_url}/api/question-start", json={"user_id": user_id, "question_id": 1})
        response = requests.post(
            f"{base_url}/api/submit-answer", json={"user_id": user_id, "question_id": 1, "selected_answer": None}
        )
        assert response.json()["timed_out"] is True

        browser.get(f"{base_url}/live-stats/")
        WebDriverWait(browser, 15).until(lambda d: "slowstudent" in d.page_source)
        body = browser.find_element(By.TAG_NAME, "body").text
        assert "⏱" in body, body
        assert "0/1" in body, body  # the timed-out question counts as answered (and failed)


@skip_if_selenium_disabled
def test_whole_quiz_time_up_locks_the_answer_while_sending(temp_dir, browser):
    """While the time-up answer is on its way (slow Wi-Fi), the student cannot send another answer."""
    quizzes = timed_quiz({"whole_quiz": 3}, questions=[question("Q1?"), question("Q2?")])
    with custom_webquiz_server(config=EN, quizzes=quizzes) as (proc, port):
        register_user(browser, port)
        wait_for_element(browser, By.ID, "quiz-timer")
        browser.find_element(By.ID, "option_0").click()  # selected, but not submitted
        # Slow network: every submit-answer request takes 3 seconds
        browser.execute_script(
            """
            const originalFetch = window.fetch;
            window.fetch = (url, options) => String(url).includes('submit-answer')
                ? new Promise(resolve => setTimeout(resolve, 3000)).then(() => originalFetch(url, options))
                : originalFetch(url, options);
        """
        )
        WebDriverWait(browser, 6).until(lambda d: d.find_element(By.ID, "quiz-timer").text.strip() == "0:00")
        time.sleep(0.5)  # the empty answer is now on its way

        assert browser.find_element(By.ID, "submit-answer-btn").get_attribute("disabled") is not None
        assert "disabled" in browser.find_element(By.ID, "option_1").get_attribute("class")

        WebDriverWait(browser, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, ".results-table .time-up-message")) == 2
        )
