"""Selenium tests for the explanation step the student sees after answering a question."""

import base64
import os

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server
from selenium_helpers import (
    browser,
    find_option_by_index,
    register_user,
    skip_if_selenium_disabled,
    wait_for_clickable,
    wait_for_question_containing_text,
)

EN = {"language": "en"}

# A 1x1 PNG image
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def question(text, explanation=None):
    data = {"question": text, "options": ["A", "B"], "correct_answer": 0}
    if explanation is not None:
        data["explanation"] = explanation
    return data


def quiz(questions, **settings):
    data = {"title": "Explain", "show_right_answer": True, "show_explanation": True, "questions": questions}
    data.update(settings)
    return {"explain.yaml": data}


def answer_and_continue(browser):
    find_option_by_index(browser, 0).click()
    wait_for_clickable(browser, By.ID, "submit-answer-btn").click()
    wait_for_clickable(browser, By.ID, "continue-btn").click()


def wait_for_step(browser):
    return WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "explanation-step")))


def wait_for_progress(browser, text):
    WebDriverWait(browser, 5).until(EC.text_to_be_present_in_element((By.ID, "progress-text"), text))


@skip_if_selenium_disabled
def test_explanation_step_between_questions(temp_dir, browser):
    questions = [question("Q1?", "**Because** of A"), question("Q2?"), question("Q3?")]
    with custom_webquiz_server(config=EN, quizzes=quiz(questions)) as (proc, port):
        register_user(browser, port)
        answer_and_continue(browser)
        step = wait_for_step(browser)
        assert step.find_element(By.CSS_SELECTOR, ".explanation-content strong").text == "Because"
        assert "Q1?" in step.find_element(By.CSS_SELECTOR, ".explanation-question").text
        assert not browser.find_element(By.ID, "current-question-container").is_displayed()
        assert not browser.find_element(By.ID, "continue-btn").is_displayed()
        browser.find_element(By.ID, "explanation-next-btn").click()
        wait_for_progress(browser, "Question 2 of 3")
        wait_for_question_containing_text(browser, "Q2?")
        assert not browser.find_element(By.ID, "explanation-step").is_displayed()


@skip_if_selenium_disabled
def test_question_without_explanation_goes_straight_on(temp_dir, browser):
    questions = [question("Q1?"), question("Q2?", "Text")]
    with custom_webquiz_server(config=EN, quizzes=quiz(questions)) as (proc, port):
        register_user(browser, port)
        answer_and_continue(browser)
        wait_for_question_containing_text(browser, "Q2?")
        assert not browser.find_element(By.ID, "explanation-step").is_displayed()


@skip_if_selenium_disabled
def test_last_question_explanation_then_results(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=quiz([question("Only?", "Last words")])) as (proc, port):
        register_user(browser, port)
        answer_and_continue(browser)
        assert "Last words" in wait_for_step(browser).text
        browser.find_element(By.ID, "explanation-next-btn").click()
        WebDriverWait(browser, 5).until(EC.text_to_be_present_in_element((By.ID, "results"), "Result"))
        assert not browser.find_element(By.ID, "explanation-step").is_displayed()


@skip_if_selenium_disabled
def test_no_step_when_right_answer_hidden(temp_dir, browser):
    questions = [question("Q1?", "Hidden"), question("Q2?")]
    with custom_webquiz_server(config=EN, quizzes=quiz(questions, show_right_answer=False)) as (proc, port):
        register_user(browser, port)
        find_option_by_index(browser, 0).click()
        wait_for_clickable(browser, By.ID, "submit-answer-btn").click()
        wait_for_question_containing_text(browser, "Q2?")
        assert not browser.find_element(By.ID, "explanation-step").is_displayed()


@skip_if_selenium_disabled
def test_double_click_next_does_not_skip(temp_dir, browser):
    questions = [question("Q1?", "Read me"), question("Q2?"), question("Q3?")]
    with custom_webquiz_server(config=EN, quizzes=quiz(questions)) as (proc, port):
        register_user(browser, port)
        answer_and_continue(browser)
        wait_for_step(browser)
        ActionChains(browser).double_click(browser.find_element(By.ID, "explanation-next-btn")).perform()
        wait_for_progress(browser, "Question 2 of 3")
        wait_for_question_containing_text(browser, "Q2?")
        WebDriverWait(browser, 2).until(lambda d: "Question 2 of 3" in d.find_element(By.ID, "progress-text").text)


@skip_if_selenium_disabled
def test_whole_quiz_time_up_during_step_shows_results(temp_dir, browser):
    questions = [question("Q1?", "Slow reading"), question("Q2?")]
    quizzes = quiz(questions, time_limit={"whole_quiz": 5})
    env = {"WEBQUIZ_TIME_LIMIT_GRACE_SECONDS": "0"}
    with custom_webquiz_server(config=EN, quizzes=quizzes, env=env) as (proc, port):
        register_user(browser, port)
        answer_and_continue(browser)
        wait_for_step(browser)
        WebDriverWait(browser, 15).until(EC.text_to_be_present_in_element((By.ID, "results"), "Result"))
        assert not browser.find_element(By.ID, "explanation-step").is_displayed()


@skip_if_selenium_disabled
def test_explanation_fits_phone_width(temp_dir, browser):
    browser.set_window_size(375, 800)
    table = "| a | b | c | d | e | f |\n|---|---|---|---|---|---|\n" + "| long cell text | " * 6 + "\n"
    with custom_webquiz_server(config=EN, quizzes=quiz([question("Q1?", table), question("Q2?")])) as (proc, port):
        register_user(browser, port)
        answer_and_continue(browser)
        wait_for_step(browser)
        assert browser.execute_script("return document.documentElement.scrollWidth <= window.innerWidth")


@skip_if_selenium_disabled
def test_explanation_image_is_loaded(temp_dir, browser):
    explanation = "Look: ![dot](/imgs/dot.png)"
    with custom_webquiz_server(config=EN, quizzes=quiz([question("Q1?", explanation), question("Q2?")])) as (
        proc,
        port,
    ):
        with open(os.path.join(temp_dir, f"quizzes_{port}", "imgs", "dot.png"), "wb") as f:
            f.write(PNG)
        register_user(browser, port)
        answer_and_continue(browser)
        image = wait_for_step(browser).find_element(By.CSS_SELECTOR, ".explanation-content img")
        WebDriverWait(browser, 5).until(lambda d: d.execute_script("return arguments[0].naturalWidth", image) > 0)
