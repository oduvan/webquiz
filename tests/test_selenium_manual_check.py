"""Selenium tests for answers that the teacher checks by hand (manual_check: true)."""

import asyncio
import json

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server, register_student
from selenium_helpers import (
    browser,
    find_option_by_index,
    register_user,
    skip_if_selenium_disabled,
    wait_for_clickable,
    wait_for_element,
    wait_for_question_containing_text,
)
from test_manual_check import connect_review, recv_state, send_verdict, submit
from test_selenium_admin_start_settings import open_start_popup

EN = {"language": "en"}


def quiz(**settings):
    data = {
        "title": "Manual",
        "show_right_answer": True,
        "questions": [
            {"question": "Why is the sky blue?", "manual_check": True, "correct_value": "Scattering", "points": 2},
            {"question": "2 + 2?", "options": ["3", "4"], "correct_answer": 1},
        ],
    }
    data.update(settings)
    return {"manual.yaml": data}


def decide_first_waiting_answer(port, is_correct):
    """Act as a teacher: take the first waiting answer and give a verdict."""

    async def run():
        async with await connect_review(port) as ws:
            state = await recv_state(ws, lambda s: s["item"] is not None)
            await send_verdict(ws, state["item"]["review_id"], is_correct)
            await recv_state(ws, lambda s: s["item"] is None or s["item"]["review_id"] != state["item"]["review_id"])

    asyncio.run(run())


def answer_manual_then_choice(browser):
    wait_for_question_containing_text(browser, "Why is the sky blue?")
    text_input = wait_for_element(browser, By.ID, "text-answer-input")
    text_input.clear()
    text_input.send_keys("Light scatters")
    wait_for_clickable(browser, By.ID, "submit-answer-btn").click()
    message = WebDriverWait(browser, 5).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#checker-feedback .pending-review-message"))
    )
    assert "teacher will check it" in message.text
    wait_for_clickable(browser, By.ID, "continue-btn").click()
    wait_for_question_containing_text(browser, "2 + 2?")
    find_option_by_index(browser, 1).click()
    wait_for_clickable(browser, By.ID, "submit-answer-btn").click()
    wait_for_clickable(browser, By.ID, "continue-btn").click()


@skip_if_selenium_disabled
def test_results_wait_for_teacher_and_update_by_themselves(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=quiz()) as (proc, port):
        register_user(browser, port, "Student")
        answer_manual_then_choice(browser)

        notice = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "pending-review-notice"))
        )
        assert "not checked yet: 1" in notice.text
        row = browser.find_element(By.CSS_SELECTOR, ".results-table tr.pending-review-row")
        assert "Waiting for the teacher" in row.text
        assert len(browser.find_elements(By.CSS_SELECTOR, ".results-table tr.pending-review-row")) == 1

        decide_first_waiting_answer(port, True)

        done = WebDriverWait(browser, 12).until(EC.visibility_of_element_located((By.ID, "pending-review-done")))
        assert "checked all your answers" in done.text
        assert browser.find_elements(By.CSS_SELECTOR, ".results-table tr.pending-review-row") == []
        assert "2/2" in browser.find_element(By.ID, "results-content").text


@skip_if_selenium_disabled
def test_review_page_login_and_verdict(temp_dir, browser):
    with custom_webquiz_server(config=EN, quizzes=quiz()) as (proc, port):
        user_id = register_student(port, "Hidden Name")
        submit(port, user_id, 1, "Light scatters")
        submit(port, user_id, 2, 1)

        browser.get(f"http://localhost:{port}/review/")
        key_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.ID, "master-key-input")))
        key_input.send_keys("wrong")
        browser.find_element(By.ID, "login-button").click()
        WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "login-error")))
        key_input.clear()
        key_input.send_keys("test123")
        browser.find_element(By.ID, "login-button").click()

        card = WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.ID, "item-card")))
        assert "Why is the sky blue?" in card.text
        assert "Light scatters" in card.text
        assert "Scattering" in card.text
        assert "Hidden Name" not in browser.page_source
        assert "Waiting for a check: 1" in browser.find_element(By.ID, "pending-count").text

        wait_for_clickable(browser, By.ID, "verdict-incorrect").click()
        idle = WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "idle")))
        assert "No answers to check" in idle.text

        results = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}").json()["final_results"]
        assert results["test_results"][0]["is_correct"] is False
        assert results["pending_count"] == 0


@skip_if_selenium_disabled
def test_review_page_fits_phone_width(temp_dir, browser):
    browser.set_window_size(375, 800)
    with custom_webquiz_server(config=dict(EN, admin={"trusted_ips": ["127.0.0.1"]}), quizzes=quiz()) as (
        proc,
        port,
    ):
        submit(port, register_student(port), 1, "A long answer " * 20)
        browser.get(f"http://localhost:{port}/review/")
        WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.ID, "item-card")))
        assert browser.execute_script("return document.documentElement.scrollWidth <= window.innerWidth")
        assert browser.find_element(By.ID, "verdict-correct").is_displayed()
        assert browser.find_element(By.ID, "verdict-incorrect").is_displayed()


@skip_if_selenium_disabled
def test_start_popup_tells_about_manual_check(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        open_start_popup(browser, port)
        note = WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "start-manual-check-note")))
        assert "1" in browser.find_element(By.ID, "start-manual-check-count").text
        links = note.find_elements(By.CSS_SELECTOR, "a")
        assert links and all(link.get_attribute("href").endswith("/review/") for link in links)


@skip_if_selenium_disabled
def test_start_popup_has_no_note_without_manual_questions(temp_dir, browser):
    plain = {"q.yaml": {"title": "Plain", "questions": [{"question": "Q", "options": ["a", "b"], "correct_answer": 0}]}}
    with custom_webquiz_server(quizzes=plain) as (proc, port):
        open_start_popup(browser, port)
        assert not browser.find_element(By.ID, "start-manual-check-note").is_displayed()


@skip_if_selenium_disabled
def test_admin_panel_shows_review_status(temp_dir, browser):
    from test_selenium_quiz_editor import admin_login

    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        admin_login(browser, port)
        section = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, "manual-review-section"))
        )
        assert "Ніхто не перевіряє" in section.text
        submit(port, register_student(port), 1, "Light scatters")
        WebDriverWait(browser, 5).until(EC.text_to_be_present_in_element((By.ID, "manual-review-pending"), "1"))


@skip_if_selenium_disabled
def test_editor_saves_manual_check(temp_dir, browser):
    import os
    import time

    import yaml
    from test_selenium_quiz_editor import admin_login, select_and_edit_quiz

    quizzes = {
        "q.yaml": {
            "title": "Editor",
            "questions": [
                {"question": "Type it", "correct_value": "x", "checker": "assert user_answer == 'x'"},
                {"question": "By hand", "manual_check": True},
            ],
        }
    }
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        admin_login(browser, port)
        select_and_edit_quiz(browser)
        boxes = browser.find_elements(By.CSS_SELECTOR, ".manual-check-input")
        assert [box.is_selected() for box in boxes] == [False, True]
        groups = browser.find_elements(By.CSS_SELECTOR, ".checker-group")
        assert browser.execute_script("return arguments[0].style.display", groups[1]) == "none"

        # Turn manual check on for the first question: its checker code is hidden and not saved
        browser.execute_script("arguments[0].click()", boxes[0])
        assert browser.execute_script("return arguments[0].style.display", groups[0]) == "none"
        browser.find_element(By.ID, "save-continue-btn").click()
        time.sleep(1.0)

        with open(os.path.join(f"quizzes_{port}", "q.yaml"), encoding="utf-8") as f:
            saved = yaml.safe_load(f)
        assert saved["questions"][0]["manual_check"] is True
        assert "checker" not in saved["questions"][0]
        assert saved["questions"][0]["correct_value"] == "x"
        assert saved["questions"][1]["manual_check"] is True
